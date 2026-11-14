# AquaPredict — Milestone 3 (M3) Historical Flood Validation Readiness Report

**Project:** AquaPredict — Urban Waterlogging Risk Visualization Prototype  
**Milestone:** M3 (Historical Flood Validation Readiness)  
**Study Area:** Downtown Houston / Buffalo Bayou Pilot Sector, Harris County, Texas  
**Pilot Boundary Bounding Box:** `[-95.3750° W, 29.7560° N]` to `[-95.3650° W, 29.7650° N]`  
**Pilot Surface Area:** 0.97 km² (240 acres)  
**Date of Assessment:** October 2026  
**Final Validation Decision:** **VALIDATION DATA UNAVAILABLE**  

---

## 1. Executive Summary

Milestone 3 (M3) investigates whether the exploratory waterlogging susceptibility results developed in Milestone 1 (M1)—computed via the Exploratory Waterlogging Susceptibility Index (EWSI)—can be independently evaluated against reliable historical flood or street-waterlogging observations within the existing Downtown Houston pilot boundary.

Following a comprehensive audit of the local project repository (`C:\AquaPredict_tests`), City of Houston open enterprise GIS services, USGS hydrological networks, Houston TranStar highway systems, and FEMA regulatory flood hazard layers, this report determines that **suitable empirical ground-truth observations of urban street waterlogging do NOT exist within the pilot boundary**.

In strict adherence to the project's scientific integrity rules:
1. **Zero Data Fabrication:** No synthetic flood events, synthetic inundation polygons, or artificial benchmark metrics (e.g. ROC/AUC curves, precision-recall scores, or confusion matrices) were generated.
2. **Model Integrity Preserved:** M1 indicator weights (35% Depressions, 25% TPI, 20% Slope Flatness, 20% Storm Inlet Proximity) and susceptibility scores were kept 100% untouched.
3. **Pilot Scope Maintained:** The boundary was not shifted or expanded to cherry-pick external stream gauge data.
4. **Transparent Communication:** AquaPredict explicitly disclaims flood prediction capabilities and documents the exact missing empirical evidence required before validation can be achieved.

---

## 2. Pilot Boundary & Geographic Context

The study area encompasses a 0.97 km² urban quadrant in Downtown Houston, bounded as follows:

| Boundary Edge | Coordinate | Geographic Reference |
| :--- | :--- | :--- |
| **West Bound** | `-95.3750° W` | Heiner Street / Gulf Freeway (I-45) eastern transition |
| **South Bound** | `29.7560° N` | Clay Street / Bell Street corridor |
| **East Bound** | `-95.3650° W` | Milam Street / Travis Street corridor |
| **North Bound** | `29.7650° N` | Buffalo Bayou northern bank / Franklin Street |

```
                       29.7650° N (Buffalo Bayou / Franklin St)
          +-------------------------------------------------------+
          | [HCFWS Stn 1600: Milam St]                            |
          | ~~~~~~~~~~ Buffalo Bayou Channel ~~~~~~~~~~~~~~~~~~~ |
          |                                                       |
          |   Downtown Commercial & Civic Center                  |
          |   * Houston City Hall (901 Bagby St)                  |
          |     [29.75837° N, -95.36984° W]                       |
          |     (Site of extreme 311 geocoding clustering)        |
          |                                                       |
          |   1,176 Stormwater Assets:                            |
          |     624 Gravity Mains | 265 Inlets                    |
          |     283 Manholes      | 4 Outfalls                    |
          +-------------------------------------------------------+
-95.3750° W                                             -95.3650° W
(I-45 Edge)            29.7560° N (Clay / Bell St)
```

The pilot contains high-density commercial skyscrapers, municipal administrative structures (including Houston City Hall at 901 Bagby St), paved street grids, and the steep embankment of the Buffalo Bayou riverine channel along its northern margin.

---

## 3. Candidate Source Inventory & Provenance

Five authoritative candidate sources for historical flood data, high water marks, incident logs, and floodplains were identified and rigorously evaluated against empirical validation criteria:

| Source ID | Candidate Dataset | Authoritative Agency & Provenance | Access Method & Schema | Spatial Precision & Coverage | Evaluation Finding |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SRC-01** | **USGS Short-Term Network (STN) High Water Marks (HWMs)** | USGS Office of Water Information (OWI) / Flood Event Viewer | USGS STN Web Services / REST API (`stn.wim.usgs.gov`) | Sub-meter survey elevation; point marks along Buffalo Bayou banks (Milam St Bridge). 0 street marks. | **DISQUALIFIED (PHYSICAL MISMATCH)**: Measures riverine channel flood crests, not street overland ponding. |
| **SRC-02** | **City of Houston 311 Citizen Service Requests** | City of Houston Public Works / HITS | Houston Open Data Portal & ArcGIS REST (`geogimsms.houstontx.gov`) | Varies from street address to default administrative centroids. Severe City Hall clustering. | **DISQUALIFIED (UNRELIABLE & BIASED)**: Citizen perception logs lacking physical depth, duration, or validated footprints. |
| **SRC-03** | **Houston TranStar Roadway High Water Feeds** | TranStar Consortium (TxDOT, City, County, METRO) | Houston TranStar Incident Feeds & Map System | Point/segment status for state highways and freeway underpasses (I-45, Memorial Dr). 0 local streets. | **DISQUALIFIED (SPATIAL COVERAGE DEFICIT)**: Covers highway mainlanes; zero monitoring of downtown surface streets. |
| **SRC-04** | **Harris County Flood Warning System (HCFWS) Stream Stage** | Harris County Flood Control District (HCFCD) | HCFWS Automated Sensor Network & API (`harriscountyfws.org`) | Continuous 15-min riverine stream stage at Station 1600 (Buffalo Bayou @ Milam St). | **DISQUALIFIED (CHANNEL vs SURFACE)**: Measures 500+ sq mi river basin stage; 0 overland street surface sensors. |
| **SRC-05** | **FEMA National Flood Hazard Layer (NFHL) / FIRMs** | Federal Emergency Management Agency (FEMA) / NFIP | FEMA NFHL ArcGIS REST Services (Panel 48201C0670M) | Regional 100-yr (Zone AE) and 500-yr (Zone X Shaded) riverine floodplains. | **DISQUALIFIED (MODEL OUTPUT)**: Regulatory steady-state hydraulic model (HEC-RAS), not an empirical flood observation. |

---

## 4. In-Depth Scientific Distinctions & Disqualification Rationale

### 4.1 Pluvial (Urban Surface Ponding) vs. Fluvial (Riverine Overbank) Flood Regimes

* **M1 EWSI Model Scope:** M1 evaluates **pluvial waterlogging susceptibility**—the tendency of rainwater to accumulate on urban street surfaces due to micro-topographical depressions, low terrain gradients (< 1.5°), and overland flow distance to storm inlets. Pluvial flooding is governed by cloudburst precipitation intensity, surface roughness, and street curb geometry.
* **USGS & HCFWS Fluvial Data:** Physical high-water marks and stream gauges along Buffalo Bayou measure **fluvial overbank flooding**—where regional runoff from a 500+ square mile upstream watershed exceeds the channel banks. During Hurricane Harvey (August 2017), the bayou reached an elevation of ~11.8 m NAVD88 at Milam Street.
* **The Incompatibility:** A localized street depression located at 15 m elevation that ponds 10 cm of water due to clogged inlet grates would be completely unrecorded by bayou water levels. Conversely, riverine backwater that submerges low-elevation outfalls does not validate whether the street-level slope index correctly identifies ponding. Conflating riverine stages with street overland drainage invalidates scientific verification.

### 4.2 Citizen Complaints (311) vs. Physical Ground-Truth Measurements

* **Lack of Physical Metrics:** 311 calls ("Flooded Street Hazard", "Clogged Catch Basin") record human frustration, not physical flood metrics. They contain no measured water depth, no duration, no flow velocity, and no surveyed geometric boundary.
* **Severe Geocoding Clustering Artifact:** Houston's open data infrastructure defaults unlocated telephone calls, city-wide administrative inquiries, and general correspondence to **Houston City Hall (`901 Bagby St`, `29.75837° N, -95.36984° W`)**. In the active 311 service request layer, over 1,500 non-flood inquiries were clustered at City Hall—which sits squarely within our pilot boundary. Using 311 points as "ground truth" would evaluate the presence of municipal government buildings rather than stormwater physics.
* **Temporal Disconnect:** Service requests are typically submitted hours or days after rain ceases, providing zero synchronization with peak rainfall hyetographs.

### 4.3 Regulatory Hydraulic Models (FEMA FIRMs) vs. Empirical Observations

* FEMA 100-year base flood elevations (BFEs) and Special Flood Hazard Areas (Zone AE) are derived from numerical 1D/2D hydraulic models (such as HEC-RAS) driven by synthetic 24-hour design storms.
* Comparing an exploratory terrain screening index against a regulatory hydraulic model is a **model-to-model cross-comparison**, not an empirical validation against historical reality. Claiming validation based on FEMA maps would be scientifically misleading.

---

## 5. Local Data Inventory Audit (`C:\AquaPredict_tests`)

A recursive audit of the project data directory confirmed:

| Data Category | Files Present | Records / Assets | Validation Utility |
| :--- | :--- | :--- | :--- |
| **Storm Infrastructure** | `feat_GravityMains.json`, `feat_Inlets.json`, `feat_Manholes.json`, `feat_Discharge.json` | 624 mains, 265 inlets, 283 manholes, 4 outfalls | Structural input for M0/M1; not ground truth. |
| **LiDAR DEM** | `stratmap18-1m_2995134d4.tif`, `stratmap18-1m_2995143c3.tif` | 1-meter bare earth grid (100% pilot coverage) | Topographical input for M0/M1; not ground truth. |
| **Completeness CSVs** | `completeness_*.csv`, `fields_*.csv` | Attribute audit logs | Quality metadata; not ground truth. |
| **Rainfall Folder** | `rainfall/` | 0 files | Ingestion directory; no rainfall or flood data. |
| **Historical Flood Observations** | **NONE** | **0 records** | **Ground truth completely absent from local data.** |

---

## 6. Audit of M1 Model Weights and Integrity

Project rules strictly dictate that M1 weights and susceptibility scores must not be altered during validation readiness assessment:

$$\text{EWSI} = 0.35 \times I_{\text{dep}} + 0.25 \times I_{\text{tpi}} + 0.20 \times I_{\text{slope}} + 0.20 \times I_{\text{inlet}}$$

* **Terrain Depressions ($I_{\text{dep}}$):** Weight = **0.35** (Max sink depth: 6.15 m, Sink area: 8.8%) — **VERIFIED UNCHANGED**
* **Topographic Position Index ($I_{\text{tpi}}$):** Weight = **0.25** (30m moving neighborhood) — **VERIFIED UNCHANGED**
* **Slope Flatness ($I_{\text{slope}}$):** Weight = **0.20** (Slopes < 1.5° = 46.0%) — **VERIFIED UNCHANGED**
* **Drainage Inlet Proximity ($I_{\text{inlet}}$):** Weight = **0.20** (Mean distance = 54.7 m, 265 inlets) — **VERIFIED UNCHANGED**
* **Susceptibility Grid (`susceptibility_grid.json`):** 1,088,212 bytes — **VERIFIED INTACT**

---

## 7. Explicit Decision: VALIDATION DATA UNAVAILABLE

Because no suitable, reliable, and geographically precise pluvial waterlogging observations exist within the 0.97 km² Downtown Houston pilot boundary, AquaPredict officially records:

> ### **DECISION: VALIDATION DATA UNAVAILABLE**
> **Quantitative baseline validation (ROC/AUC, F1-score, Precision/Recall, Brier Score) cannot be calculated.**  
> Fabricating synthetic flood events or calculating metrics against mismatched riverine or complaint data is rejected as scientifically invalid.

---

## 8. Missing Evidence Required for Future Validation

To transition AquaPredict from an exploratory screening prototype to an independently validated prediction system, the following four empirical datasets must be acquired:

1. **Calibrated Street-Level Water Depth Sensors (IoT Network):**
   * High-frequency ultrasonic or pressure transducer sensors installed in street gutters, catch basins, or curb inlets logging continuous water depths (cm/inches) during storm events.
2. **High-Resolution Orthorectified Inundation Polygons:**
   * Airborne optical photography, drone survey mosaics, or high-resolution synthetic aperture radar (SAR) captured at peak rainfall, delineating exact surface ponding boundaries on the Downtown street grid.
3. **Event-Synchronized Time-Series Records:**
   * Timestamped waterlogging onset, peak, and drainage recession logs synchronized with sub-hourly rainfall observations (e.g. HCFWS Station 1600).
4. **Storm Drain Operational State Records:**
   * Field inspection logs recording inlet grate debris clogging percentages and bayou outfall flap gate submergence during rainfall.

---

## 9. Next Steps & Guardrails for Milestone 4 (M4)

1. **Maintain Transparent User Communication:** The UI and documentation must consistently describe M1 as an *Exploratory Waterlogging Susceptibility Index (EWSI)* and not a calibrated flood prediction model.
2. **Standardized Evaluation Harness:** When verified street sensor or surveyed flood polygon data become available, feed them into an automated validation pipeline to compute ROC/AUC curves without adjusting indicator weights in advance.
3. **M4 Preparation:** When integrating dynamic rainfall with terrain susceptibility in M4, present the output as a *meteorological-topographic risk index* rather than certified flood depths.
