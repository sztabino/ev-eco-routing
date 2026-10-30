from dataclasses import dataclass
from typing import List, Tuple
import random
import copy
import numpy as np

from src.route_manager import Route
from src.vehicle_model import BaseVehicleModel, SimulationResult


@dataclass
class OptimizationConfig:
    # wagi funkcji celu
    # w_energy: 1.0, w_time: 0.0 -> czyste eko
    # w_energy: 0.2, w_time: 0.8 -> zbalansowany szybki dojazd
    weight_energy: float = 0.8
    weight_time: float = 0.2
    penalty_jerk: float = 0.05
    population_size: int = 40
    generations: int = 60
    mutation_rate: float = 0.3
    min_speed_kmh: float = 30.0


@dataclass
class OptimizationReport:
    # zestawienie wynikow przed i po optymalizacji
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
    # optymalizator profilu predkosci z wygladzaniem trajektorii

    def __init__(self, vehicle_model: BaseVehicleModel, config: OptimizationConfig = None):
        self.vehicle_model = vehicle_model
        self.config = config or OptimizationConfig()

    def _smooth_profile(self, speeds: List[float], limits: List[float]) -> List[float]:
        # filtr sredniej ruchomej, zeby uniknac szarpania (nierealistycznego stylu jazdy)
        smoothed = []
        n = len(speeds)
        for i in range(n):
            # okno 3-elementowe
            start = max(0, i - 1)
            end = min(n, i + 2)
            avg = sum(speeds[start:end]) / (end - start)
            # scinamy do limitu przepisowego i min predkosci
            low = min(self.config.min_speed_kmh, limits[i])
            smoothed.append(float(np.clip(avg, low, limits[i])))
        return smoothed

    def _calculate_cost(self, route: Route, speeds: List[float], base_energy: float, base_time: float) -> Tuple[float, SimulationResult]:
        # normalizacja wartosci energii i czasu wzgledem przejazdu bazowego (skala 0.0 - 1.0)
        sim_res = self.vehicle_model.simulate_route(route, speeds)

        norm_energy = sim_res.total_energy_kwh / base_energy if base_energy > 0 else 1.0
        norm_time = sim_res.total_time_s / base_time if base_time > 0 else 1.0

        # kara za szarpanie (roznice predkosci miedzy kolejnymi krokami)
        jerk = sum(abs(speeds[i + 1] - speeds[i]) for i in range(len(speeds) - 1))
        norm_jerk = jerk / (len(speeds) * 50.0)  # odniesienie do skali 50 km/h roznicy

        total_cost = (
            self.config.weight_energy * norm_energy +
            self.config.weight_time * norm_time +
            self.config.penalty_jerk * norm_jerk
        )
        return total_cost, sim_res

    def _create_individual(self, limits: List[float], route: Route) -> List[float]:
        # inicjalizacja osobnika: bazujemy na limitach z losowym obnizeniem predkosci (zwlaszcza pod gorke)
        ind = []
        for i, limit in enumerate(limits):
            grade = route.segments[i].grade
            # na podjazdach intuicyjnie oplaca sie jechac wolniej, z gorki blisko limitu
            reduction = random.uniform(0.7, 1.0)
            if grade > 0.01:
                reduction *= random.uniform(0.75, 0.95)
            
            speed = limit * reduction
            low = min(self.config.min_speed_kmh, limit)
            ind.append(float(np.clip(speed, low, limit)))
        return self._smooth_profile(ind, limits)

    def _mutate(self, individual: List[float], limits: List[float]):
        # mutacja blokowa - zmiana predkosci na pewnym odcinku trasy zamiast w jednym punkcie
        n = len(individual)
        idx_start = random.randint(0, n - 1)
        length = random.randint(1, max(2, n // 5))
        delta = random.uniform(-15.0, 15.0)

        for i in range(idx_start, min(n, idx_start + length)):
            low = min(self.config.min_speed_kmh, limits[i])
            individual[i] = float(np.clip(individual[i] + delta, low, limits[i]))

    def optimize(self, route: Route) -> OptimizationReport:
        limits = [s.speed_limit_kmh for s in route.segments]

        # wyznaczenie wartosci odniesienia dla bazy
        base_res = self.vehicle_model.simulate_route(route, limits)
        base_energy = base_res.total_energy_kwh
        base_time = base_res.total_time_s

        base_cost, _ = self._calculate_cost(route, limits, base_energy, base_time)

        # generowanie populacji
        population = [self._create_individual(limits, route) for _ in range(self.config.population_size - 1)]
        population.append(copy.deepcopy(limits))  # profil bazowy w populacji

        best_cost = base_cost
        best_ind = copy.deepcopy(limits)
        fitness_history = []

        for gen in range(self.config.generations):
            costs_res = [self._calculate_cost(route, ind, base_energy, base_time) for ind in population]
            costs = [cr[0] for cr in costs_res]

            # zapis najlepszego wyniku
            min_c = min(costs)
            if min_c < best_cost:
                best_cost = min_c
                best_ind = copy.deepcopy(population[costs.index(min_c)])

            fitness_history.append(best_cost)

            # reprodukcja (elityzm + selekcja turniejowa)
            new_pop = [copy.deepcopy(best_ind)]

            while len(new_pop) < self.config.population_size:
                # turniej 3-osobnikowy
                p1 = min(random.sample(population, 3), key=lambda ind: self._calculate_cost(route, ind, base_energy, base_time)[0])
                p2 = min(random.sample(population, 3), key=lambda ind: self._calculate_cost(route, ind, base_energy, base_time)[0])

                # krzyzowanie
                pt = random.randint(1, len(limits) - 1)
                child = p1[:pt] + p2[pt:]

                # mutacja
                if random.random() < self.config.mutation_rate:
                    self._mutate(child, limits)

                # wygladzenie trajektorii
                child = self._smooth_profile(child, limits)
                new_pop.append(child)

            population = new_pop

        # ostateczne podsumowanie
        _, opt_res = self._calculate_cost(route, best_ind, base_energy, base_time)

        return OptimizationReport(
            initial_speeds=limits,
            optimized_speeds=best_ind,
            baseline_result=base_res,
            optimized_result=opt_res,
            fitness_history=fitness_history
        )