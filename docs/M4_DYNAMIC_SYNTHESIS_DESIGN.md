# AquaPredict — Milestone 4 (M4) Dynamic Rainfall–Susceptibility Synthesis Architecture & Design

**Project:** AquaPredict — Urban Waterlogging Risk Visualization Prototype  
**Milestone:** M4 (Dynamic Rainfall–Susceptibility Synthesis)  
**Study Area:** Downtown Houston / Buffalo Bayou Pilot Sector, Harris County, Texas  
**Pilot Coordinates:** `[-95.3750° W, 29.7560° N]` to `[-95.3650° W, 29.7650° N]` (`0.97 km²` / 240 acres)  
**Document Status:** Complete Architecture & Design Specification  

---

## 1. Objective & Scope

Milestone 4 (M4) establishes a scientifically transparent framework for presenting time-varying rainfall information alongside Milestone 1's static terrain-based waterlogging susceptibility (EWSI).

### Fundamental Principles:
1. **Preservation of M1:** M1 indicator weights (35% Depressions, 25% TPI, 20% Slope Flatness, 20% Storm Inlet Proximity), susceptibility scores, tier boundaries, and raster outputs are **100% unaltered**.
2. **Decoupled Dimensions:** Static terrain susceptibility (governed by topography and stormwater infrastructure layout) and dynamic meteorological intensity (governed by atmospheric precipitation) are maintained as separate physical dimensions.
3. **No Calibrated Flood Predictions:** The synthesis does **not** multiply susceptibility by rainfall to predict flood water depth, inundation volume, flood extent, or calibrated flood probability.
4. **Neutral Qualitative Categorization:** Matrix combinations use objective, neutral descriptions of joint occurrence without unverified claims of "drainage failure", "rapid evacuation", or "gutter flow velocities".
5. **Rigorous Data State Governance:** Clearly enforces four distinct system states: `UNAVAILABLE`, `UNVERIFIED DEMONSTRATION`, `VERIFIED`, and `INVALID`.

---

## 2. Two-Dimensional Decoupled Architecture

```
                  +----------------------------------------------+
                  |         DIMENSION 1: STATIC TERRAIN          |
                  |     Waterlogging Susceptibility (EWSI)       |
                  |  * 1m NOAA Bare-Earth LiDAR DEM (StratMap18) |
                  |  * 265 Verified Municipal Storm Inlets       |
                  |  * 4 Tiers: Low, Moderate, Elevated, High    |
                  |  * Stored in: susceptibility_grid.json       |
                  |    and susceptibility.png (800x800)          |
                  +----------------------+-----------------------+
                                         |
                                         | Joint Occurrence
                                         v
   +--------------------------------------------------------------------------+
   |          M4 QUALITATIVE BIVARIATE SCREENING STATE: S(r, c, t)            |
   |              Tuple: ( Susceptibility Tier, Rainfall Category )           |
   |                                                                          |
   |   * Screening Matrix identifies where high static sink tendencies       |
   |     coincide with active downpours.                                      |
   |   * Fully transparent: NO artificial water depth or probability number.  |
   +--------------------------------------------------------------------------+
                                         ^
                                         |
                  +----------------------+-----------------------+
                  |       DIMENSION 2: DYNAMIC PRECIPITATION     |
                  |          Rainfall Intensity & Hyetograph     |
                  |  * HCFWS Station 1600 (Buffalo Bayou @ Milam)|
                  |  * Sub-hourly 15-minute interval metrics     |
                  |  * Units: Native Inches (in) and Rate (in/hr)|
                  |  * 4 Provisional Display Categories:         |
                  |    Zero/Trace, Low, Moderate, Heavy          |
                  +----------------------------------------------+
```

---

## 3. Neutral Qualitative Bivariate Screening Matrix

The 4 static susceptibility tiers and 4 dynamic rainfall intensity categories form a 16-state bivariate screening matrix. Every category is described using neutral, factual terminology:

| Static Susceptibility Tier | Zero / Trace Rainfall ($0.00\text{ in/hr}$) | Low Intensity Rainfall ($0.00 < I < 0.40\text{ in/hr}$) | Moderate Intensity Rainfall ($0.40 \le I < 1.00\text{ in/hr}$) | Heavy Intensity Rainfall ($I \ge 1.00\text{ in/hr}$) |
| :--- | :--- | :--- | :--- | :--- |
| **High Susceptibility** ($\text{EWSI} \ge 0.70$) | **High Susceptibility · Dry / Trace Rainfall**<br>*(Quiescent topographically enclosed sink; no active rainfall influx)* | **High Susceptibility · Low Intensity Rainfall**<br>*(Topographical sink receiving light precipitation)* | **High Susceptibility · Moderate Intensity Rainfall**<br>*(Topographical sink receiving steady precipitation downpour)* | **High Susceptibility · Heavy Intensity Rainfall**<br>*(Topographical sink receiving heavy downpour; priority exploratory screening zone)* |
| **Elevated Susceptibility** ($0.50 \le \text{EWSI} < 0.70$) | **Elevated Susceptibility · Dry / Trace Rainfall**<br>*(Local swale or flat terrain; no active rainfall)* | **Elevated Susceptibility · Low Intensity Rainfall**<br>*(Local swale receiving light precipitation)* | **Elevated Susceptibility · Moderate Intensity Rainfall**<br>*(Local swale receiving steady precipitation)* | **Elevated Susceptibility · Heavy Intensity Rainfall**<br>*(Local swale receiving heavy downpour)* |
| **Moderate Susceptibility** ($0.30 \le \text{EWSI} < 0.50$) | **Moderate Susceptibility · Dry / Trace Rainfall**<br>*(Intermediate slope/terrace; no active rainfall)* | **Moderate Susceptibility · Low Intensity Rainfall**<br>*(Intermediate slope receiving light precipitation)* | **Moderate Susceptibility · Moderate Intensity Rainfall**<br>*(Intermediate slope receiving steady precipitation)* | **Moderate Susceptibility · Heavy Intensity Rainfall**<br>*(Intermediate slope receiving heavy downpour)* |
| **Low Susceptibility** ($\text{EWSI} < 0.30$) | **Low Susceptibility · Dry / Trace Rainfall**<br>*(Well-drained ridge or terrace; no active rainfall)* | **Low Susceptibility · Low Intensity Rainfall**<br>*(Well-drained ridge receiving light precipitation)* | **Low Susceptibility · Moderate Intensity Rainfall**<br>*(Well-drained ridge receiving steady precipitation)* | **Low Susceptibility · Heavy Intensity Rainfall**<br>*(Well-drained ridge receiving heavy downpour)* |

### Scientific Notes on Categorization:
- **No Inferred Hydraulic Capacities:** This matrix does not assume that storm drains "fail" at any specific intensity, nor does it assert that water "rapidly evacuates". It neutrally identifies joint occurrences.
- **Provisional Nature:** Intensity thresholds ($0.00$, $0.40$, $1.00\text{ in/hr}$) are provisional display intervals designed for exploratory visualization and comparison, not certified engineering failure criteria.

---

## 4. Mathematical Formulas, Units, and Semantics

### 4.1 Rainfall Intensity Formulation
For each discrete sub-hourly observation window from timestamp $t_{\text{from}}$ to $t_{\text{to}}$, with duration $\Delta t$ in minutes:

$$\Delta t_{\text{hr}} = \frac{\Delta t_{\text{min}}}{60.0}$$

$$\text{Calculated Intensity } I \;(\text{in/hr}) = \frac{r_{\text{in}}}{\Delta t_{\text{hr}}}$$

For standard 15-minute HCFWS gauge intervals ($\Delta t_{\text{min}} = 15$):

$$I \;(\text{in/hr}) = r_{\text{in}} \times \frac{60}{15} = r_{\text{in}} \times 4.0$$

Metric equivalent:

$$r_{\text{mm}} = r_{\text{in}} \times 25.4, \quad I_{\text{mm/hr}} = I_{\text{in/hr}} \times 25.4$$

### 4.2 Cumulative Event Accumulation
Cumulative precipitation $C(t_k)$ from the start of the observation record to index $k$:

$$C(t_k) = \sum_{j=0}^{k} r_{\text{in}}(j)$$

Missing intervals (`null` or unrecorded) are omitted from sums and flagged explicitly; they are never imputed with synthetic curves.

---

## 5. Spatial Uniformity Assumption & Physical Limitations

1. **Point-to-Grid Extrapolation Assumption:**
   - HCFWS Station 1600 is located at the northeastern boundary of the pilot area (`29.7642° N, -95.3653° W`).
   - The M4 demonstration couples this single point time series across the entire 0.97 km² study domain.
   - **Documented Caveat:** One point gauge does not establish spatially uniform rainfall. In Houston's subtropical maritime climate, convective summer deluges and cloudburst storm cells often exhibit steep spatial gradients over distances under 1 km.
2. **Exclusion of Subsurface Conduit Hydraulics:**
   - Proximity to storm inlets reflects surface travel distance only. The system does not simulate:
     - Inlet grate debris clogging percentages
     - Conduit flow velocity or Manning's roughness
     - Full-pipe pressurized surcharge
     - Buffalo Bayou riverine stage backwater locking flap gates at the 4 outfalls
3. **Exploratory Screening vs. Inundation Mapping:**
   - A cell classified as "High Susceptibility · Heavy Intensity" has a strong morphological sink tendency coincident with an intense downpour. However, without calibrated infiltration, overland flow routing, and subsurface capacity modeling, this joint state does **not** prove that standing water actually ponded to any specific depth.

---

## 6. The Four Data States

```
                +---------------------------------------+
                |     INPUT RAINFALL DATA EVALUATION    |
                +-------------------+-------------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
     [ Files Absent ]      [ Synthetic Fixture ]     [ Corrupt / Invalid ]
            |                       |                       |
            v                       v                       v
      UNAVAILABLE         UNVERIFIED DEMONSTRATION       INVALID
   * Dynamic synthesis    * Timeline slider active    * Synthesis halted
     disabled               (96 intervals)            * Corruption logged
   * Static M1 active     * PROMINENT WARNING BANNER  * Fallback to static
   * Diagnostic message     PERSISTENT IN UI            terrain view
                          * Not saved as real data
```

1. **`UNAVAILABLE` (Default Live State):**
   - Trigger: `C:\AquaPredict_tests\rainfall` contains 0 files.
   - UI Behavior: Header shows `RAINFALL: UNAVAILABLE`. Dynamic synthesis controls disabled. Static M1 terrain susceptibility displayed normally. Clear callout explains that real gauge files are awaiting placement.
2. **`UNVERIFIED DEMONSTRATION`:**
   - Trigger: User explicitly selects "Exploratory Fixture (Station 1600)".
   - UI Behavior: Header displays `RAINFALL: UNVERIFIED DEMONSTRATION`. Prominent warning banner permanently visible: **"SYNTHETIC DEMONSTRATION — NOT OBSERVED RAINFALL"**. Interactive timeline slider unlocked for all 96 intervals.
3. **`VERIFIED` (Future State):**
   - Trigger: Requires genuine sensor calibration logs and spatial verification.
   - UI Behavior: Displays station identifier, QA calibration date, and point-gauge spatial representativeness disclaimer.
4. **`INVALID`:**
   - Trigger: Gauge files contain negative values, timestamps out of sequence, or unphysical readings (> 15 in/interval).
   - UI Behavior: Synthesis engine safely halts; displays error diagnostics and falls back to static M1 terrain screening.

---

## 7. M3 Validation Readiness Continuity

AquaPredict maintains strict continuity with Milestone 3 findings:
- **Decision Maintained:** **VALIDATION DATA UNAVAILABLE** remains displayed in the header and the validation modal.
- **Independence:** The synthetic rainfall demonstration fixture is **never** used as ground-truth to validate M1 susceptibility scores.
- **Integrity:** Software functionality (an interactive timeline slider and bivariate category lookup) is clearly distinguished from scientific empirical validation.
