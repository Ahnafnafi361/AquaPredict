import json
import os

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"
mains_path = os.path.join(workspace, "public", "data", "gravity_mains.geojson")

with open(mains_path, "r", encoding="utf-8") as f:
    features = json.load(f)["features"]

print(f"Total Gravity Mains: {len(features)}")

# Let's inspect properties and classification
# For each conduit, check:
# 1. Diameter: p.get("WIDTH")
# 2. Length: p.get("SHAPE.STLength()")
# 3. Explicit Slope: p.get("SLOPE")
# 4. Inverts: p.get("UPELEV"), p.get("DOWNELEV")

# Mutual exclusivity audit:
# Mutually exclusive hierarchy for why a conduit cannot have a valid Manning capacity:
# If diameter is missing or <= 0: "MISSING_OR_ZERO_DIAMETER"
# Else if slope is missing (both explicit slope and inverts are missing/incomplete): "MISSING_SLOPE_AND_INVERTS"
# Else if effective slope is <= 0: "ADVERSE_OR_ZERO_SLOPE"
# Else: "VALID_POSITIVE_CAPACITY" (which can be with recorded material vs assumed n)

categories = {}
reasons = {}

for f in features:
    p = f["properties"]
    cid = p.get("FACILITYID")
    
    diam = float(p.get("WIDTH")) if (p.get("WIDTH") is not None and str(p.get("WIDTH")).strip() != '') else None
    length = float(p.get("SHAPE.STLength()", 0.0))
    src_slope = float(p.get("SLOPE")) if (p.get("SLOPE") is not None and str(p.get("SLOPE")).strip() != '') else None
    up_elev = float(p.get("UPELEV")) if (p.get("UPELEV") is not None and str(p.get("UPELEV")).strip() != '') else None
    down_elev = float(p.get("DOWNELEV")) if (p.get("DOWNELEV") is not None and str(p.get("DOWNELEV")).strip() != '') else None
    mat = p.get("MATERIAL")
    
    # Determine effective slope
    slope_pct = None
    slope_src = None
    if src_slope is not None:
        slope_pct = src_slope
        slope_src = "SOURCE_SLOPE"
    elif up_elev is not None and down_elev is not None and length > 0 and down_elev > 0:
        slope_pct = ((up_elev - down_elev) / length) * 100.0
        slope_src = "DERIVED_INVERT"

    # Mutually exclusive classification
    if diam is None or diam <= 0:
        cat = "MISSING_OR_ZERO_DIAMETER"
        detail = f"diam={diam}"
    elif slope_pct is None:
        cat = "MISSING_SLOPE_AND_INVERTS"
        detail = f"src_slope={src_slope}, up={up_elev}, down={down_elev}"
    elif slope_pct <= 0:
        cat = "ADVERSE_OR_ZERO_SLOPE"
        detail = f"slope_pct={slope_pct:.4f}% ({slope_src})"
    else:
        # Valid capacity!
        mat_key = str(mat).upper().strip() if mat else ""
        if mat_key in ["RCP", "CP", "MRC", "CMP", "BR", "PVC", "HDPE"]:
            cat = "CALCULATED_RECORDED_MATERIAL"
        else:
            cat = "CALCULATED_ASSUMED_ROUGHNESS"
        detail = f"slope={slope_pct:.2f}%, diam={diam}in, mat={mat}"

    categories[cat] = categories.get(cat, 0) + 1

print("\n--- MUTUALLY EXCLUSIVE PRIMARY CLASSIFICATION OF ALL 624 CONDUITS ---")
total = 0
for cat, count in sorted(categories.items()):
    pct = (count / len(features)) * 100.0
    print(f"{cat:<35}: {count:>3} ({pct:>5.1f}%)")
    total += count
print(f"Total checked: {total}")
