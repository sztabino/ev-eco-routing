# EV Eco-Routing & Speed Optimizer

System optymalizacji profilu prędkości samochodu elektrycznego (EV) w celu minimalizacji zużycia energii na zadanej trasie, z uwzględnieniem ukształtowania terenu i ograniczeń prędkości.

Aplikacja modeluje siły działające na pojazd (opory powietrza zależne od kwadratu prędkości, opory toczenia, grawitację na wzniesieniach i rekuperację) oraz wyznacza płynną trajektorię prędkości (Predictive Cruise Control) pozwalającą na zbalansowanie czasu przejazdu i zasięgu.

## Architektura projektu

```text
ev-eco-routing/
│
├── data/
│   └── routes_cache/        # lokalny cache pobranych tras (geojson/json)
│
├── src/
│   ├── __init__.py
│   ├── route_manager.py     # pobieranie geometrii (OSRM), elewacji (SRTM) i klasyfikacja dróg
│   ├── vehicle_model.py     # model fizyczny dynamiki wzdłużnej EV i baza parametrów pojazdów
│   └── optimizer.py         # heurystyka optymalizująca profil prędkości z filtrem płynności
│
├── app.py                   # interfejs graficzny Streamlit (mapy Folium + wykresy Plotly)
├── test_pipeline.py         # skrypt do testów integracyjnych modułów bez GUI
├── requirements.txt         # lista zależności
└── README.md
```

## Główne założenia implementacji (OOP)

- RouteManager: pobiera geometrię trasy z OSRM, odpytuje satelitarne API Open-Meteo o realne wysokości n.p.m. dla każdego węzła oraz klasyfikuje ograniczenia prędkości na bazie europejskiego systemu oznaczeń dróg (autostrady A, ekspresówki S, drogi krajowe i wojewódzkie). Zaimplementowano mechanizm cache'owania, aby ograniczyć zapytania sieciowe.
- BaseVehicleModel i PhysicsVehicleModel: klasa bazowa definiująca interfejs symulatora oraz analityczna implementacja bilansu mocy na kołach (aerodynamika, nachylenie drogi, straty przekładni i odzysk energii z hamowania). Baza pojazdów zawiera parametry wzorowane na modelach NREL FASTSim.
- SpeedProfileOptimizer: predykcyjne dopasowanie prędkości z uwzględnieniem ukształtowania terenu (odpuszczanie gazu na podjazdach, wykorzystanie grawitacji ze zjazdów) oraz wcześniejszego wytracania prędkości przed strefami wolniejszymi (coasting).

## Wymagania i instalacja

Projekt wymaga Pythona w wersji 3.10+.

1. Klonowanie repozytorium:
```bash
git clone https://github.com/sztabino/ev-eco-routing.git
cd ev-eco-routing
```

2. Utworzenie środowiska wirtualnego:
```bash
python -m venv .venv
```

Aktywacja:
- Windows:
```bash
.venv\Scripts\activate
```
- Linux / macOS:
```bash
source .venv/bin/activate
```

3. Instalacja zależności:
```bash
pip install -r requirements.txt
```

## Uruchomienie

Uruchomienie aplikacji webowej:
```bash
streamlit run app.py
```

Szybki test poprawności modelu fizycznego i routingu w konsoli:
```bash
python test_pipeline.py
```