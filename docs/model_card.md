# AquaPredict Model Card & Technical Specifications

**Milestone:** M10 Hardening & Static Export  
**Version:** 0.10.0  
**Target Sector:** Downtown Houston / Buffalo Bayou Pilot Sector  
**Bounding Box (WGS84):** West: `-95.3750°`, South: `29.7560°`, East: `-95.3650°`, North: `29.7650°` (~$0.97\,\text{km}^2$)  
**Status:** **RESEARCH PROTOTYPE — UNVALIDATED AGAINST REAL-WORLD FLOOD OBSERVATIONS**

---

## 1. Model Description & Intended Scope

AquaPredict provides screening-level visualization and exploration of urban waterlogging tendencies. It combines high-resolution LiDAR bare earth topography, municipal stormwater drainage GIS records, SCS Curve Number runoff partitioning, and street routing graphs into an exploratory interface.

### Intended Use
* Comparative physical screening of relative topographic depressions and sluggish runoff zones.
* Educational visualization of drainage connectivity and theoretical hydraulic conduit conveyance.
* Prototype exploration of multi-criteria routing under simulated ponding conditions.

### Out of Scope & Prohibited Uses
* **NOT AN OFFICIAL FLOOD WARNING SYSTEM.**
* **NOT CERTIFIED FOR LIFE-SAFETY EVACUATION OR EMERGENCY OPERATIONS.**
* Cannot be extrapolated citywide outside the $0.97\,\text{km}^2$ Downtown Houston pilot boundary.
* Must not be represented as a calibrated 1D/2D hydrodynamic model (e.g. SWMM, HEC-RAS, TUFLOW, InfoWorks).

---

## 2. Model Hierarchy & Components

### M1: Exploratory Waterlogging Susceptibility Index (EWSI)
* **Type:** Multi-criteria weighted physical screening model (100×100 grid cells, ~9.7m resolution).
* **Factors:**
  1. Topographic Depressions / Sinks (Weight: 35%) via morphological reconstruction.
  2. Topographic Position Index / Relative Elevation (Weight: 25%) via 30m radius annulus.
  3. Surface Slope Flatness (Weight: 20%) identifying sluggish slopes (<1.5°).
  4. Distance to Nearest Storm Inlet (Weight: 20%) via CRS-aware Euclidean metric distance.
* **Limitations:** Overpass bridges appear as solid terrain dams in raw LiDAR unless culverts are manually burned in. Proximity to inlet does not assess pipe conveyance capacity or inlet clogging.

### M5: Hydrological Screening Simulation
* **Type:** Mass-conserving physical screening ledger with SCS Curve Number ($CN=88$) runoff generation and 2D kinematic ponding diffusion.
* **Scenarios:** 5 synthetic rainfall presets (10mm, 25mm, 50mm, 75mm, 100mm over 180 minutes with peak intensity at minute 60).
* **Limitations:** Does not simulate pipe surcharging, backwater hydraulic heads, pressurized conduit flow, or bayou water level tidal fluctuations.

### M6: Drainage Network Capacity Screening
* **Type:** Steady-state gravity conduit capacity screening using Manning's equation ($Q = \frac{1}{n} A R^{2/3} S^{1/2}$).
* **Limitations:** 86.2% of municipal stormwater conduits have unrecorded slopes in public records; assumed minimum default slope of 0.20% is applied where unrecorded. Assumes clean pipes free of sediment or structural collapse.

### M7: Drainage-Informed Route Planner Engine
* **Type:** Multi-criteria Dijkstra network search comparing three profiles:
  1. *Baseline Shortest:* Pure street distance minimization.
  2. *Drainage-Informed:* Penalizes modeled flood depths, conduit loading ratio > 0.70, and data uncertainty.
  3. *Low-Susceptibility:* Penalizes baseline terrain EWSI susceptibility.
* **Limitations:** Street centerlines snapped from OpenStreetMap/GIS; does not incorporate real-time traffic closures or dynamic barricades.

### M8: 3D Terrain & Flood Visualization
* **Type:** Continuous 256×256 elevation heightmap mesh rendered via Three.js with configurable vertical exaggeration (1.0× to 10.0×).
* **Limitations:** Requires browser WebGL support; subtle vertical features require vertical exaggeration (default: 3.0×) to perceive due to flat Gulf Coast coastal topography.

### M9: ML Surrogate Model
* **Type:** `HistGradientBoostingRegressor` emulator trained strictly on M5 screening simulation outputs.
* **Feature Inputs:** Normalized longitude, latitude, DEM elevation, EWSI susceptibility tier, total rainfall, duration, elapsed time, rainfall intensity, and drainage rate.
* **M9 Full-Scenario Simulation Benchmark (Verified in Milestone M9):**
  - **Original Screening Model:** **1.448 ms** median per scenario.
  - **ML Surrogate Model:** **1,256.59 ms** median per scenario.
  - **Speed Ratio:** The ML surrogate pipeline is approximately **868× slower** than the original screening model due to tabular feature matrix construction, spatial transformations, and non-vectorized per-cell prediction overhead.
  - *(Note: This full-scenario benchmark was established and audited during Milestone M9 and was not re-run during M10 to preserve the frozen model state).*
* **Provenance & Scope:** The ML surrogate is a **SYNTHETIC SURROGATE** that emulates the unvalidated screening simulation. It does not introduce real-world physics, field observations, or external validation.

---

## 3. Performance & Benchmark Summary

### A. M10 Component Latency Measurements
Measured during Milestone M10 on Windows 11 AMD64 (Python 3.12.2) over the active pilot sector:

| Metric | Cold Start | Warm Mean | Warm Median | Warm p95 | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AOI / Data Loading (6 files, 4.71 MB)** | 105.24 ms | 125.69 ms | 121.43 ms | 149.57 ms | Cold unprimed vs 50 warm loads |
| **M5 Timestep Frame Retrieval** | 0.039 ms | 0.008 ms | 0.008 ms | 0.008 ms | In-memory frame dictionary lookup (NOT a full simulation run) |
| **M7 Route Alternatives Query** | 336.20 ms | 34.83 ms | 33.72 ms | 43.62 ms | 3 alternative paths via Dijkstra search |
| **Frontend Code Payload (Unvendored)** | — | — | — | **388.94 KB** | Application HTML/CSS/JS only |
| **Total Frontend Bundle (w/ Three.js)** | — | — | — | **1,004.00 KB** | Includes vendored 3D libraries |

### B. M9 Verified Full-Scenario Simulation Benchmark (Reference)
* **Original Physical Screening Model:** **1.448 ms** median
* **ML Surrogate Inference Pipeline:** **1,256.59 ms** median
* **Surrogate Latency Penalty:** ~**868× slower** than original screening model

---

## 4. Internationalisation & Static Export

* **Bangla (বাংলা):** Canonical `i18n/bn.json` dictionary provided. Scientific disclaimers (`SYNTHETIC SURROGATE`, `UNVALIDATED`, `MODELLED`, `ASSUMED`) are strictly preserved alongside translated terminology.
* **Static Export (`dist_static/`):** Generates standalone, zero-dependency distribution operable on any plain web server without Python.
