import json
import os

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"
mains_path = os.path.join(workspace, "public", "data", "gravity_mains.geojson")

with open(mains_path, "r", encoding="utf-8") as f:
    features = json.load(f)["features"]

assert len(features) == 624, f"Expected 624, got {len(features)}"

counts = {
    "MISSING_OR_ZERO_DIAMETER": 0,
    "MISSING_SLOPE_AND_INVERTS": 0,
    "ADVERSE_OR_ZERO_SLOPE": 0,
    "CALCULATED_RECORDED_MATERIAL": 0,
    "CALCULATED_ASSUMED_ROUGHNESS": 0
}

MATERIAL_MAP = {"RCP", "CP", "MRC", "CMP", "BR", "PVC", "HDPE"}

for f in features:
    p = f["properties"]
    
    # 1. Diameter check
    w = p.get("WIDTH")
    has_valid_diam = False
    if w is not None and str(w).strip() != "":
        try:
            fw = float(w)
            if fw > 0.0:
                has_valid_diam = True
        except:
            pass

    # 2. Slope check
    length = float(p.get("SHAPE.STLength()", 0.0))
    src_slope = float(p.get("SLOPE")) if (p.get("SLOPE") is not None and str(p.get("SLOPE")).strip() != '') else None
    up_elev = float(p.get("UPELEV")) if (p.get("UPELEV") is not None and str(p.get("UPELEV")).strip() != '') else None
    down_elev = float(p.get("DOWNELEV")) if (p.get("DOWNELEV") is not None and str(p.get("DOWNELEV")).strip() != '') else None

    slope_pct = None
    if src_slope is not None:
        slope_pct = src_slope
    elif up_elev is not None and down_elev is not None and length > 0 and down_elev > 0:
        slope_pct = ((up_elev - down_elev) / length) * 100.0

    # Mutually exclusive primary classification
    if not has_valid_diam:
        counts["MISSING_OR_ZERO_DIAMETER"] += 1
    elif slope_pct is None:
        counts["MISSING_SLOPE_AND_INVERTS"] += 1
    elif slope_pct <= 0.0:
        counts["ADVERSE_OR_ZERO_SLOPE"] += 1
    else:
        mat = str(p.get("MATERIAL", "")).upper().strip()
        if mat in MATERIAL_MAP:
            counts["CALCULATED_RECORDED_MATERIAL"] += 1
        else:
            counts["CALCULATED_ASSUMED_ROUGHNESS"] += 1

print("MUTUALLY EXCLUSIVE COUNTS:")
for k, v in counts.items():
    print(f"  {k}: {v}")

total = sum(counts.values())
print(f"Total: {total}")
assert total == 624
assert counts["MISSING_OR_ZERO_DIAMETER"] == 104
assert counts["MISSING_SLOPE_AND_INVERTS"] == 75
assert counts["ADVERSE_OR_ZERO_SLOPE"] == 181
assert counts["CALCULATED_RECORDED_MATERIAL"] == 186
assert counts["CALCULATED_ASSUMED_ROUGHNESS"] == 78
print("All assertions passed perfectly!")
