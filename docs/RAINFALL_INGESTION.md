# AquaPredict Milestone 2 (M2) — Rainfall Data Ingestion & Governance Guide

## 1. Overview & Architectural Purpose
Milestone 2 (M2) introduces an automated, repeatable ingestion and quality validation pipeline for rainfall observation data in AquaPredict. 
The pipeline transforms raw gauge exports (such as those from the **Harris County Flood Warning System (HCFWS)** or **USGS**) into standardized, quality-tagged JSON data structures consumed by the AquaPredict interactive visualization interface.

```
+------------------------------------+
| Raw Gauge Data                     |
| C:\AquaPredict_tests\rainfall\     |
| (.xls, .xlsx, .csv, .json)         |
+-----------------+------------------+
                  |
                  v
+-----------------+------------------+
| Ingestion & QA Pipeline            |
| scripts/ingest_rainfall.py         |
| - Strips formatting artifacts      |
| - Validates timestamps & intervals |
| - Rejects spikes & negative values |
| - Classifies status (UNVERIFIED)   |
| - Never fabricates missing values  |
+-----------------+------------------+
                  |
                  v
+-----------------+------------------+
| Normalized Outputs                 |
| public/data/rainfall_series.json   |
| public/data/rainfall_meta.json     |
+-----------------+------------------+
                  |
                  v
+-----------------+------------------+
| AquaPredict Frontend               |
| - Interactive Hyetograph (SVG)     |
| - Empty State (if UNAVAILABLE)     |
| - Quality & Disclaimer Badges      |
+------------------------------------+
```

---

## 2. Data Quality & Status Definitions

Every ingested dataset is classified strictly into one of four quality tiers:

| Status | Definition & Verification Rules | Model Usage Policy |
| :--- | :--- | :--- |
| **`VERIFIED`** | Gauge data that has undergone third-party sensor calibration, ground-truth radar QA/QC, and benchmark synchronization. | Eligible for validated hydraulic models. |
| **`UNVERIFIED`** | Raw external gauge exports (e.g. standard HCFWS `.xls` downloads) that parsed cleanly, but lack local sensor calibration audits. | **Visual exploratory analysis ONLY.** Excluded from calibrated model input. |
| **`UNAVAILABLE`** | No raw gauge files exist in the target directory (`C:\AquaPredict_tests\rainfall`). | Informative empty state displayed. Zero synthetic data invented. |
| **`INVALID`** | Corrupt files, missing required time/rain columns, or negative/unphysical values. | Rejected by pipeline; error logged. |

> [!IMPORTANT]
> **Status Upgrade Guardrail:** The pipeline defaults all raw external gauge records to `UNVERIFIED`. The system will **never** automatically upgrade a dataset to `VERIFIED` without verifiable calibration evidence.

---

## 3. Supported File Formats & Column Mapping

The pipeline supports `.xls`, `.xlsx`, `.csv`, and `.json`.

### A. Harris County Flood Warning System (HCFWS) Standard Export
Commonly exported with `calamine`, `openpyxl`, or `xlrd` engines:
* **`Reading Date From`**: Interval start timestamp (e.g., `"10/24/2026 04:00:00 AM"`)
* **`Reading Date To`**: Interval end timestamp (e.g., `"10/24/2026 04:15:00 AM"`)
* **`Rain`**: Precipitation in inches. Often contains gauge artifacts (e.g. `0.25"`, `?`, `0.10″`, whitespace).

### B. Standard Time-Series CSV / JSON
* **Timestamp Column**: `Timestamp`, `Datetime`, `Date`, or `Time` (ISO 8601 or standard datetime formats)
* **Precipitation Column**: `Rain`, `Rainfall`, `Precip`, or `Value` (in inches or millimeters)

---

## 4. How to Ingest a New Gauge Station or Dataset

### Step 1: Place Raw Gauge File into Directory
Copy your exported file into `C:\AquaPredict_tests\rainfall\`:
```powershell
Copy-Item "1600_Rainfall_2026-10-24.xls" "C:\AquaPredict_tests\rainfall\"
```

### Step 2: Run the Ingestion Pipeline
To ingest all files in the default directory:
```powershell
python scripts/ingest_rainfall.py
```

To ingest a specific file directly:
```powershell
python scripts/ingest_rainfall.py --input-file "path/to/my_gauge_data.csv" --station-id "1600"
```

### Step 3: Verify Processed Outputs
Check the newly generated files in `public/data/`:
* `public/data/rainfall_series.json`: Contains parsed records, intervals, cumulative sums, peak rates.
* `public/data/rainfall_meta.json`: Ingestion audit log and summary metrics.

---

## 5. How to Add a New Known Station Definition

To add a new station (e.g. USGS Gauge or new Harris County sensor), edit `scripts/ingest_rainfall.py` and register the station in the `KNOWN_GAUGES` dictionary:

```python
KNOWN_GAUGES["1600"] = {
    "name": "Buffalo Bayou at Milam Street (Station 1600)",
    "lat": 29.7642,
    "lon": -95.3653,
    "source": "Harris County Flood Warning System (HCFWS)",
    "proximity": "Immediate pilot area boundary (NE edge)",
    "sensor_type": "Tipping Bucket Rain Gauge"
}
```

---

## 6. Pipeline Guardrails & Limitations

1. **No Data Fabrication**: Missing intervals are recorded as missing (`null`) with quality flag `MISSING_VALUE`. The pipeline never interpolates or fabricates synthetic rainfall to fill gaps.
2. **Duplicate Detection**: Identical timestamps are tracked, preserving the first instance and flagging repeats with `DUPLICATE_TIMESTAMP`.
3. **Plausibility Thresholds**: Single readings $> 15.0$ inches (which exceed US continental records) or negative values are flagged as `UNPHYSICAL_SPIKE_INVALID` or `NEGATIVE_VALUE_INVALID`.
4. **Temporal Resolution Integrity**: If a file contains daily observations, it is flagged as `daily`; the pipeline does not synthesize artificial 15-minute intervals.
5. **Independent M0/M1 Operations**: The M0 GIS infrastructure and M1 terrain susceptibility calculations remain fully functional regardless of whether rainfall data is present or absent.
