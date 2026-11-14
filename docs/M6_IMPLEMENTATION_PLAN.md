# Milestone 6 (M6) Implementation Plan
## Drainage Network, Connectivity and Hydraulic Capacity

### 1. Scope & Preservation Directives
- **Location:** Strictly preserved Downtown Houston / Buffalo Bayou pilot boundary (`0.97 km²`).
- **Preserved Functionality:** All M0–M5 components (Leaflet map, DEM layers, susceptibility tiers, M2 rainfall pipeline, M3 validation audit, M4 bivariate synthesis, M5 simulation engine with 5 presets, timeline playback, 6-field status bar, and modal panels).
- **Architecture:** Incremental data generation script (`scripts/build_drainage_network.py`), metadata assets, comprehensive test suite (`scripts/test_m6_drainage.py`), and non-disruptive frontend integration in `public/js/app.js`, `public/index.html`, and `public/css/style.css`.

---

### 2. Execution Phases

#### Phase 1: M6-A Drainage Data Audit
- Inspect all 4 municipal GIS datasets (`gravity_mains.geojson`, `inlets.geojson`, `manholes.geojson`, `discharge.geojson`).
- Classify observed source attributes vs. derived values vs. assumed parameters vs. missing values.
- Document geometry, CRS, dimensions, invert elevations, slopes, and connectivity gaps.
- Publish `docs/M6_DRAINAGE_DATA_AUDIT.md`.

#### Phase 2: M6-B Drainage Network Graph Engine
- Build `scripts/build_drainage_network.py`:
  - Nodes: 552 features ($265$ Inlets, $283$ Manholes, $4$ Bayou Outfalls).
  - Conduits: 624 Gravity Mains.
  - Connectivity Classification: `source_confirmed` (matches `UPSTMNODE` & `DOWNSTMNODE`), `inferred_snapped` ($\le 1.0\text{ m}$ tolerance), and `dangling_boundary`.
  - Graph Topology: Forward adjacency (downstream) and reverse adjacency (upstream), connected components, and outfall reachability.
  - Export structured dataset: `public/data/m6_drainage_network.json` and `public/data/m6_analysis_meta.json`.

#### Phase 3: M6-C Provisional Hydraulic Capacity Model
- Implement Manning's equation for circular full pipe gravity conveyance:
  $$Q_{\text{full}} = \frac{1.486}{n} A R_h^{2/3} S_0^{1/2} \quad (\text{cfs}), \quad Q_{\text{m}^3/\text{s}} = Q_{\text{cfs}} \times 0.0283168$$
- Source slope priority: explicit positive `SLOPE` ($86$ pipes) or derived positive invert slope $(UPELEV - DOWNELEV)/L$ ($178$ pipes).
- Explicit `UNAVAILABLE` classification for 360 pipes with adverse slopes ($S_0 \le 0$), zero datums, or missing diameters (never fabricate capacities).
- Roughness $n$: observed material-based ($0.013$ for RCP/CP, $0.024$ for CMP, $0.015$ for BR, $0.010$ for PVC) and illustrative default $0.013$ for unrecorded.

#### Phase 4: M6-D Dynamic Drainage Status & Timeline Integration
- Define asset states: `Normal`, `High Loading` ($70\text{--}100\%$), `Capacity Exceeded` ($>100\%$), `Disconnected`, `Insufficient Data`.
- Evaluate time-indexed dynamic flow loading during M5 simulation playback.
- Maintain M5 5% aggregate drawdown as global water ledger; label conduit states as localized hydraulic stress screening without double-counting.

#### Phase 5: M6-E UI Extensions, Network Tracing & Inspector Card
- **Asset Inspector:** Add interactive **Trace Upstream** and **Trace Downstream** buttons with visual path highlighting on the Leaflet map.
- **Drainage Analysis Modal / Drawer Tab:** Provide detailed connectivity counts, capacity breakdowns, and outfall reachability metrics.
- **Hotspot Ranking:** Cluster top conceptual model hotspots combining deep M5 ponding and throttled/disconnected drainage assets.
- **Six-Field Status Bar:** Dynamically update `Surcharged Nodes` and `Overloaded Drains` during simulation timeline.
- **Workflow Drawer:** Update Step 5 (Drainage) and Step 7 (Hotspots) from `UNAVAILABLE` to `COMPLETED` ($7/7$ Complete).

#### Phase 6: Comprehensive Testing & Verification
- Implement `scripts/test_m6_drainage.py` with 15+ rigorous unit tests.
- Run all M0–M5 regression suites (`test_m5_simulation.py`, `test_rainfall_ingestion.py`, `test_m3_validation.py`, `test_m4_synthesis.py`, `test_all_endpoints.py`).
- Run CDP browser verification script to confirm interactive tracing and UI readouts.
