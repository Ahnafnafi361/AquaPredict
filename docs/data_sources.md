# AquaPredict Data Sources & Provenance Audit

**Milestone:** M10 Hardening & Static Export  
**Study Area:** Downtown Houston / Buffalo Bayou Pilot Sector  
**Geographic Bounds (WGS84):** West: `-95.3750°`, South: `29.7560°`, East: `-95.3650°`, North: `29.7650°` (~$0.97\,\text{km}^2$)  

---

## 1. Topographic Elevation Data (DEM)

| Property | Value |
| :--- | :--- |
| **Dataset Name** | NOAA 2018 Coastal Texas StratMap18 LiDAR Bare Earth DEM |
| **Source Agency** | National Oceanic and Atmospheric Administration (NOAA) / TNRIS |
| **Native CRS** | EPSG:6344 (NAD83 2011 / Texas South Central (ftUS)) |
| **Projected CRS** | EPSG:4326 (WGS84 Geographic Coordinates) |
| **Spatial Resolution** | 1.0 meter horizontal grid cell size |
| **Pilot Coverage** | 100% complete within bounding box (0 missing or nodata pixels) |
| **Elevation Range** | Min: -0.17 m (Buffalo Bayou bed), Max: 17.84 m (Southwest ridge terrace) |
| **Mean Elevation** | 12.01 m |
| **Known Artifacts** | Elevated transportation overpasses (I-45, Gulf Freeway) appear as solid ground dams without culvert bridge cutting. |

---

## 2. Municipal Stormwater Drainage Network Assets

| Asset Layer | Source Record | Feature Count | Attribute Completeness & Quality Notes |
| :--- | :--- | :--- | :--- |
| **Gravity Mains (Pipes)** | City of Houston GIS Open Data | 624 conduits | **Diameter:** 94.6% recorded (mean 24.8 in).<br>**Slope:** 86.2% unrecorded in municipal records; assumed 0.20% default where missing.<br>**Material:** 82.4% Reinforced Concrete Pipe (RCP).<br>**Flow Direction:** 0.0% recorded; inferred via invert elevations and topology. |
| **Storm Inlets** | City of Houston GIS Open Data | 265 intake nodes | Curb and grate intake nodes. 78.4% recorded rim elevations. |
| **Manholes** | City of Houston GIS Open Data | 283 junctions | Access inspection junctions. Rim and invert elevations recorded where available. |
| **Discharge Outfalls** | City of Houston GIS Open Data | 4 terminal points | Direct outfall terminals discharging into Buffalo Bayou channel. |

---

## 3. Rainfall Gauge Observations

| Property | Value |
| :--- | :--- |
| **Monitoring Network** | Harris County Flood Warning System (HCFWS) |
| **Gauge Station** | Station 1600 (Buffalo Bayou at Milam Street, Lat: `29.7642°`, Lon: `-95.3653°`) |
| **Temporal Resolution** | Sub-hourly (15-minute intervals) |
| **Operational Status** | **UNVERIFIED / EXPLORATORY**; live operational feed is uncalibrated. Uniform spatial assumption applied across 0.97 km² pilot sector for prototype demonstration. |

---

## 4. Street Network Centerlines

| Property | Value |
| :--- | :--- |
| **Source** | OpenStreetMap (OSM) Centerline Extract |
| **Feature Count** | 200 street segments (210 routable directed edges) |
| **Nodes** | 71 unique topological intersection junctions |
| **One-Way Rules** | Encoded via OSM `oneway` tags; enforced strictly in vehicle routing mode (`TF` and `FT` flags). |

---

## 5. Summary of Known Data Gaps & Validation Limitations

1. **Absence of Real-World Flood Validation Ground Truth:**
   There are no high-water marks, USGS calibrated stream gauge rating curves, or street-level flood depth sensor observations tied to specific historical events within the pilot sector. All model outputs are strictly **UNVALIDATED**.
2. **Missing Hydraulic Invert Data:**
   Over 86% of storm conduits lack measured longitudinal bed slopes. Hydraulic capacity values calculated via Manning's formula are screening estimates.
3. **No Dynamic Surface-Subsurface Coupling:**
   Underground pipe surcharging, surface street runoff spillback, and backwater from high bayou stage are uncoupled.
