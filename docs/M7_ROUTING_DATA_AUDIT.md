# Milestone 7 (M7) Routing Data Audit & Network Readiness Report

**Project:** AquaPredict · Downtown Houston Pilot Domain (`0.97 km²`)  
**Study Area Bounding Box:** West `-95.3750°`, South `29.7560°`, East `-95.3650°`, North `29.7650°`  
**Datum & Projections:** Source Coordinates reprojected from EPSG:2278 (Texas South Central ftUS) to EPSG:4326 (WGS84)  
**Audit Date:** October 2026  

---

## 1. Executive Summary & Data Availability Audit

| Network Source | Availability Status | Feature Count | Geometry Type | Routing Suitability | Notes & Limitations |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Local M0–M6 Extracted Data** | **NO Surface Roads** | 0 | None | **UNSUITABLE** | Only underground stormwater gravity mains (624 conduits) were present in the initial offline extract. Subsurface sewer pipes cannot be traversed by pedestrians or vehicles. |
| **OpenStreetMap (Overpass API)** | **UNAVAILABLE** | 0 | None | **UNSUITABLE** | Overpass API endpoints (`overpass-api.de`, `kumi.systems`, `mail.ru`) timed out and failed SSL certificate validation in the local test environment. |
| **City of Houston Enterprise GIS (`DIR/LandbaseandRoads_gx/9`)** | **VERIFIED & AUDITED** | **200** | Polyline (LineString) | **SUITABLE** | Official municipal street centerlines with road classifications, lengths, and one-way directionality. |

---

## 2. Network Topology & Graph Connectivity

### Graph Topology Metrics (Houston Municipal Street Centerlines)
* **Total Street Segments:** 200 polyline features.
* **Total Network Length:** $93,697.7\text{ ft}$ ($28.56\text{ km}$).
* **Unique Named Streets:** 51 named thoroughfares (including Bagby St, Louisiana St, Milam St, Travis St, Capitol St, Lamar St, McKinney St, Dallas St, Franklin St, Memorial Dr, Allen Pkwy).
* **Intersection Nodes (3.0 m snap tolerance):** 160 distinct topology vertices.
* **Connected Components:** **1 single connected component (100.0% connectivity)**. Every node in the network is reachable.
* **Directionality Breakdown:**
  * One-Way From-To (`FT`): **100 segments (50.0%)**
  * One-Way To-From (`TF`): **69 segments (34.5%)**
  * Bidirectional (`BI` or ` `): **31 segments (15.5%)**
* **Road Classifications:**
  * Local Streets (`LOCAL`): 111 segments (55.5%)
  * Major Thoroughfares (`MAJOR`): 51 segments (25.5%)
  * Freeway Ramps (`RAMP`): 28 segments (14.0%)
  * Highway Segments (`HIGHWAY`): 10 segments (5.0%)

---

## 3. Spatial Association with Terrain & Drainage Assets

### A. Terrain Susceptibility (M1 EWSI Grid)
* **Association Method:** Route segments are densified and sampled at approximately $10\text{ m}$ intervals along polyline geometry (preserving input vertices and endpoints, with zero duplicate consecutive samples). Intermediate points are interpolated in EPSG:4326 using symmetric round-half-up rounding for bit-level client/server numerical parity.
* **Coordinate Mapping:** Each sample point $(lon, lat)$ maps to the M1 $100 \times 100$ grid cell $(row, col)$:
  $$col = \left\lfloor \frac{lon - west}{east - west} \times 100 \right\rfloor, \quad row = \left\lfloor \frac{north - lat}{north - south} \times 100 \right\rfloor$$
* **Sampled Attributes & Proxy Mapping:** M1 grid cells provide discrete susceptibility tiers (`Low`, `Moderate`, `Elevated`, `High`). In `_sample_susc_profile`, tiers are mapped via canonical proxy weights: `Low: 0.15`, `Moderate: 0.45`, `Elevated: 0.70`, `High: 0.90` (outside grid defaults to 0.35).
* **Segment Summary:** Arithmetic mean susceptibility proxy score and maximum sampled score across all densified points along the edge.

### B. Modelled Ponding Depth (M5 Scenario Simulation)
* **Association Method:** Evaluated for the selected rainfall preset (10, 25, 50, 75, or 100 mm) and selected timestep (minute 0 to 180) sampled at approximately $10\text{ m}$ intervals along the edge polyline.
* **Depth Lookup:** Queried against M5 `simulation_scenarios.json` sparse depth arrays at each sampled grid cell ($flatIdx = row \times 100 + col$). Empty sparse depth arrays (`[]`) legitimately encode dry conditions ($0.0\text{ m}$). Missing or null depth scenario arrays are strictly flagged `UNAVAILABLE` and penalized with uncertainty ($P_{uncert} = +80.0\text{ m}$).
* **Segment Summary:** Maximum modelled depth ($d_{max}$), mean depth ($d_{mean}$), and length of segment submerged in water ($d > 0.05\text{ m}$).
* **Scientific Classification:** Explicitly labeled as **Uncalibrated Model Output**.

### C. Subsurface Drainage Loading (M6 Capacity Screening)
* **Association Method:** 25-meter spatial midpoint buffer corridor matching street centerline segments to nearby M6 gravity mains.
* **Drainage Metrics:** Intersects $m6\_drainage\_network.json$ gravity mains to identify adjacent conduits with `EXCEEDED` capacity ($Q_{inflow} > Q_{cap}$) or `HIGH` capacity ($0.70 \le Q/Q_{cap} \le 1.0$).
* **Screening Role:** Supplementary asset-level surcharge indicator. Does **not** signify confirmed surface road closure.

---

## 4. Missing Inputs, Uncertainties & Engineering Guardrails

1. **Pedestrian Sidewalk Completeness:** Sidewalk centerlines and mid-block crossings are not fully attributed with curb ramps, ADA accessibility ratings, or tactile paving in raw municipal street centerlines.
2. **Elevated Structures (Viaducts vs. Sinks):** Highway overpasses (e.g. Pierce Elevated / I-45) and elevated ramps appear as solid terrain features in raw bare-earth LiDAR. Modelled ponding in the depressed highway trench below must not be conflated with the elevated deck surface.
3. **Speed & Travel Time Assumptions:**
   * Pedestrian walking speed: Assumed AASHTO default of $1.34\text{ m/s}$ ($4.8\text{ km/h} \approx 3.0\text{ mph}$).
   * Vehicular travel time: Uses municipal speed limits (default $30\text{ mph}$ for local streets, $40\text{ mph}$ for Allen Pkwy) where recorded.
4. **Data Uncertainty Must Penalize, Not Excuse:** Missing hydraulic data or segments extending outside the pilot boundary are penalized with explicit uncertainty weights; missing data is **never** interpreted as evidence that a route is safe.
5. **No Certification of Safety:** Lower modelled route cost reflects relative physical screening only; it is **NOT a certified evacuation routing service or real-time flood advisory**.
