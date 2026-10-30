from src.route_manager import RouteManager
from src.vehicle_model import PhysicsVehicleModel, VehicleDatabase
from src.optimizer import SpeedProfileOptimizer, OptimizationConfig

def test_optimization():
    # tworzenie dluzszej trasy testowej (20 km) z gorkami
    manager = RouteManager()
    route = manager.generate_synthetic_route(total_distance_m=20000.0, step_m=200.0)

    # pojazd
    params = VehicleDatabase.get_vehicle("Tesla Model 3 Standard")
    car = PhysicsVehicleModel(params)

    # konfiguracja optymalizatora
    config = OptimizationConfig(
        weight_energy=1.0,
        weight_time=0.5,
        penalty_jerk=0.2,
        population_size=30,
        generations=40
    )

    optimizer = SpeedProfileOptimizer(car, config)
    print("rozpoczynam optymalizacje profilu...")
    report = optimizer.optimize(route)

    print("\n--- wyniki optymalizacji ---")
    print(f"poczatkowa energia: {report.baseline_result.total_energy_kwh:.3f} kwh")
    print(f"optymalna energia:  {report.optimized_result.total_energy_kwh:.3f} kwh")
    print(f"zaoszczedzono energii: {report.energy_saved_pct:.2f}%")
    print(f"roznica w czasie jazdy: {report.time_diff_min:+.2f} min")

if __name__ == "__main__":
    test_optimization()