import os
import json
import pandas as pd

SRC_DIR = r"C:\AquaPredict_tests"
PUB_DIR = r"c:\Users\ASUS\Desktop\AquaPredict\public\data"

print("--- 1. Verifying Feature Counts ---")
layers = [
    ("GravityMains", "feat_GravityMains.json", "gravity_mains.geojson"),
    ("Inlets", "feat_Inlets.json", "inlets.geojson"),
    ("Manholes", "feat_Manholes.json", "manholes.geojson"),
    ("Discharge", "feat_Discharge.json", "discharge.geojson")
]

total_src = 0
total_pub = 0

for name, src_file, pub_file in layers:
    with open(os.path.join(SRC_DIR, src_file), "r", encoding="utf-8-sig") as f:
        src_data = json.load(f)
    with open(os.path.join(PUB_DIR, pub_file), "r", encoding="utf-8") as f:
        pub_data = json.load(f)
        
    src_cnt = len(src_data.get("features", []))
    pub_cnt = len(pub_data.get("features", []))
    total_src += src_cnt
    total_pub += pub_cnt
    
    match = src_cnt == pub_cnt
    print(f"[{'PASS' if match else 'FAIL'}] {name:15}: Source = {src_cnt}, Processed = {pub_cnt}")

print(f"Total Assets: Source = {total_src}, Processed = {total_pub} (Expected: 1,176)")

print("\n--- 2. Verifying Completeness Metrics from CSV vs quality_metrics.json ---")
with open(os.path.join(PUB_DIR, "quality_metrics.json"), "r", encoding="utf-8") as f:
    qm = json.load(f)

csv_map = {
    "gravity_mains": "completeness_GravityMains.csv",
    "inlets": "completeness_Inlets.csv",
    "manholes": "completeness_Manholes.csv",
    "discharge": "completeness_Discharge.csv"
}

all_metrics_match = True
for key, csv_file in csv_map.items():
    df = pd.read_csv(os.path.join(SRC_DIR, csv_file))
    json_metrics = {m["field"]: m for m in qm["datasets"][key]["metrics"]}
    
    for _, row in df.iterrows():
        field = str(row["Field"])
        pct_blank = float(row["PctBlank"])
        expected_comp = round(100.0 - pct_blank, 1)
        
        if field in json_metrics:
            actual_comp = json_metrics[field]["completeness_pct"]
            if abs(expected_comp - actual_comp) > 0.05:
                print(f"[FAIL] Metric mismatch in {key}.{field}: expected {expected_comp}%, got {actual_comp}%")
                all_metrics_match = False

if all_metrics_match:
    print("[PASS] All completeness metrics in quality_metrics.json match the source CSV files exactly!")

print("\n--- 3. Verifying DEM Metadata ---")
with open(os.path.join(PUB_DIR, "dem_meta.json"), "r", encoding="utf-8") as f:
    dem_meta = json.load(f)
print("DEM Source:", dem_meta["source"])
print("DEM Tile Used:", dem_meta["tile_used"])
print("DEM Resolution:", dem_meta["native_resolution"])
print("DEM Elevation (m):", f"Min {dem_meta['elevation_min_meters']}m, Max {dem_meta['elevation_max_meters']}m, Mean {dem_meta['elevation_mean_meters']}m")
print("DEM Status:", dem_meta["vertical_datum_status"])
