from src.route_manager import RouteManager

def test_route_generation():
    # weryfikacja generowania syntetycznej trasy
    manager = RouteManager()
    route = manager.generate_synthetic_route(total_distance_m=5000.0, step_m=200.0)
    
    print(f"liczba segmentow: {len(route.segments)}")
    print(f"calkowity dystans: {route.total_distance_km:.2f} km")
    print(f"nachylenie pierwszego segmentu: {route.segments[0].grade:.4f}")

if __name__ == "__main__":
    test_route_generation()