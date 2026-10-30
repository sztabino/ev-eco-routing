from src.route_manager import RouteManager
from src.vehicle_model import PhysicsVehicleModel, VehicleDatabase, VehicleParameters

def test_pipeline():
    # generowanie trasy
    manager = RouteManager()
    route = manager.generate_synthetic_route(total_distance_m=10000.0, step_m=200.0)
    speeds = [s.speed_limit_kmh for s in route.segments]

    print("dostepne auta w bazie:", VehicleDatabase.list_models())

    # test 1: gotowy preset z bazy (tesla)
    tesla_params = VehicleDatabase.get_vehicle("Tesla Model 3 Standard")
    tesla_model = PhysicsVehicleModel(tesla_params)
    res_tesla = tesla_model.simulate_route(route, speeds)
    print(f"[{tesla_params.name}] energia: {res_tesla.total_energy_kwh:.3f} kwh, czas: {res_tesla.total_time_s / 60:.2f} min, soc: {res_tesla.battery_soc_end*100:.1f}%")

    # test 2: wlasne auto zdefiniowane z reki
    custom_params = VehicleParameters(
        name="Wlasny EV",
        mass_kg=1200.0,
        drag_coefficient=0.20,
        frontal_area_m2=2.0,
        rolling_resistance_coeff=0.008,
        battery_capacity_kwh=45.0,
        max_regen_power_kw=40.0,
        powertrain_efficiency=0.95,
        regen_efficiency=0.85
    )
    custom_model = PhysicsVehicleModel(custom_params)
    res_custom = custom_model.simulate_route(route, speeds)
    print(f"[{custom_params.name}] energia: {res_custom.total_energy_kwh:.3f} kwh, czas: {res_custom.total_time_s / 60:.2f} min, soc: {res_custom.battery_soc_end*100:.1f}%")

if __name__ == "__main__":
    test_pipeline()