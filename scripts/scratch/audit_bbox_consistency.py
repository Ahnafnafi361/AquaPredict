import json
import os

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"

print("=" * 80)
print("COMPREHENSIVE AUDIT OF BOUNDING BOXES ACROSS AQUAPREDICT (M0 - M6)")
print("=" * 80)

# 1. Search for M6 audit bounding box [-95.375, 29.758, -95.355, 29.772]
print("\n--- 1. Searching for occurrences of '29.772' or '-95.355' or '29.758' ---")
for root, dirs, files in os.walk(workspace):
    if ".git" in root or "__pycache__" in root or "node_modules" in root:
        continue
    for f in files:
        if f.endswith(('.py', '.json', '.geojson', '.js', '.html', '.css', '.md', '.txt')):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    if "29.772" in content or "-95.355" in content or "29.758" in content:
                        for lno, line in enumerate(content.splitlines(), 1):
                            if any(k in line for k in ["29.772", "-95.355", "29.758"]):
                                print(f"[{os.path.relpath(path, workspace)}:{lno}] {line.strip()[:120]}")
            except Exception as e:
                pass

# 2. Check GeoJSON spatial bounds
print("\n--- 2. Actual GeoJSON feature coordinates extents ---")
geojsons = [
    "pilot_boundary.geojson",
    "inlets.geojson",
    "manholes.geojson",
    "discharge.geojson",
    "gravity_mains.geojson"
]

for gj_name in geojsons:
    gj_path = os.path.join(workspace, "public", "data", gj_name)
    if os.path.exists(gj_path):
        with open(gj_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        bounds = [float('inf'), float('-inf'), float('inf'), float('-inf')] # min_lon, max_lon, min_lat, max_lat
        count = 0
        
        def check_pt(pt):
            lon, lat = pt[0], pt[1]
            if lon < bounds[0]: bounds[0] = lon
            if lon > bounds[1]: bounds[1] = lon
            if lat < bounds[2]: bounds[2] = lat
            if lat > bounds[3]: bounds[3] = lat

        def extract_coords(geom):
            gtype = geom.get('type')
            coords = geom.get('coordinates', [])

            if gtype == 'Point':
                check_pt(coords)
            elif gtype in ('MultiPoint', 'LineString'):
                for pt in coords: check_pt(pt)
            elif gtype in ('MultiLineString', 'Polygon'):
                for ring in coords:
                    for pt in ring: check_pt(pt)
            elif gtype == 'MultiPolygon':
                for poly in coords:
                    for ring in poly:
                        for pt in ring: check_pt(pt)

        features = data.get('features', [])
        if not features and data.get('type') == 'Feature':
            features = [data]
        elif not features and 'coordinates' in data:
            extract_coords(data)
            count = 1

        for feat in features:
            count += 1
            geom = feat.get('geometry')
            if geom:
                extract_coords(geom)

        print(f"{gj_name:<25} | count={count:<5} | Lon: [{bounds[0]:.6f}, {bounds[1]:.6f}] | Lat: [{bounds[2]:.6f}, {bounds[3]:.6f}]")

# 3. Check JSON Metadata & Matrix Grids
print("\n--- 3. Metadata Files & Lookups ---")
meta_files = [
    "dem_meta.json",
    "dem_grid.json",
    "m1_analysis_meta.json",
    "susceptibility_grid.json",
    "m3_validation_readiness.json",
    "m4_synthesis_meta.json",
    "m5_simulation_meta.json",
    "simulation_scenarios.json",
    "m6_analysis_meta.json",
    "m6_drainage_network.json"
]

for mf in meta_files:
    mf_path = os.path.join(workspace, "public", "data", mf)
    if os.path.exists(mf_path):
        with open(mf_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check for bbox / bounds
        bbox_found = []
        def find_bbox(d, prefix="", depth=0):
            if depth > 4: return
            if isinstance(d, dict):
                for k, v in d.items():
                    if any(x in k.lower() for x in ['bbox', 'bounds', 'extent', 'pilot_boundary', 'study_area', 'pilot_area']):
                        bbox_found.append(f"{prefix}{k}: {v}")
                    elif isinstance(v, (dict, list)):
                        find_bbox(v, prefix=f"{prefix}{k}.", depth=depth+1)
            elif isinstance(d, list) and len(d) > 0 and isinstance(d[0], dict):
                find_bbox(d[0], prefix=f"{prefix}[0].", depth=depth+1)

        find_bbox(data)
        print(f"File: {mf}")
        for b in bbox_found[:5]:
            print(f"   -> {b}")
        if not bbox_found:
            print("   -> (no direct bbox key found)")

print("\n--- Finished Scan ---")
