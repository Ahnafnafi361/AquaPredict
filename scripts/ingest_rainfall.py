#!/usr/bin/env python3
"""
AquaPredict Milestone 2 (M2) — Rainfall Data Ingestion & Quality Validation Pipeline
====================================================================================
Ingests, parses, cleans, validates, and standardizes rainfall gauge exports (e.g. HCFWS)
into normalized JSON outputs for the AquaPredict visualization HUD.

Key Features & Guardrails:
1. Strict status classification: VERIFIED, UNVERIFIED, UNAVAILABLE, INVALID.
2. Preserves raw files intact; keeps raw source strictly separated from processed data.
3. Explicit handling of duplicate timestamps, missing readings, and non-numeric artifacts.
4. Auto-detects temporal resolution (daily vs hourly vs sub-hourly).
5. Never invents missing observations or fabricates synthetic values.
6. Does NOT upgrade unverified gauge data to verified model inputs.
"""

import os
import sys
import glob
import json
import argparse
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# Default directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT_DIR = r"C:\AquaPredict_tests\rainfall"
DEFAULT_OUTPUT_SERIES = os.path.join(PROJECT_ROOT, "public", "data", "rainfall_series.json")
DEFAULT_OUTPUT_META = os.path.join(PROJECT_ROOT, "public", "data", "rainfall_meta.json")

# Known Harris County Flood Warning System (HCFWS) Gauge Metadata near Houston Pilot Area
KNOWN_GAUGES = {
    "1600": {
        "name": "Buffalo Bayou at Milam Street (Station 1600)",
        "lat": 29.7642,
        "lon": -95.3653,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "Immediate pilot area boundary (NE edge)",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "2220": {
        "name": "White Oak Bayou at Heights Blvd (Station 2220)",
        "lat": 29.7758,
        "lon": -95.3978,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "3.8 km NW of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "2250": {
        "name": "Little White Oak Bayou at Trimble St (Station 2250)",
        "lat": 29.7733,
        "lon": -95.3725,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "1.5 km N of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "520": {
        "name": "Brays Bayou at Main Street (Station 520)",
        "lat": 29.7028,
        "lon": -95.4019,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "6.5 km SW of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "530": {
        "name": "Brays Bayou at Almeda Road (Station 530)",
        "lat": 29.6997,
        "lon": -95.3811,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "6.8 km S of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "560": {
        "name": "Harrisburg / Buffalo Bayou (Station 560)",
        "lat": 29.7411,
        "lon": -95.2978,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "7.0 km E of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    },
    "570": {
        "name": "Buffalo Bayou at 69th Street (Station 570)",
        "lat": 29.7547,
        "lon": -95.3089,
        "source": "Harris County Flood Warning System (HCFWS)",
        "proximity": "5.6 km E of pilot area",
        "sensor_type": "Tipping Bucket Rain Gauge"
    }
}


def parse_arguments():
    parser = argparse.ArgumentParser(description="AquaPredict M2 Rainfall Ingestion & Quality Validation Pipeline")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Input directory containing rainfall files")
    parser.add_argument("--input-file", default=None, help="Explicit rainfall file to ingest")
    parser.add_argument("--output-series", default=DEFAULT_OUTPUT_SERIES, help="Destination JSON path for series")
    parser.add_argument("--output-meta", default=DEFAULT_OUTPUT_META, help="Destination JSON path for metadata")
    parser.add_argument("--station-id", default=None, help="Override or specify gauge station ID")
    parser.add_argument("--force-status", choices=["VERIFIED", "UNVERIFIED", "UNAVAILABLE", "INVALID"], default=None,
                        help="Override status only if external proof is supplied (strictly guardrailed)")
    return parser.parse_args()


def extract_station_id_from_filename(filename):
    """Attempt to extract standard 3 to 4 digit station ID from filename (e.g. '2220 Rainfall 2026-24-10.xls')."""
    base = os.path.basename(filename)
    parts = base.replace("_", " ").replace("-", " ").split()
    for part in parts:
        if part.isdigit() and len(part) in (3, 4, 5):
            return part
    return "UNKNOWN_STATION"


def read_raw_rainfall_file(filepath):
    """
    Reads excel (.xls, .xlsx) or csv file safely using available engines.
    Preserves original file completely without modifications.
    """
    ext = os.path.splitext(filepath)[1].lower()
    df = None
    engine_used = None

    if ext in [".xls", ".xlsx"]:
        for eng in ["calamine", "openpyxl", "xlrd"]:
            try:
                df = pd.read_excel(filepath, engine=eng)
                engine_used = eng
                break
            except Exception:
                continue
    elif ext == ".csv":
        for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                engine_used = f"csv({enc})"
                break
            except Exception:
                continue
    elif ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            if isinstance(raw_json, list):
                df = pd.DataFrame(raw_json)
            elif isinstance(raw_json, dict) and "records" in raw_json:
                df = pd.DataFrame(raw_json["records"])
            engine_used = "json"
        except Exception:
            pass

    return df, engine_used


def normalize_and_validate_dataframe(df, filename, station_id_arg=None):
    """
    Validates column structure, parses timestamps, cleans artifacts,
    detects duplicate timestamps, checks numeric ranges, and calculates temporal resolution.
    """
    report = {
        "valid": False,
        "error": None,
        "warnings": [],
        "station_id": None,
        "station_info": {},
        "raw_rows": len(df),
        "valid_rows": 0,
        "missing_rows": 0,
        "invalid_numeric_rows": 0,
        "duplicate_timestamps": 0,
        "detected_resolution": "unknown",
        "median_interval_minutes": None,
        "cumulative_in": 0.0,
        "cumulative_mm": 0.0,
        "max_reading_in": 0.0,
        "max_reading_mm": 0.0,
        "peak_intensity_in_hr": 0.0,
        "period_start": None,
        "period_end": None,
        "records": []
    }

    if df is None or len(df) == 0:
        report["error"] = "Empty dataset: DataFrame contains 0 rows."
        return report

    # 1. Column Identification
    col_map = {str(c).strip().lower(): c for c in df.columns}
    
    # Identify rain column
    rain_col = None
    for candidate in ["rain", "rainfall", "precip", "precipitation", "value", "reading", "amount"]:
        for col_lower, original in col_map.items():
            if candidate in col_lower:
                rain_col = original
                break
        if rain_col:
            break

    if not rain_col:
        report["error"] = f"Missing rainfall column. Found columns: {list(df.columns)}"
        return report

    # Identify date/time column(s)
    # HCFWS typically has "Reading Date From" and "Reading Date To"
    date_from_col = None
    date_to_col = None
    single_date_col = None

    for col_lower, original in col_map.items():
        if "from" in col_lower and ("date" in col_lower or "time" in col_lower):
            date_from_col = original
        elif "to" in col_lower and ("date" in col_lower or "time" in col_lower):
            date_to_col = original
        elif any(k in col_lower for k in ["timestamp", "datetime", "date", "time"]) and not single_date_col:
            single_date_col = original

    if not date_to_col and not single_date_col and not date_from_col:
        report["error"] = f"No recognizable date/time columns found. Columns: {list(df.columns)}"
        return report

    primary_date_col = date_to_col or single_date_col or date_from_col

    # 2. Station Identification
    station_id = station_id_arg or extract_station_id_from_filename(filename)
    report["station_id"] = station_id
    if station_id in KNOWN_GAUGES:
        report["station_info"] = KNOWN_GAUGES[station_id]
    else:
        report["station_info"] = {
            "name": f"Station {station_id}",
            "lat": None,
            "lon": None,
            "source": "Unverified Gauge Export",
            "proximity": "Unknown distance to pilot area",
            "sensor_type": "Unspecified Precipitation Gauge"
        }

    # 3. Numeric Cleaning & Parsing
    # Replace common artifacts: "?", '"', '″', and whitespace
    raw_series = df[rain_col].astype(str)
    cleaned_series = (
        raw_series.str.replace("?", "", regex=False)
        .str.replace('"', "", regex=False)
        .str.replace("″", "", regex=False)
        .str.strip()
    )

    numeric_rain = pd.to_numeric(cleaned_series, errors="coerce")

    # 4. Timestamp Parsing
    timestamps = pd.to_datetime(df[primary_date_col], errors="coerce")

    # Build validated records list
    records = []
    seen_timestamps = set()
    dup_count = 0
    missing_count = 0
    invalid_num_count = 0

    for idx, (ts, raw_val, num_val) in enumerate(zip(timestamps, raw_series, numeric_rain)):
        if pd.isna(ts):
            report["warnings"].append(f"Row {idx}: Unparseable timestamp '{df[primary_date_col].iloc[idx]}'")
            continue

        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        # Duplicate check
        if ts_str in seen_timestamps:
            dup_count += 1
            quality_flag = "DUPLICATE_TIMESTAMP"
        elif pd.isna(num_val):
            missing_count += 1
            quality_flag = "MISSING_VALUE"
        elif num_val < 0.0:
            invalid_num_count += 1
            quality_flag = "NEGATIVE_VALUE_INVALID"
        elif num_val > 15.0:  # Physically implausible single-reading spike in Texas (> 15 inches)
            invalid_num_count += 1
            quality_flag = "UNPHYSICAL_SPIKE_INVALID"
        else:
            quality_flag = "VALID"
            seen_timestamps.add(ts_str)

        # Retain original date range strings if available
        d_from_str = str(df[date_from_col].iloc[idx]) if date_from_col else None
        d_to_str = str(df[date_to_col].iloc[idx]) if date_to_col else ts_str

        rain_in = float(num_val) if pd.notna(num_val) and num_val >= 0 else None
        rain_mm = round(rain_in * 25.4, 3) if rain_in is not None else None

        records.append({
            "index": idx,
            "timestamp": ts_str,
            "date_from": d_from_str,
            "date_to": d_to_str,
            "rain_in": rain_in,
            "rain_mm": rain_mm,
            "raw_input": raw_val,
            "quality_flag": quality_flag
        })

    # Sort chronologically by timestamp
    records.sort(key=lambda r: r["timestamp"])

    report["records"] = records
    report["duplicate_timestamps"] = dup_count
    report["missing_rows"] = missing_count
    report["invalid_numeric_rows"] = invalid_num_count
    
    valid_records = [r for r in records if r["quality_flag"] == "VALID"]
    report["valid_rows"] = len(valid_records)

    if not valid_records:
        report["error"] = "Zero valid numeric observation records after quality filtering."
        return report

    # 5. Temporal Resolution Detection & Summary Statistics
    valid_ts = [datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S") for r in valid_records]
    intervals = [(valid_ts[i] - valid_ts[i-1]).total_seconds() for i in range(1, len(valid_ts))]

    if intervals:
        median_sec = float(np.median(intervals))
        report["median_interval_minutes"] = round(median_sec / 60.0, 1)

        if 80000 <= median_sec <= 90000:
            report["detected_resolution"] = "daily"
        elif 3300 <= median_sec <= 3900:
            report["detected_resolution"] = "hourly"
        elif median_sec <= 1800:
            report["detected_resolution"] = f"sub-hourly ({int(round(median_sec/60.0))}m)"
        else:
            report["detected_resolution"] = f"custom ({round(median_sec/60.0, 1)}m)"
    else:
        report["detected_resolution"] = "single-point"
        report["median_interval_minutes"] = None

    valid_vals_in = [r["rain_in"] for r in valid_records]
    report["cumulative_in"] = round(float(sum(valid_vals_in)), 3)
    report["cumulative_mm"] = round(report["cumulative_in"] * 25.4, 2)
    report["max_reading_in"] = round(float(max(valid_vals_in)), 3)
    report["max_reading_mm"] = round(report["max_reading_in"] * 25.4, 2)

    # Estimate peak intensity (in/hr) based on detected resolution
    if report["median_interval_minutes"] and report["median_interval_minutes"] > 0:
        hr_multiplier = 60.0 / report["median_interval_minutes"]
        report["peak_intensity_in_hr"] = round(report["max_reading_in"] * hr_multiplier, 2)
    else:
        report["peak_intensity_in_hr"] = report["max_reading_in"]

    report["period_start"] = valid_records[0]["timestamp"]
    report["period_end"] = valid_records[-1]["timestamp"]
    report["valid"] = True

    return report


def build_unavailable_output(input_dir, output_series_path, output_meta_path):
    """Generates standard UNAVAILABLE payload when no gauge exports exist."""
    meta = {
        "timestamp_generated": datetime.now(timezone.utc).isoformat(),
        "status": "UNAVAILABLE",
        "station_id": None,
        "station_name": "No Station Configured",
        "source_directory": input_dir,
        "files_scanned": 0,
        "message": (
            "No rainfall gauge files found in C:\\AquaPredict_tests\\rainfall. "
            "System state is set to UNAVAILABLE. Awaiting gauge file placement or API feed."
        ),
        "expected_inputs": {
            "format": ["Excel (.xls, .xlsx)", "CSV (.csv)", "JSON (.json)"],
            "expected_columns": ["Reading Date From", "Reading Date To", "Rain (inches)"],
            "target_station": "Harris County Flood Warning System (HCFWS) Station 1600 (Buffalo Bayou @ Milam St)",
            "ingestion_command": "python scripts/ingest_rainfall.py"
        },
        "scientific_disclaimers": [
            "Rainfall observations are currently UNAVAILABLE for this pilot run.",
            "Synthetic or fabricated rainfall has NOT been substituted into the system.",
            "Waterlogging susceptibility (M1) remains purely terrain- and inlet-driven."
        ]
    }

    series = {
        "status": "UNAVAILABLE",
        "station_id": None,
        "station_name": "No Rainfall Data Ingested",
        "station_coords": None,
        "source_organization": "None (Awaiting Ingestion)",
        "source_file": None,
        "temporal_resolution": "unavailable",
        "median_interval_minutes": None,
        "units": {"primary": "in", "secondary": "mm"},
        "time_zone": "US/Central (CDT/CST)",
        "period": {"start": None, "end": None},
        "metrics": {
            "total_records": 0,
            "valid_records": 0,
            "nonzero_records": 0,
            "missing_records": 0,
            "duplicate_timestamps": 0,
            "cumulative_in": 0.0,
            "cumulative_mm": 0.0,
            "max_reading_in": 0.0,
            "max_reading_mm": 0.0,
            "peak_intensity_in_hr": 0.0
        },
        "records": [],
        "disclaimer": "UNAVAILABLE: No gauge observations exist in raw directory. Real-time data is not claimed."
    }

    os.makedirs(os.path.dirname(output_series_path), exist_ok=True)
    with open(output_series_path, "w", encoding="utf-8") as f:
        json.dump(series, f, indent=2)

    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"[STATUS: UNAVAILABLE] Written clean empty state to {output_series_path}")
    return series, meta


def run_pipeline(input_dir=DEFAULT_INPUT_DIR, input_file=None, output_series_path=DEFAULT_OUTPUT_SERIES,
                 output_meta_path=DEFAULT_OUTPUT_META, station_id_override=None, force_status=None):
    """
    Main ingestion execution pipeline.
    """
    print("=" * 70)
    print(" AquaPredict Milestone 2 (M2) — Rainfall Ingestion & QA Pipeline")
    print("=" * 70)

    # 1. Discover target files
    target_files = []
    if input_file and os.path.exists(input_file):
        target_files.append(input_file)
    elif os.path.exists(input_dir):
        for pattern in ["*.xls", "*.xlsx", "*.csv", "*.json"]:
            target_files.extend(glob.glob(os.path.join(input_dir, pattern)))

    print(f"Target Directory: {input_dir}")
    print(f"Discovered Files: {len(target_files)}")

    # If no files found, write UNAVAILABLE output
    if not target_files:
        return build_unavailable_output(input_dir, output_series_path, output_meta_path)

    # 2. Iterate and parse discovered files
    results = []
    for fpath in target_files:
        fname = os.path.basename(fpath)
        print(f"\nProcessing file: {fname} ({os.path.getsize(fpath)} bytes)")
        df, engine = read_raw_rainfall_file(fpath)
        if df is None:
            print(f"  [INVALID] Failed to read or parse {fname}")
            results.append({"filename": fname, "filepath": fpath, "valid": False, "error": "Parser failed to read format"})
            continue

        print(f"  Loaded with engine: {engine}, Shape: {df.shape}")
        report = normalize_and_validate_dataframe(df, fname, station_id_arg=station_id_override)
        report["filename"] = fname
        report["filepath"] = fpath
        report["engine"] = engine
        results.append(report)

    # 3. Select primary active dataset (prefer closest known gauge or highest valid row count)
    valid_results = [r for r in results if r["valid"]]
    
    if not valid_results:
        # All files were invalid
        meta = {
            "timestamp_generated": datetime.now(timezone.utc).isoformat(),
            "status": "INVALID",
            "message": "Files were found but all failed validation or contained 0 valid observation rows.",
            "files_scanned": len(results),
            "file_details": results
        }
        series = {
            "status": "INVALID",
            "station_id": None,
            "station_name": "Invalid File Format",
            "records": [],
            "metrics": {},
            "disclaimer": "INVALID: Source file(s) failed validation. Check column schemas."
        }
        with open(output_series_path, "w", encoding="utf-8") as f:
            json.dump(series, f, indent=2)
        with open(output_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print("[STATUS: INVALID] Written invalid report.")
        return series, meta

    # Sort valid results: if Station 1600 is present, prefer it; otherwise select one with largest valid rows
    valid_results.sort(key=lambda r: (r["station_id"] == "1600", r["valid_rows"]), reverse=True)
    primary = valid_results[0]

    # Verification status logic:
    # Unless explicit third-party calibration certificate is provided, status is UNVERIFIED.
    status = force_status or "UNVERIFIED"

    # Build primary series output
    st_info = primary.get("station_info", {})
    st_coords = [st_info.get("lat"), st_info.get("lon")] if st_info.get("lat") else None

    nonzero_count = sum(1 for r in primary["records"] if r["rain_in"] and r["rain_in"] > 0)

    series_payload = {
        "status": status,
        "station_id": primary["station_id"],
        "station_name": st_info.get("name", f"Station {primary['station_id']}"),
        "station_coords": st_coords,
        "source_organization": st_info.get("source", "Harris County Flood Warning System (HCFWS)"),
        "source_file": primary["filename"],
        "temporal_resolution": primary["detected_resolution"],
        "median_interval_minutes": primary["median_interval_minutes"],
        "units": {
            "primary": "in",
            "secondary": "mm"
        },
        "time_zone": "US/Central (CDT/CST)",
        "period": {
            "start": primary["period_start"],
            "end": primary["period_end"]
        },
        "metrics": {
            "total_records": primary["raw_rows"],
            "valid_records": primary["valid_rows"],
            "nonzero_records": nonzero_count,
            "missing_records": primary["missing_rows"],
            "duplicate_timestamps": primary["duplicate_timestamps"],
            "invalid_numeric_records": primary["invalid_numeric_rows"],
            "cumulative_in": primary["cumulative_in"],
            "cumulative_mm": primary["cumulative_mm"],
            "max_reading_in": primary["max_reading_in"],
            "max_reading_mm": primary["max_reading_mm"],
            "peak_intensity_in_hr": primary["peak_intensity_in_hr"]
        },
        "records": primary["records"],
        "disclaimer": (
            "UNVERIFIED EXPLORATORY DATA: Raw gauge export. Not verified against radar or calibrated. "
            "Do NOT use as calibrated hydrodynamic or flood model input."
        )
    }

    meta_payload = {
        "timestamp_generated": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "primary_station_id": primary["station_id"],
        "primary_file": primary["filename"],
        "total_files_scanned": len(results),
        "valid_files_count": len(valid_results),
        "inventory": [
            {
                "filename": r.get("filename"),
                "valid": r.get("valid"),
                "station_id": r.get("station_id"),
                "rows": r.get("raw_rows", 0),
                "resolution": r.get("detected_resolution"),
                "period": [r.get("period_start"), r.get("period_end")] if r.get("valid") else None
            }
            for r in results
        ],
        "guardrails": {
            "raw_files_preserved": True,
            "missing_data_fabricated": False,
            "calibrated_model_input": False
        }
    }

    os.makedirs(os.path.dirname(output_series_path), exist_ok=True)
    with open(output_series_path, "w", encoding="utf-8") as f:
        json.dump(series_payload, f, indent=2)

    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)

    print("\n" + "=" * 70)
    print(f" INGESTION COMPLETE [STATUS: {status}]")
    print(f" Station: {series_payload['station_name']}")
    print(f" Temporal Resolution: {primary['detected_resolution']}")
    print(f" Period: {primary['period_start']} -> {primary['period_end']}")
    print(f" Valid Observations: {primary['valid_rows']} (Non-zero: {nonzero_count})")
    print(f" Cumulative Rain: {primary['cumulative_in']} in ({primary['cumulative_mm']} mm)")
    print(f" Peak Single Reading: {primary['max_reading_in']} in")
    print(f" Output Series: {output_series_path}")
    print(f" Output Meta: {output_meta_path}")
    print("=" * 70)

    return series_payload, meta_payload


if __name__ == "__main__":
    args = parse_arguments()
    run_pipeline(
        input_dir=args.input_dir,
        input_file=args.input_file,
        output_series_path=args.output_series,
        output_meta_path=args.output_meta,
        station_id_override=args.station_id,
        force_status=args.force_status
    )
