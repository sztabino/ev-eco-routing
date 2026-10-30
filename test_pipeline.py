from src.route_manager import RouteManager

def test_accurate_osm_routing():
    manager = RouteManager()
    
    # 1. Trasa Tarnobrzeg (DK9) - powinna miec 50 / 70 / 90, bez autostrady
    print("--- Trasa Rzeszów -> Tarnobrzeg ---")
    tb_route = manager.fetch_real_route((50.0412, 21.9991), (50.5732, 21.6795), name="Rzeszów -> Tarnobrzeg")
    tb_limits = [s.speed_limit_kmh for s in tb_route.segments]
    print(f"Dystans: {tb_route.total_distance_km:.1f} km")
    print(f"Wszystkie unikalne znaki drogowe z bazy OSM: {sorted(list(set(tb_limits)))} km/h")
    
    # 2. Trasa Autostrada A4 - powinna miec autentyczne 140 km/h
    print("\n--- Trasa Autostrada A4 ---")
    preset_a4 = manager.PRESETS["A4 Rzeszow -> Sedziszow Mlp (Autostrada A4)"]
    a4_route = manager.fetch_real_route(preset_a4["start"], preset_a4["end"], name="A4")
    a4_limits = [s.speed_limit_kmh for s in a4_route.segments]
    print(f"Dystans: {a4_route.total_distance_km:.1f} km")
    print(f"Wszystkie unikalne znaki drogowe z bazy OSM: {sorted(list(set(a4_limits)))} km/h")

if __name__ == "__main__":
    test_accurate_osm_routing()