from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict
import os
import json
import hashlib
import requests
import numpy as np


@dataclass
class RoadSegment:
    length_m: float
    speed_limit_kmh: float
    grade: float
    start_elevation: float
    end_elevation: float
    coords: Tuple[float, float]


@dataclass
class Route:
    name: str
    segments: List[RoadSegment]

    @property
    def total_distance_km(self) -> float:
        return sum(s.length_m for s in self.segments) / 1000.0

    @property
    def all_coordinates(self) -> List[Tuple[float, float]]:
        return [s.coords for s in self.segments]


class RouteManager:
    # uniwersalny menedzer tras z generyczna klasyfikacja drogowa i danymi srtm

    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "routes_cache")

    PRESETS: Dict[str, Dict] = {
        "A4 Rzeszow -> Sedziszow Mlp (Autostrada A4)": {
            "start": (50.1080, 21.9800),
            "end": (50.1180, 21.6850)
        },
        "Rzeszow -> Lancut (DK94)": {
            "start": (50.0412, 21.9991),
            "end": (50.0673, 22.2307)
        },
        "Rzeszow -> Dynow (DW878)": {
            "start": (50.0412, 21.9991),
            "end": (49.8152, 22.2331)
        }
    }

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def _haversine(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        lat1, lon1 = np.radians(p1)
        lat2, lon2 = np.radians(p2)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
        return float(6371000.0 * 2 * np.arcsin(np.sqrt(a)))

    def _get_cache_path(self, start: Tuple[float, float], end: Tuple[float, float]) -> str:
        key = f"{start[0]:.4f}_{start[1]:.4f}_{end[0]:.4f}_{end[1]:.4f}"
        return os.path.join(self.CACHE_DIR, f"route_{hashlib.md5(key.encode()).hexdigest()[:10]}.json")

    def _fetch_elevations(self, coords: List[Tuple[float, float]]) -> List[float]:
        elevations = []
        chunk_size = 40

        for i in range(0, len(coords), chunk_size):
            chunk = coords[i:i + chunk_size]
            lats = ",".join(f"{pt[0]:.4f}" for pt in chunk)
            lons = ",".join(f"{pt[1]:.4f}" for pt in chunk)
            url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"

            try:
                res = requests.get(url, timeout=8).json()
                if "elevation" in res:
                    elevations.extend([float(e) for e in res["elevation"]])
                else:
                    elevations.extend([210.0 for _ in chunk])
            except Exception:
                elevations.extend([210.0 for _ in chunk])

        return elevations

    def _determine_step_speed(self, step: Dict) -> float:
        # generyczna klasyfikacja na podstawie oznaczen sieci drogowej
        ref = step.get('ref', '').upper().replace(" ", "")
        maneuver_type = step.get('maneuver', {}).get('type', '')

        # 1. manewry na skrzyzowaniach i rondach
        if maneuver_type in ['roundabout', 'rotary']:
            return 40.0

        # 2. siec autostrad (np. A4, A1, A2)
        if ref.startswith('A') and any(char.isdigit() for char in ref):
            return 140.0

        # 3. drogi ekspresowe (np. S19, S7, S8)
        if ref.startswith('S') and any(char.isdigit() for char in ref):
            return 120.0

        # 4. drogi krajowe jedno- i dwucyfrowe (np. DK9, DK94, 9, 94)
        if ref.startswith('DK') or (ref.isdigit() and len(ref) <= 2):
            return 90.0

        # 5. drogi wojewodzkie trzycyfrowe (np. DW878, 878, 988)
        if ref.startswith('DW') or (ref.isdigit() and len(ref) == 3):
            return 90.0

        # 6. drogi lokalne wewnatrz miast i wsi (obszar zabudowany)
        return 50.0

    def fetch_real_route(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], name: str = "Trasa") -> Route:
        cache_file = self._get_cache_path(start_coords, end_coords)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Route(name=name, segments=[RoadSegment(**s) for s in data["segments"]])
            except Exception:
                pass

        # odpytanie serwera routingu o dokladne kroki drogowe
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        res = requests.get(url, timeout=10).json()
        route_obj = res['routes'][0]
        
        raw_points = []
        raw_speeds = []

        for leg in route_obj['legs']:
            for step in leg['steps']:
                step_limit = self._determine_step_speed(step)
                coords = step['geometry']['coordinates']
                for pt in coords:
                    raw_points.append((pt[1], pt[0]))
                    raw_speeds.append(step_limit)

        # probkowanie co 350m
        sampled_coords = [raw_points[0]]
        sampled_limits = [raw_speeds[0]]

        for i in range(1, len(raw_points)):
            if self._haversine(sampled_coords[-1], raw_points[i]) >= 350.0:
                sampled_coords.append(raw_points[i])
                sampled_limits.append(raw_speeds[i])

        if sampled_coords[-1] != raw_points[-1]:
            sampled_coords.append(raw_points[-1])
            sampled_limits.append(raw_speeds[-1])

        elevations = self._fetch_elevations(sampled_coords)

        segments = []
        for i in range(len(sampled_coords) - 1):
            p1 = sampled_coords[i]
            p2 = sampled_coords[i + 1]
            dist = self._haversine(p1, p2)
            if dist <= 0:
                continue

            h_start = elevations[i]
            h_end = elevations[i + 1]
            grade = (h_end - h_start) / dist

            segments.append(RoadSegment(
                length_m=dist,
                speed_limit_kmh=sampled_limits[i],
                grade=grade,
                start_elevation=h_start,
                end_elevation=h_end,
                coords=p1
            ))

        new_route = Route(name=name, segments=segments)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"name": name, "segments": [asdict(s) for s in segments]}, f, indent=2)
        except Exception:
            pass

        return new_route