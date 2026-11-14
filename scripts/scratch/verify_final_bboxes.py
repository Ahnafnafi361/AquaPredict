import json
import os

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"
EXPECTED_BBOX = {"west": -95.375, "south": 29.756, "east": -95.365, "north": 29.765}

files_to_check = [
    ("public/data/dem_meta.json", lambda d: d["pilot_bbox_wgs84"]),
    ("public/data/dem_grid.json", lambda d: d["bbox"]),
    ("public/data/m1_analysis_meta.json", lambda d: d["pilot_boundary"]),
    ("public/data/susceptibility_grid.json", lambda d: d["bbox"]),
    ("public/data/m3_validation_readiness.json", lambda d: d["pilot_area"]["bounding_box"]),
    ("public/data/m4_synthesis_meta.json", lambda d: d["pilot_boundary"]),
    ("public/data/m5_simulation_meta.json", lambda d: d["domain"]["pilot_boundary"]),
    ("public/data/m6_drainage_network.json", lambda d: d["provenance"]["boundary"]),
    ("public/data/pilot_boundary.geojson", lambda d: {
        "west": d["features"][0]["properties"]["west"],
        "south": d["features"][0]["properties"]["south"],
        "east": d["features"][0]["properties"]["east"],
        "north": d["features"][0]["properties"]["north"]
    })
]

for rel_path, getter in files_to_check:
    full_path = os.path.join(workspace, rel_path)
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bbox = getter(data)
    for k in ["west", "south", "east", "north"]:
        assert round(bbox[k], 4) == round(EXPECTED_BBOX[k], 4), f"{rel_path} {k}: {bbox[k]} != {EXPECTED_BBOX[k]}"
    print(f"[VERIFIED] {rel_path} -> {bbox}")

print("\nALL FILES PRESERVE THE AUTHORITATIVE BOUNDING BOX EXACTLY:")
print("West: -95.3750, South: 29.7560, East: -95.3650, North: 29.7650")
