# Milestone 6 (M6) Drainage Data Audit & Network Readiness Report

**Project:** AquaPredict · Downtown Houston Pilot Domain (`0.97 km²`)  
**Study Area Bounding Box:** West `-95.3750°`, South `29.7560°`, East `-95.3650°`, North `29.7650°`  
**Datum & Projections:** Source Coordinates reprojected from EPSG:2278 (Texas South Central ftUS) to EPSG:4326 (WGS84)  
**Audit Date:** October 2026  

---

## 1. Verified Asset Counts & Completeness

| Asset Layer | File Name | Verified Count | Geometry Type | Identifier Field | Completeness |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gravity Mains** | `gravity_mains.geojson` | **624** | Polyline (LineString) | `FACILITYID` | 100% complete |
| **Inlets** | `inlets.geojson` | **265** | Point | `FACILITYID` | 100% complete |
| **Manholes** | `manholes.geojson` | **283** | Point | `FACILITYID` | 100% complete |
| **Outfalls** | `discharge.geojson` | **4** | Point | `FACILITYID` | 100% complete |
| **Total Nodes** | *Combined Node Registry* | **552** | Point | `FACILITYID` | 100% unique IDs |

---

## 2. Observed Source Attributes vs. Derived vs. Assumed Values

| Parameter / Attribute | Classification | Source / Determination Method | Known Limitations |
| :--- | :--- | :--- | :--- |
| **Node Coordinates** | **Observed Source** | Transformed from EPSG:2278 municipal feature layers | Accurate to $\pm 0.1\text{ ft}$ |
| **Pipe Diameter (`WIDTH`)** | **Observed Source** | Municipal GIS table (inches) | 97 conduits record `0.0 in`, 7 unrecorded/null (104 total) |
| **Pipe Length** | **Observed Source** | `SHAPE.STLength()` in survey feet | 100% complete |
| **Invert Elevations** | **Observed Source** | `UPELEV` and `DOWNELEV` (ft NAVD88) | 58 pipes have `DOWNELEV == 0.0` (unrecorded datum) |
| **Explicit Slope (`SLOPE`)** | **Observed Source** | Municipal GIS table (percent slope) | Only 86 pipes (13.8%) have explicit slopes recorded |
| **Derived Slope ($S_0$)** | **Derived Value** | $S_0 = (UPELEV - DOWNELEV) / L$ | 181 pipes show adverse or zero slope ($S_0 \le 0$) |
| **Manning's Roughness ($n$)** | **Observed / Assumed** | Material map (RCP: 0.013, CMP: 0.024, PVC: 0.010); assumed $0.013$ for nulls | 268 unrecorded materials use illustrative $0.013$ |
| **Conduit Capacity ($Q_{full}$)** | **Derived Value** | Manning's formula for circular full pipe gravity conveyance | Only calculable for 264 pipes ($S_0 > 0, D > 0$) |
| **Connectivity Type** | **Derived & Inferred** | Cross-referenced `UPSTMNODE` / `DOWNSTMNODE` and $1.0\text{m}$ snap distance | Disconnected / boundary exit pipes identified |

---

## 3. Network Connectivity & Graph Topology

### Connectivity Classification Breakdown
- **Source-Confirmed Conduits:** **391** (62.7%)  
  *Both upstream and downstream node identifiers match registered inlets, manholes, or outfalls.*
- **Partially Snapped Conduits:** **74** (11.9%)  
  *One endpoint matched by source attribute; opposite endpoint snapped within $1.0\text{m}$ tolerance.*
- **Inferred Snapped Conduits:** **14** (2.2%)  
  *Both endpoints snapped geometrically within $1.0\text{m}$ snapping tolerance.*
- **Dangling / Boundary Conduits:** **145** (23.2%)  
  *Conduits whose endpoints cross the pilot bounding box or terminate without connecting to a mapped node.*

### DISCONNECTED State Definition & Engineering Guardrail
> [!IMPORTANT]
> **DISCONNECTED State Meaning:** Conduits flagged with state `DISCONNECTED` represent **unresolved mapped connectivity** (conduits crossing boundary streets into surrounding Houston drainage sectors without a mapped downstream terminal in this extract).  
> **This does NOT signify confirmed physical drainage failure, structural collapse, or sediment blockage.** It indicates that downstream hydraulic boundary conditions cannot be resolved from this local pilot extract alone.

### Connected Components & Outfall Reachability
- **Total Connected Sub-Networks:** 79 distinct graph components.
- **Buffalo Bayou Outfall Branches:** 108 conduits and 84 nodes trace directly into the 4 Buffalo Bayou Outfall terminals.
- **Pilot Boundary Exits:** 516 conduits convey stormwater toward regional trunk lines that exit the $0.97\text{ km²}$ pilot polygon southward or eastward.

---

## 4. Hydraulic Capacity Audit (M6-C)

### Manning's Equation Formulation
$$Q_{full} = \frac{1.486}{n} A R_h^{2/3} S_0^{1/2} \quad (\text{cfs})$$
$$Q_{full, m^3/s} = Q_{cfs} \times 0.0283168$$

### Mutually Exclusive Primary Data-Quality Classification (624 Conduits)
Every conduit is classified using exactly one mutually exclusive primary quality reason:

| Mutually Exclusive Primary Category | Conduit Count | Share (%) | Engineering Criterion |
| :--- | :---: | :---: | :--- |
| **`CALCULATED_RECORDED_MATERIAL`** | **186** | **29.8%** | Valid diameter ($D > 0$), positive slope ($S_0 > 0$), confirmed municipal material code. |
| **`CALCULATED_ASSUMED_ROUGHNESS`** | **78** | **12.5%** | Valid diameter ($D > 0$), positive slope ($S_0 > 0$), unrecorded material defaulting to $n = 0.013$. |
| **`ADVERSE_OR_ZERO_SLOPE`** | **181** | **29.0%** | Non-positive slope ($S_0 \le 0$) in digitized record (157 adverse, 24 flat). Gravity flow invalid. |
| **`MISSING_SLOPE_AND_INVERTS`** | **75** | **12.0%** | Valid diameter, but unrecorded slope and incomplete inverts (including 58 placeholder zero inverts). |
| **`MISSING_OR_ZERO_DIAMETER`** | **104** | **16.7%** | Missing or zero diameter ($D \le 0$ or null). Cross-sectional area cannot be evaluated. |
| **TOTAL** | **624** | **100.0%** | **Mutually exclusive partition of all 624 gravity mains.** |

Summary:
- **Calculable Capacity:** **264 conduits (42.3%)**
- **Explicitly UNAVAILABLE Capacity:** **360 conduits (57.7%)**

> [!IMPORTANT]
> **Zero/Negative Capacity Handling:** Conduits with `None`, zero, or negative capacity are strictly classified as `INSUFFICIENT_DATA` (or `DISCONNECTED`) during dynamic simulation loading and **never silently produce `NORMAL` status**.

---

## 5. Non-Duplication of Drainage Inflows & Volumes (M6-D)

1. **Surface Runoff Introduction:** Surface runoff is introduced into the subsurface pipe network strictly at the **265 mapped Inlets** ($A_{inlet} = 970,000\text{ m²} / 265 \approx 3,660.4\text{ m²}$ per inlet).
2. **Topological Conveyance:** Conduits convey flow downstream along the directed DAG graph. Conduits carry only the inflow conveyed from contributing upstream inlets.
3. **No Catchment Invention:** Intermediate manholes and buried conduit segments do not generate independent surface runoff.
4. **Zero Double-Counting:** M5's 5% aggregate drawdown model ($V_{drain} = 0.05 \cdot V_{available}$ per 5-minute timestep) is strictly preserved as the master domain water ledger. Conduit capacity evaluations operate as **asset-level hydraulic stress indicators** without modifying the global mass balance.
