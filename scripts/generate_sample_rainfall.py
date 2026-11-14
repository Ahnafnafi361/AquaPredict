#!/usr/bin/env python3
"""
Generates an unverified exploratory sample gauge series for Station 1600 (Buffalo Bayou @ Milam St)
for testing the M2 frontend visualization hyetograph.
"""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest_rainfall import run_pipeline

def generate():
    start_time = datetime(2026, 10, 24, 0, 0, 0)
    rows = []
    # 24 hours of 15-min intervals (96 intervals)
    for i in range(96):
        t_from = start_time + timedelta(minutes=15 * i)
        t_to = t_from + timedelta(minutes=15)
        # Moderate storm burst between 03:00 (i=12) and 09:30 (i=38)
        if 14 <= i <= 38:
            if i in [22, 23, 24]:
                val = 0.38  # peak 15m rate (~1.52 in/hr)
            elif i in [20, 21, 25, 26]:
                val = 0.22
            elif i in [16, 17, 18, 19, 27, 28, 29]:
                val = 0.09
            else:
                val = 0.02
        else:
            val = 0.0
        rows.append({
            "Reading Date From": t_from.strftime("%m/%d/%Y %I:%M:%S %p"),
            "Reading Date To": t_to.strftime("%m/%d/%Y %I:%M:%S %p"),
            "Rain": f'{val:.2f}"'
        })

    df = pd.DataFrame(rows)
    tmp_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_sample_1600.csv")
    df.to_csv(tmp_csv, index=False)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample_series_path = os.path.join(project_root, "public", "data", "rainfall_sample_1600.json")
    sample_meta_path = os.path.join(project_root, "public", "data", "rainfall_sample_meta.json")

    run_pipeline(
        input_file=tmp_csv,
        output_series_path=sample_series_path,
        output_meta_path=sample_meta_path,
        station_id_override="1600",
        force_status="UNVERIFIED"
    )

    if os.path.exists(tmp_csv):
        os.remove(tmp_csv)

    print("Sample 1600 series successfully written to:", sample_series_path)

if __name__ == "__main__":
    generate()
