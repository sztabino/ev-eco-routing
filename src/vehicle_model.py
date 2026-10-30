from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class SimulationResult:
    # zunifikowany wynik symulacji przejazdu
    total_energy_kwh: float
    total_time_s: float
    battery_soc_end: float


@dataclass
class VehicleParameters:
    # parametry fizyczne i elektryczne pojazdu wzorowane na bazie fastsim
    name: str
    mass_kg: float
    drag_coefficient: float  # cd
    frontal_area_m2: float   # a
    rolling_resistance_coeff: float  # cr
    battery_capacity_kwh: float
    max_regen_power_kw: float
    powertrain_efficiency: float
    regen_efficiency: float


class VehicleDatabase:
    # wbudowana baza rzeczywistych modeli pojazdow (dane zbiezne z nrel fastsim)
    
    MODELS: Dict[str, VehicleParameters] = {
        "Tesla Model 3 Standard": VehicleParameters(
            name="Tesla Model 3 Standard",
            mass_kg=1611.0,
            drag_coefficient=0.23,
            frontal_area_m2=2.22,
            rolling_resistance_coeff=0.009,
            battery_capacity_kwh=57.5,
            max_regen_power_kw=70.0,
            powertrain_efficiency=0.92,
            regen_efficiency=0.85
        ),
        "Nissan Leaf 40kWh": VehicleParameters(
            name="Nissan Leaf 40kWh",
            mass_kg=1580.0,
            drag_coefficient=0.28,
            frontal_area_m2=2.27,
            rolling_resistance_coeff=0.010,
            battery_capacity_kwh=40.0,
            max_regen_power_kw=50.0,
            powertrain_efficiency=0.88,
            regen_efficiency=0.78
        ),
        "Porsche Taycan Turbo": VehicleParameters(
            name="Porsche Taycan Turbo",
            mass_kg=2305.0,
            drag_coefficient=0.22,
            frontal_area_m2=2.33,
            rolling_resistance_coeff=0.011,
            battery_capacity_kwh=93.4,
            max_regen_power_kw=100.0,
            powertrain_efficiency=0.91,
            regen_efficiency=0.88
        )
    }

    @classmethod
    def get_vehicle(cls, model_name: str) -> VehicleParameters:
        if model_name not in cls.MODELS:
            raise ValueError(f"nieznany model pojazdu: {model_name}. dostepne: {list(cls.MODELS.keys())}")
        return cls.MODELS[model_name]

    @classmethod
    def list_models(cls) -> List[str]:
        return list(cls.MODELS.keys())


class BaseVehicleModel(ABC):
    # interfejs strategii obliczania zuzycia energii

    @abstractmethod
    def simulate_route(self, route, speeds_kmh: List[float], initial_soc: float = 1.0) -> SimulationResult:
        pass


class PhysicsVehicleModel(BaseVehicleModel):
    # silnik symulacji bazujacy na bilansie sil wzdluznych pojazdu

    AIR_DENSITY = 1.225  # kg/m^3
    GRAVITY = 9.81       # m/s^2

    def __init__(self, params: VehicleParameters):
        self.params = params

    def _calculate_segment(self, segment, speed_kmh: float) -> tuple[float, float]:
        v = speed_kmh / 3.6
        if v <= 0.0:
            return 0.0, 0.0

        time_s = segment.length_m / v

        # obliczanie oporow ruchu
        f_roll = self.params.mass_kg * self.GRAVITY * self.params.rolling_resistance_coeff
        f_air = 0.5 * self.AIR_DENSITY * self.params.drag_coefficient * self.params.frontal_area_m2 * (v ** 2)
        f_grade = self.params.mass_kg * self.GRAVITY * segment.grade

        f_total = f_roll + f_air + f_grade
        power_watts = f_total * v

        # rozliczenie pracy silnika i rekuperacji
        if power_watts >= 0:
            power_kw = (power_watts / 1000.0) / self.params.powertrain_efficiency
        else:
            recovered_kw = (abs(power_watts) / 1000.0) * self.params.regen_efficiency
            power_kw = -min(recovered_kw, self.params.max_regen_power_kw)

        energy_kwh = power_kw * (time_s / 3600.0)
        return energy_kwh, time_s

    def simulate_route(self, route, speeds_kmh: List[float], initial_soc: float = 1.0) -> SimulationResult:
        total_energy = 0.0
        total_time = 0.0

        for segment, speed in zip(route.segments, speeds_kmh):
            e_kwh, t_s = self._calculate_segment(segment, speed)
            total_energy += e_kwh
            total_time += t_s

        used_soc = total_energy / self.params.battery_capacity_kwh
        end_soc = max(0.0, min(1.0, initial_soc - used_soc))

        return SimulationResult(
            total_energy_kwh=total_energy,
            total_time_s=total_time,
            battery_soc_end=end_soc
        )