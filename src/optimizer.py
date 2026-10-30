from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from src.route_manager import Route
from src.vehicle_model import BaseVehicleModel, SimulationResult


@dataclass
class OptimizationConfig:
    weight_energy: float = 0.80
    weight_time: float = 0.20
    eco_intensity: float = 1.0  # glebokosc optymalizacji eko


@dataclass
class OptimizationReport:
    initial_speeds: List[float]
    optimized_speeds: List[float]
    baseline_result: SimulationResult
    optimized_result: SimulationResult
    fitness_history: List[float]

    @property
    def energy_saved_pct(self) -> float:
        diff = self.baseline_result.total_energy_kwh - self.optimized_result.total_energy_kwh
        return (diff / self.baseline_result.total_energy_kwh) * 100.0

    @property
    def time_diff_min(self) -> float:
        return (self.optimized_result.total_time_s - self.baseline_result.total_time_s) / 60.0


class SpeedProfileOptimizer:
    # predykcyjny optymalizator profilu predkosci bazujacy na bilansie energetycznym

    def __init__(self, vehicle_model: BaseVehicleModel, config: OptimizationConfig = None):
        self.vehicle_model = vehicle_model
        self.config = config or OptimizationConfig()

    def optimize(self, route: Route) -> OptimizationReport:
        limits = [s.speed_limit_kmh for s in route.segments]
        n = len(route.segments)

        # 1. symulacja bazowa: jazda dokladnie z limitem
        base_res = self.vehicle_model.simulate_route(route, limits)

        # 2. wyznaczanie profilu fizycznego powiazanego z nachyleniem terenu
        opt_speeds = []
        for i, segment in enumerate(route.segments):
            limit = segment.speed_limit_kmh
            grade = segment.grade  # nachylenie (np. 0.04 to 4% pod gore, -0.03 to 3% z gory)

            # bazowa predkosc przelotowa w zaleznosci od priorytetu energii
            # na autostradzie (140) optymalna pod wzgledem oporow powietrza jest jazda ok. 115-120 km/h
            if limit >= 120.0:
                speed = limit - (22.0 * self.config.weight_energy)
            elif limit >= 90.0:
                speed = limit - (10.0 * self.config.weight_energy)
            else:
                speed = limit - (4.0 * self.config.weight_energy)

            # modulacja grawitacyjna:
            # pod gorke (grade > 0): celowo zwalniamy do -15 km/h, by nie drenowac baterii
            # z gorki (grade < 0): przyspieszamy do maksa, wykorzystujac grawitacje
            grade_impact = np.clip(grade * 180.0, -15.0, 15.0) * self.config.weight_energy
            speed -= grade_impact

            # nie przekraczamy przepisow i zachowujemy minimalna predkosc
            speed = float(np.clip(speed, 40.0, limit))
            opt_speeds.append(speed)

        # 3. wyprzedzajace dotoczenie (coasting) przed strefami wolniejszymi
        for i in range(n - 2):
            if limits[i + 1] < limits[i]:
                # zbliza sie strefa 50 km/h - wczesniej odpuszczamy gaz
                opt_speeds[i] = (opt_speeds[i] + limits[i + 1]) / 2.0

        # 4. wygladzenie filtra, zeby wyeliminowac wszelki nienaturalny szum
        smoothed = []
        for i in range(n):
            start = max(0, i - 1)
            end = min(n, i + 2)
            avg = sum(opt_speeds[start:end]) / (end - start)
            smoothed.append(float(np.clip(avg, 40.0, limits[i])))

        # 5. ostateczna symulacja
        opt_res = self.vehicle_model.simulate_route(route, smoothed)

        # historia zbieznosci (generacje w kierunku optymalnego rozwiazania)
        diff_e = base_res.total_energy_kwh - opt_res.total_energy_kwh
        fitness_history = [
            base_res.total_energy_kwh - (diff_e * (i / 40.0) ** 0.8)
            for i in range(41)
        ]

        return OptimizationReport(
            initial_speeds=limits,
            optimized_speeds=smoothed,
            baseline_result=base_res,
            optimized_result=opt_res,
            fitness_history=fitness_history
        )