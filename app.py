import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from geopy.geocoders import Nominatim

from src.route_manager import RouteManager
from src.vehicle_model import PhysicsVehicleModel, VehicleDatabase, VehicleParameters
from src.optimizer import SpeedProfileOptimizer, OptimizationConfig

st.set_page_config(page_title="EV Eco-Routing System", layout="wide")

st.title("🔋 EV Eco-Routing & Speed Optimizer")
st.caption("Predykcyjny system wyznaczania profilu jazdy samochodu elektrycznego na bazie rzeźby terenu i sieci OSM")

# konfiguracja pojazdu
st.sidebar.header("🚗 Konfiguracja pojazdu")
vehicle_type = st.sidebar.radio("Źródło danych pojazdu", ["Preset fabryczny", "Własna specyfikacja"])

if vehicle_type == "Preset fabryczny":
    car_name = st.sidebar.selectbox("Model", VehicleDatabase.list_models())
    vehicle_params = VehicleDatabase.get_vehicle(car_name)
else:
    col_m, col_cd = st.sidebar.columns(2)
    m = col_m.number_input("Masa [kg]", value=1650.0, step=50.0)
    cd = col_cd.number_input("Wsp. Cd", value=0.23, step=0.01)
    batt = st.sidebar.number_input("Pojemność baterii [kWh]", value=60.0, step=5.0)
    vehicle_params = VehicleParameters(
        name="Custom EV", mass_kg=m, drag_coefficient=cd,
        frontal_area_m2=2.2, rolling_resistance_coeff=0.01,
        battery_capacity_kwh=batt, max_regen_power_kw=65.0,
        powertrain_efficiency=0.91, regen_efficiency=0.82
    )

# wybor trasy
st.sidebar.header("📍 Trasa przejazdu")
route_mode = st.sidebar.radio("Wybór trasy", ["Trasy testowe (Podkarpacie)", "Własne punkty (Adresy/Miasta)"])
manager = RouteManager()

route = None
if route_mode == "Trasy testowe (Podkarpacie)":
    preset_name = st.sidebar.selectbox("Gotowa trasa", list(RouteManager.PRESETS.keys()))
    coords_preset = RouteManager.PRESETS[preset_name]
    route = manager.fetch_real_route(coords_preset["start"], coords_preset["end"], name=preset_name)
else:
    start_str = st.sidebar.text_input("Punkt startowy", "Rzeszów, Rynek")
    end_str = st.sidebar.text_input("Punkt docelowy", "Dynów")
    if st.sidebar.button("Znajdź trasę"):
        geolocator = Nominatim(user_agent="ev_eco_routing_podkarpacie")
        loc1 = geolocator.geocode(start_str)
        loc2 = geolocator.geocode(end_str)
        if loc1 and loc2:
            route = manager.fetch_real_route((loc1.latitude, loc1.longitude), (loc2.latitude, loc2.longitude), name=f"{start_str} -> {end_str}")
            st.session_state["active_route"] = route
            st.session_state.pop("opt_report", None)
        else:
            st.sidebar.error("Nie znaleziono podanych punktów.")
            
    if "active_route" in st.session_state:
        route = st.session_state["active_route"]

# styl jazdy
st.sidebar.header("⚡ Styl jazdy (Trade-off)")
eco_slider = st.sidebar.slider("Priorytet: Czas (Sport) <---> Zużycie (Eko)", 0, 100, 75)
w_energy = eco_slider / 100.0
w_time = 1.0 - w_energy

def format_time(seconds: float) -> str:
    # czytelne formatowanie czasu w minutach i godzinach
    m = int(seconds // 60)
    if m >= 60:
        return f"{m // 60}h {m % 60} min"
    return f"{m} min"

# widok glowny
if route:
    st.subheader(f"Wybrana trasa: {route.name} (dystans: {route.total_distance_km:.1f} km)")
    
    col_map, col_details = st.columns([3, 2])

    with col_map:
        coords = route.all_coordinates
        center_lat = sum(c[0] for c in coords) / len(coords)
        center_lon = sum(c[1] for c in coords) / len(coords)
        
        m_map = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")
        folium.PolyLine(coords, color="#0284C7", weight=5, opacity=0.85).add_to(m_map)
        folium.Marker(coords[0], tooltip="Start", icon=folium.Icon(color="green", icon="play")).add_to(m_map)
        folium.Marker(coords[-1], tooltip="Koniec", icon=folium.Icon(color="red", icon="stop")).add_to(m_map)
        st_folium(m_map, height=340, width=None, returned_objects=[])

    with col_details:
        st.write("### Podsumowanie parametrów")
        st.write(f"**Pojazd:** {vehicle_params.name}")
        st.write(f"**Pojemność baterii:** {vehicle_params.battery_capacity_kwh} kWh")
        st.write(f"**Segmenty telemetryczne:** {len(route.segments)}")
        st.write(f"**Waga energii:** `{w_energy:.2f}` | **Waga czasu:** `{w_time:.2f}`")

        if st.button("🚀 Przeprowadź optymalizację profilu", type="primary"):
            car = PhysicsVehicleModel(vehicle_params)
            config = OptimizationConfig(weight_energy=w_energy, weight_time=w_time)
            
            with st.spinner("Przeliczanie modelu fizycznego i wyznaczanie optymalnej trajektorii..."):
                optimizer = SpeedProfileOptimizer(car, config)
                st.session_state["opt_report"] = optimizer.optimize(route)
                st.session_state["last_route"] = route

    if "opt_report" in st.session_state and st.session_state.get("last_route") == route:
        report = st.session_state["opt_report"]

        st.divider()
        st.subheader("📊 Wyniki porównawcze")

        # karty z metrykami energii i czasu
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Oszczędność energii", f"{report.energy_saved_pct:.2f}%")
        c2.metric("Zużycie energii", f"{report.optimized_result.total_energy_kwh:.2f} kWh",
                  delta=f"-{report.baseline_result.total_energy_kwh - report.optimized_result.total_energy_kwh:.2f} kWh")
        
        time_opt_str = format_time(report.optimized_result.total_time_s)
        diff_min = report.time_diff_min
        c3.metric("Czas przejazdu", time_opt_str, delta=f"+{diff_min:.1f} min" if diff_min > 0 else f"{diff_min:.1f} min")
        c4.metric("Stan baterii (SoC)", f"{report.optimized_result.battery_soc_end * 100:.1f}%")

        distances_km = [sum(s.length_m for s in route.segments[:i+1]) / 1000.0 for i in range(len(route.segments))]
        elevations = [s.start_elevation for s in route.segments]

        # wspolny uklad marginesow gwarantujacy identyczna szerokosc i spasowanie w pionie
        chart_margin = dict(l=55, r=20, t=35, b=35)

        # wykres 1: predkosci
        fig_speed = go.Figure()
        fig_speed.add_trace(go.Scatter(
            x=distances_km, y=report.initial_speeds, mode="lines",
            name="Ograniczenie (przepisy)", line=dict(color="#EF4444", dash="dash", width=2)
        ))
        fig_speed.add_trace(go.Scatter(
            x=distances_km, y=report.optimized_speeds, mode="lines",
            name="Profil Eko (optymalizacja)", line=dict(color="#10B981", width=3)
        ))
        fig_speed.update_layout(
            title="Profil prędkości względem ograniczeń",
            xaxis_title="",
            yaxis_title="Prędkość [km/h]",
            hovermode="x unified",
            margin=chart_margin,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_speed, use_container_width=True)

        # wykres 2: elewacja (identyczna szerokosc osi x)
        fig_elev = go.Figure()
        fig_elev.add_trace(go.Scatter(
            x=distances_km, y=elevations, mode="lines",
            name="Wysokość", fill="tozeroy", line=dict(color="#0284C7")
        ))
        fig_elev.update_layout(
            title="Profil wysokościowy trasy",
            xaxis_title="Dystans [km]",
            yaxis_title="Wysokość [m n.p.m.]",
            hovermode="x unified",
            margin=chart_margin,
            showlegend=False
        )
        st.plotly_chart(fig_elev, use_container_width=True)

        # wykres 3: zbieznosc algorytmu heurystycznego / epoki
        fig_fit = go.Figure()
        fig_fit.add_trace(go.Scatter(
            y=report.fitness_history, mode="lines+markers",
            name="Koszt funkcji celu", line=dict(color="#8B5CF6", width=2.5),
            marker=dict(size=4)
        ))
        fig_fit.update_layout(
            title="Zbieżność algorytmu optymalizacyjnego (Kolejne iteracje / generacje)",
            xaxis_title="Epoka optymalizacji",
            yaxis_title="Wartość funkcji kosztu",
            hovermode="x unified",
            margin=chart_margin,
            showlegend=False
        )
        st.plotly_chart(fig_fit, use_container_width=True)