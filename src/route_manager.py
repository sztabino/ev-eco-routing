from dataclasses import dataclass
from typing import List, Tuple
import requests
import numpy as np


@dataclass
class RoadSegment:
    # pojedynczy odcinek drogi o stałych parametrach
    length_m: float
    speed_limit_kmh: float
    grade: float  # nachylenie drogi w procentach (np. 0.05 to 5% wzniosu)
    start_elevation: float
    end_elevation: float


@dataclass
class Route:
    # zagregowana trasa skladajaca sie z segmentow
    segments: List[RoadSegment]

    @property
    def total_distance_km(self) -> float:
        return sum(s.length_m for s in self.segments) / 1000.0


class RouteManager:
    # zarzadzanie pozyskiwaniem i parsowaniem danych drogowych

    def __init__(self, elevation_api_url: str = "https://api.open-elevation.com/api/v1/lookup"):
        self.elevation_api_url = elevation_api_url

    def get_route_from_osrm(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> List[Tuple[float, float]]:
        # pobranie geometrii trasy (lat, lon) przez publiczne api osrm
        # coords: (szerokosc, dlugosc)
        url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        raw_coords = data['routes'][0]['geometry']['coordinates']
        # osrm zwraca [lon, lat], zamieniamy na [lat, lon]
        return [(point[1], point[0]) for point in raw_coords]

    def generate_synthetic_route(self, total_distance_m: float = 10000.0, step_m: float = 100.0) -> Route:
        # profil syntetyczny do testowania fizyki i algorytmu bez uzycia sieci
        steps = int(total_distance_m / step_m)
        segments = []
        
        current_elevation = 100.0
        for i in range(steps):
            # zmienny profil terenu: sinusoida
            # co jakis czas zmiana limitu predkosci
            grade = 0.03 * np.sin(i / 10.0)  # od -3% do +3%
            elevation_diff = step_m * grade
            next_elevation = current_elevation + elevation_diff
            
            # sztuczne ograniczenia predkosci zalezne od odcinka
            if i < steps * 0.3:
                speed_limit = 50.0
            elif i < steps * 0.7:
                speed_limit = 90.0
            else:
                speed_limit = 70.0
                
            segment = RoadSegment(
                length_m=step_m,
                speed_limit_kmh=speed_limit,
                grade=grade,
                start_elevation=current_elevation,
                end_elevation=next_elevation
            )
            segments.append(segment)
            current_elevation = next_elevation

        return Route(segments=segments)