#!/usr/bin/env python3
"""
AquaPredict Milestone 2 (M2) — Rainfall Ingestion Pipeline Test Suite
=====================================================================
Automated tests verifying:
1. Empty directory handling -> UNAVAILABLE status.
2. Real-world HCFWS Excel/CSV format parsing (15-min sub-hourly).
3. Data cleaning (stripping ?, ", ″, whitespace, handling missing data).
4. Temporal resolution detection (sub-hourly vs daily).
5. Duplicate timestamp detection and explicit accounting.
6. Negative value and unphysical spike rejection.
7. Output schema conformity (units, time zone, metadata).
8. Strict guardrail: unverified data is never upgraded to verified model input.
"""

import os
import sys
import json
import tempfile
import unittest
import pandas as pd
from datetime import datetime, timedelta

# Import ingestion logic
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest_rainfall import (
    read_raw_rainfall_file,
    normalize_and_validate_dataframe,
    build_unavailable_output,
    run_pipeline,
    KNOWN_GAUGES
)

class TestRainfallIngestion(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_empty_directory_produces_unavailable_state(self):
        """Verifies that an empty folder cleanly yields UNAVAILABLE status without fabricating data."""
        empty_dir = os.path.join(self.temp_dir.name, "empty_rainfall")
        os.makedirs(empty_dir, exist_ok=True)

        series_path = os.path.join(self.temp_dir.name, "series_out.json")
        meta_path = os.path.join(self.temp_dir.name, "meta_out.json")

        series, meta = run_pipeline(
            input_dir=empty_dir,
            output_series_path=series_path,
            output_meta_path=meta_path
        )

        self.assertEqual(series["status"], "UNAVAILABLE")
        self.assertEqual(meta["status"], "UNAVAILABLE")
        self.assertEqual(len(series["records"]), 0)
        self.assertEqual(series["metrics"]["total_records"], 0)
        self.assertIn("UNAVAILABLE", series["disclaimer"])
        self.assertTrue(os.path.exists(series_path))
        self.assertTrue(os.path.exists(meta_path))

    def test_02_hcfws_subhourly_parsing_and_resolution(self):
        """Tests parsing a standard 15-minute HCFWS gauge record with typical rainfall burst."""
        # Create 15-min intervals over 6 hours (24 points)
        start_time = datetime(2026, 10, 24, 0, 0, 0)
        rows = []
        for i in range(24):
            t_from = start_time + timedelta(minutes=15 * i)
            t_to = t_from + timedelta(minutes=15)
            # simulate a rain event with peak 0.45 inches in 15 min
            rain_val = 0.45 if i == 10 else (0.15 if 8 <= i <= 14 else 0.0)
            rows.append({
                "Reading Date From": t_from.strftime("%m/%d/%Y %I:%M:%S %p"),
                "Reading Date To": t_to.strftime("%m/%d/%Y %I:%M:%S %p"),
                "Rain": f'{rain_val:.2f}"'  # includes gauge inch quote artifact
            })

        df = pd.DataFrame(rows)
        csv_path = os.path.join(self.temp_dir.name, "1600 Rainfall 2026-10-24.csv")
        df.to_csv(csv_path, index=False)

        series_path = os.path.join(self.temp_dir.name, "series_out.json")
        meta_path = os.path.join(self.temp_dir.name, "meta_out.json")

        series, meta = run_pipeline(
            input_file=csv_path,
            output_series_path=series_path,
            output_meta_path=meta_path
        )

        self.assertEqual(series["status"], "UNVERIFIED")
        self.assertEqual(series["station_id"], "1600")
        self.assertIn("Buffalo Bayou", series["station_name"])
        self.assertEqual(series["temporal_resolution"], "sub-hourly (15m)")
        self.assertEqual(series["metrics"]["total_records"], 24)
        self.assertEqual(series["metrics"]["valid_records"], 24)
        self.assertEqual(series["metrics"]["missing_records"], 0)
        self.assertAlmostEqual(series["metrics"]["max_reading_in"], 0.45, places=2)
        # 0.45 in / 15m = 1.80 in/hr
        self.assertAlmostEqual(series["metrics"]["peak_intensity_in_hr"], 1.80, places=2)
        # Check units
        self.assertEqual(series["units"]["primary"], "in")
        self.assertEqual(series["units"]["secondary"], "mm")
        self.assertEqual(series["time_zone"], "US/Central (CDT/CST)")

    def test_03_dirty_data_cleaning_and_missing_values(self):
        """Verifies handling of '?', blanks, whitespace, negative numbers, and spikes."""
        rows = [
            {"Reading Date From": "10/24/2026 01:00:00 AM", "Reading Date To": "10/24/2026 01:15:00 AM", "Rain": '0.05"'},
            {"Reading Date From": "10/24/2026 01:15:00 AM", "Reading Date To": "10/24/2026 01:30:00 AM", "Rain": '?'},       # missing / sensor error
            {"Reading Date From": "10/24/2026 01:30:00 AM", "Reading Date To": "10/24/2026 01:45:00 AM", "Rain": '   '},     # whitespace missing
            {"Reading Date From": "10/24/2026 01:45:00 AM", "Reading Date To": "10/24/2026 02:00:00 AM", "Rain": '-0.20'},    # negative invalid
            {"Reading Date From": "10/24/2026 02:00:00 AM", "Reading Date To": "10/24/2026 02:15:00 AM", "Rain": '25.0"'},    # unphysical spike > 15 in
            {"Reading Date From": "10/24/2026 02:15:00 AM", "Reading Date To": "10/24/2026 02:30:00 AM", "Rain": '0.12″'}     # double prime unicode
        ]
        df = pd.DataFrame(rows)
        report = normalize_and_validate_dataframe(df, "2220_test.csv")

        self.assertTrue(report["valid"])
        self.assertEqual(report["raw_rows"], 6)
        # Valid should be rows 0 (0.05) and 5 (0.12)
        self.assertEqual(report["valid_rows"], 2)
        self.assertEqual(report["missing_rows"], 2) # '?' and '   '
        self.assertEqual(report["invalid_numeric_rows"], 2) # -0.20 and 25.0
        self.assertAlmostEqual(report["cumulative_in"], 0.17, places=2)

    def test_04_daily_summary_classification(self):
        """Ensures daily summary exports are classified as 'daily' rather than inventing hourly steps."""
        start_date = datetime(2026, 10, 1)
        rows = []
        for d in range(10):
            cur_date = start_date + timedelta(days=d)
            rows.append({
                "Date": cur_date.strftime("%Y-%m-%d"),
                "Rainfall": round(0.1 * d, 2)
            })
        df = pd.DataFrame(rows)
        report = normalize_and_validate_dataframe(df, "daily_precip.csv")

        self.assertTrue(report["valid"])
        self.assertEqual(report["detected_resolution"], "daily")
        self.assertEqual(report["raw_rows"], 10)
        self.assertEqual(report["valid_rows"], 10)

    def test_05_duplicate_timestamps_handling(self):
        """Verifies duplicate timestamps are flagged and not double-counted in cumulative totals."""
        rows = [
            {"Timestamp": "2026-10-24 10:00:00", "Rain": 0.10},
            {"Timestamp": "2026-10-24 10:00:00", "Rain": 0.10},  # duplicate
            {"Timestamp": "2026-10-24 10:15:00", "Rain": 0.20}
        ]
        df = pd.DataFrame(rows)
        report = normalize_and_validate_dataframe(df, "dup_test.csv")

        self.assertTrue(report["valid"])
        self.assertEqual(report["duplicate_timestamps"], 1)
        self.assertEqual(report["valid_rows"], 2)
        self.assertAlmostEqual(report["cumulative_in"], 0.30, places=2)

    def test_06_corrupt_file_marks_status_invalid(self):
        """Verifies unparseable file is flagged as INVALID."""
        bad_path = os.path.join(self.temp_dir.name, "corrupt.csv")
        with open(bad_path, "w") as f:
            f.write("foo,bar\n1,2\n3,4\n") # no date or rain columns

        series_path = os.path.join(self.temp_dir.name, "series_out.json")
        meta_path = os.path.join(self.temp_dir.name, "meta_out.json")

        series, meta = run_pipeline(
            input_file=bad_path,
            output_series_path=series_path,
            output_meta_path=meta_path
        )

        self.assertEqual(series["status"], "INVALID")
        self.assertEqual(meta["status"], "INVALID")

    def test_07_known_gauges_metadata_accuracy(self):
        """Checks Station 1600 coordinates align with Downtown Houston pilot boundary."""
        st1600 = KNOWN_GAUGES["1600"]
        self.assertEqual(st1600["lat"], 29.7642)
        self.assertEqual(st1600["lon"], -95.3653)
        # Pilot bounding box: [-95.3750, 29.7560] to [-95.3650, 29.7650]
        self.assertTrue(29.7560 <= st1600["lat"] <= 29.7650)
        self.assertTrue(-95.3750 <= st1600["lon"] <= -95.3650)


if __name__ == "__main__":
    unittest.main(verbosity=2)
