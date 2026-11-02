# EV Eco-Routing & Speed Optimizer

System optymalizacji profilu prędkości samochodu elektrycznego (EV) w celu minimalizacji zużycia energii na zadanej trasie, z uwzględnieniem ukształtowania terenu i ograniczeń prędkości.

Aplikacja modeluje siły działające na pojazd (opory powietrza zależne od kwadratu prędkości, opory toczenia, grawitację na wzniesieniach i rekuperację) oraz wyznacza płynną trajektorię prędkości (Predictive Cruise Control) pozwalającą na zbalansowanie czasu przejazdu i zasięgu.

## Architektura projektu

```text
ev-eco-routing/
│
├── .github/
│   └── workflows/
│       └── ci.yml           # automatyczny pipeline CI (GitHub Actions)
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

## Założenia projektowe i model inżynierski

### 1. Model dynamiki wzdłużnej pojazdu
Całkowita siła oporu ruchu modelowana jest jako suma oporów toczenia, aerodynamiki oraz siły grawitacji na wzniesieniach:
$$F_{total} = m g c_r + \frac{1}{2} \rho_{air} C_d A v^2 + m g \cdot p$$
gdzie $p = \frac{\Delta h}{\Delta s}$ reprezentuje procentowe nachylenie jezdni pobierane z numerycznego modelu terenu NASA SRTM.

Moc na zaciskach baterii uwzględnia sprawność układu napędowego oraz nieliniowe nasycenie prądu ładowania podczas rekuperacji:
$$P_{bat} = \begin{cases} \frac{F_{total} \cdot v}{\eta_{drive}} & \text{dla } F_{total} \ge 0 \\ -\min\left(|F_{total} \cdot v| \cdot \eta_{regen}, \; P_{regen}^{max}\right) & \text{dla } F_{total} < 0 \end{cases}$$

### 2. Wielokryterialna funkcja celu (Trade-off)
Optymalizator minimalizuje znormalizowany koszt przejazdu łączący zużycie energii, czas podróży oraz karę za szarpanie (pochodną przyspieszenia):
$$J = w_E \frac{E}{E_{base}} + w_T \frac{T}{T_{base}} + w_j \frac{1}{N} \sum_{i=1}^{N-1} |v_{i+1} - v_i|$$
Wagi $w_E$ oraz $w_T = 1 - w_E$ są dynamicznie definiowane przez użytkownika za pomocą suwaka w interfejsie graficznym.

### 3. Akwizycja danych i redukcja wymiarowości (GIS)
- **Spatial Downsampling:** Wykorzystanie formuły Haversine'a do adaptacyjnego próbkowania gęstej geometrii drogowej do stałych odcinków decyzyjnych ($\Delta s \approx 350-400\text{ m}$), co redukuje przestrzeń poszukiwań o 85%.
- **Klasyfikacja prędkości:** Generyczne mapowanie klas dróg w sieci OSM (autostrady A: 140 km/h, ekspresówki S: 120 km/h, drogi krajowe i wojewódzkie: 90 km/h, obszar zabudowany: 50 km/h).
- **Subsystem Cache:** Buforowanie przetworzonych tras w plikach JSON z hashowaniem MD5 współrzędnych geograficznych.

## Główne założenia implementacji (OOP)

- `RouteManager`: pobiera geometrię trasy z OSRM, odpytuje satelitarne API Open-Meteo o realne wysokości n.p.m. dla każdego węzła oraz klasyfikuje ograniczenia prędkości na bazie europejskiego systemu oznaczeń dróg.
- `BaseVehicleModel` i `PhysicsVehicleModel`: klasa bazowa definiująca interfejs symulatora (wzorzec Strategii) oraz analityczna implementacja bilansu mocy na kołach. Baza pojazdów zawiera zweryfikowane parametry oparte o modele NREL FASTSim (Tesla Model 3, Porsche Taycan, Nissan Leaf).
- `SpeedProfileOptimizer`: predykcyjne dopasowanie prędkości z uwzględnieniem topografii (gravity assist na zjazdach, odpuszczanie gazu na podjazdach) oraz wcześniejszego wytracania prędkości przed strefami wolniejszymi (look-ahead coasting).

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

## Ciągła integracja (CI/CD)

Projekt wykorzystuje **GitHub Actions** (`.github/workflows/ci.yml`). Przy każdym zdarzeniu typu `push` oraz `pull_request` na gałąź `main`:
1. Wirtualne środowisko Ubuntu automatycznie instaluje zależności z `requirements.txt`.
2. Uruchamiany jest skrypt testów integracyjnych `test_pipeline.py`, weryfikujący poprawność obliczeń numerycznych, pobierania danych GIS oraz modelu fizycznego.