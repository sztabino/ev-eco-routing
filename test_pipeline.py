from src.route_manager import RouteManager
from src.vehicle_model import PhysicsVehicleModel, VehicleDatabase
from src.optimizer import SpeedProfileOptimizer, OptimizationConfig


def test_end_to_end_pipeline():
    # test integracyjny calego pipeline'u numerycznego
    print("1. Inicjalizacja trasy testowej...")
    manager = RouteManager()
    preset = manager.PRESETS["A4 Rzeszow -> Sedziszow Mlp (Autostrada A4)"]
    route = manager.fetch_real_route(preset["start"], preset["end"], name="Trasa Testowa CI")

    assert len(route.segments) > 0, "Trasa nie zawiera segmentow"
    assert route.total_distance_km > 0.0, "Dystans trasy musi byc wiekszy od zera"
    print(f"   Dystans: {route.total_distance_km:.2f} km, segmenty: {len(route.segments)}")

    print("\n2. Weryfikacja bazy i modelu fizycznego EV...")
    car_params = VehicleDatabase.get_vehicle("Tesla Model 3 Standard")
    car = PhysicsVehicleModel(car_params)

    # symulacja bazowa
    baseline_speeds = [s.speed_limit_kmh for s in route.segments]
    base_res = car.simulate_route(route, baseline_speeds)
    assert base_res.total_energy_kwh > 0.0, "Zuzycie energii bazowej musi byc dodatnie"
    print(f"   Energia bazowa: {base_res.total_energy_kwh:.3f} kWh, SoC: {base_res.battery_soc_end*100:.1f}%")

    print("\n3. Weryfikacja optymalizatora profilu predkosci...")
    config = OptimizationConfig(weight_energy=0.8, weight_time=0.2)
    optimizer = SpeedProfileOptimizer(car, config)
    report = optimizer.optimize(route)

    # asercje poprawnej optymalizacji
    assert report.optimized_result.total_energy_kwh < report.baseline_result.total_energy_kwh, "Optymalizator nie zredukowal zuzycia energii"
    assert 0.0 <= report.optimized_result.battery_soc_end <= 1.0, "SoC poza zakresem [0, 1]"
    assert len(report.optimized_speeds) == len(route.segments), "Niezgodnosc wymiarow wektora predkosci"

    print(f"   Zaoszczedzona energia: {report.energy_saved_pct:.2f}%")
    print(f"   Roznica czasu: {report.time_diff_min:+.2f} min")
    print("\n[OK] Caly pipeline integracyjny przeszedl pomyslnie.")


if __name__ == "__main__":
    test_end_to_end_pipeline()