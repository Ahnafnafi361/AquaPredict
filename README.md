# AquaPredict · Houston Pilot (M0–M10 Implementation)

Urban waterlogging risk visualization prototype using a selected pilot area in Downtown Houston, Texas.

---

## 1. Project Overview & Milestones

### Milestone 0 (M0) — Base Interactive Map & GIS Layers
* **Houston Pilot Sector:** Strictly bounded to Downtown Houston / Buffalo Bayou:
  * **Bounding Box (WGS84):** West: `-95.3750°`, South: `29.7560°`, East: `-95.3650°`, North: `29.7650°` (~$0.97\,\text{km}^2$).
* **DEM Terrain Visualization:**
  * High-resolution 1-meter Bare Earth DEM from NOAA 2018 Coastal Texas (StratMap18).
  * 100% complete coverage over the pilot boundary (0 missing pixels).
  * Toggleable Topographic Hypsometric Tint and 3D Shaded Relief / Hillshade.
* **Toggleable Storm Drainage Network Layers:**
  * **Gravity Mains:** 624 conduits styled by diameter.
  * **Inlets:** 265 street intake nodes.
  * **Manholes:** 283 inspection junctions.
  * **Discharge Points:** 4 bayou outfall terminals.

### Milestone 1 (M1) — Terrain-Based Waterlogging Susceptibility Analysis
* **Exploratory Waterlogging Susceptibility Index (EWSI):** Multi-criteria screening model integrating:
  1. Local Topographic Depressions / Sinks (35%).
  2. Topographic Position Index / Relative Elevation (25%).
  3. Surface Slope Flatness (20%).
  4. Drainage Proximity (20%).
* **Tier Distribution in Pilot Area:** Low (69.7%), Moderate (23.5%), Elevated (5.8%), High (1.0%).

### Milestone 2 (M2) — Rainfall Ingestion & QA Pipeline
* Automated ingestion of sub-hourly (15-minute) gauge observations from Harris County Flood Warning System (HCFWS) Station 1600.
* State-aware QA flags: `UNAVAILABLE`, `UNVERIFIED`, `VERIFIED`, `INVALID`.

### Milestone 3 (M3) — Historical Flood Validation Readiness Audit
* Systematic audit against 6 historical storm events (Hurricane Harvey 2017, Tax Day 2016, Memorial Day 2015, Imelda 2019, Allison 2001, May 2024 Derecho).
* Explicit status: **UNAVAILABLE** (no empirical street-level flood depth calibration data).

### Milestone 4 (M4) — Dynamic Rainfall–Susceptibility Synthesis
* Bivariate matrix synthesis coupling dynamic 15-minute rainfall intensity with static M1 terrain susceptibility tiers.

### Milestone 5 (M5) — Scenario Simulation Engine
* Hydrological screening simulation model evaluating 5 rainfall presets (10mm, 25mm, 50mm, 75mm, 100mm over 180 min).
* 5-class flood depth raster: Dry, Shallow ($\le 0.05\,\text{m}$), Moderate ($0.05\text{--}0.20\,\text{m}$), Deep ($0.20\text{--}0.50\,\text{m}$), Very Deep ($> 0.50\,\text{m}$).

### Milestone 6 (M6) — Drainage Network Capacity & Hotspot Screening
* Hydraulic capacity evaluation using Manning's equation for circular pipes.
* Full topological upstream/downstream network graph tracing flow to Buffalo Bayou outfalls.

### Milestone 7 (M7) — Drainage-Informed Route Planner Engine
* Multi-criteria Dijkstra network routing over 200 street centerlines (210 directed edges).
* Compares 3 alternative route profiles: Baseline Shortest, Drainage-Informed, and Low-Susceptibility.
* Supports pedestrian mode and strict vehicular one-way constraint enforcement.

### Milestone 8 (M8) — Interactive 3D Terrain & Flood View
* Continuous 256×256 elevation heightmap mesh rendered using Three.js and OrbitControls.
* Synchronized 3D flood depth surface draping and drainage pipe overlay with configurable vertical exaggeration (1.0× to 10.0×).

### Milestone 9 (M9) — ML Surrogate of the Screening Model
* `HistGradientBoostingRegressor` machine learning surrogate trained to emulate M5 simulation outputs.
* **Full-Scenario Benchmark (M9 Verified):** Original screening simulation ($1.448\,\text{ms}$ median) is ~$868\times$ faster than the ML surrogate pipeline ($1,256.59\,\text{ms}$ median). (Note: Established during M9 audit; not re-run during M10). In M10, cached in-memory frame retrieval was separately measured at $0.008\,\text{ms}$.
* Explicit scientific warning banner displayed whenever surrogate mode is active.

### Milestone 10 (M10) — Hardening, Bangla, Static Export & Deployment
* **Technical Hardening:** 0 security vulnerabilities (`pip-audit` & `npm audit`), 0 lint/type-check errors, 89 passed regression tests.
* **Bangla Internationalisation (`i18n/bn.json`):** Full bilingual interface with seamless language toggle; all scientific warnings preserved in both English and Bangla.
* **Static Export Mode (`dist_static/`):** Standalone distribution requiring no Python backend; displays precomputed scenarios, 3D views, and routing.
* **Deployment Documentation:** Full deployment guide for Windows PowerShell, Static Web Hosting, and Containerized Docker host (`DEPLOYMENT.md`).

---

## 2. Scientific Guardrails & Disclaimers

> [!IMPORTANT]
> * **Screening Indicator Only:** AquaPredict is **NOT an official flood forecasting system, certified 1D/2D hydrodynamic model, or real-time flood warning tool**.
> * **Unvalidated Outputs:** Model outputs have not been calibrated or verified against observed street flood depths. Accuracy is unknown.
> * **Strict Pilot Boundary:** The analysis applies strictly to the $0.97\,\text{km}^2$ Downtown Houston pilot boundary and must not be extrapolated citywide.

---

## 3. Quickstart & Usage

### A. Local Python Server (Full Mode)
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend server
python serve.py
```
Open `http://localhost:8000/`.

### B. Static Hosting (Offline Precomputed Mode)
```bash
# Generate static export bundle
python scripts/export_static.py

# Serve statically via plain HTTP server (no Python backend needed)
cd dist_static
python -m http.server 8080
```
Open `http://localhost:8080/`.

### C. Performance Benchmarks
```bash
python scripts/bench.py
```

### D. Running Tests
```bash
python -m unittest discover -s scripts -p "test_*.py"
```

---

## 4. Documentation Links

* [Model Card & Technical Specifications](docs/model_card.md)
* [Data Sources & Provenance Audit](docs/data_sources.md)
* [Deployment Guide](DEPLOYMENT.md)
* [Historical Flood Validation Readiness (M3)](docs/M3_VALIDATION_READINESS.md)
* [Drainage Network Audit (M6)](docs/M6_DRAINAGE_DATA_AUDIT.md)
* [Routing Data Audit (M7)](docs/M7_ROUTING_DATA_AUDIT.md)
