import os
import json
import glob
import pandas as pd
import rasterio

DATA_DIR = r"C:\AquaPredict_tests"

print("--- Inspecting GIS GeoJSON / ArcGIS JSON Files ---")
for name in ["Discharge", "GravityMains", "Inlets", "Manholes"]:
    path = os.path.join(DATA_DIR, f"feat_{name}.json")
    if os.path.exists(path):
        size_kb = os.path.getsize(path) / 1024
        # check encoding
        for enc in ['utf-8', 'utf-16', 'utf-8-sig']:
            try:
                with open(path, 'r', encoding=enc) as f:
                    data = json.load(f)
                    sr = data.get("spatialReference", {})
                    features = data.get("features", [])
                    print(f"[{name}] (Encoding: {enc}, Size: {size_kb:.1f} KB):")
                    print(f"  Feature count: {len(features)}")
                    print(f"  Spatial Reference: {sr}")
                    if features:
                        f0 = features[0]
                        geom = f0.get("geometry", {})
                        geom_type = "Point" if "x" in geom else ("Polyline/Polygon" if ("paths" in geom or "rings" in geom) else list(geom.keys()))
                        print(f"  Geometry format: {geom_type}, Keys: {list(geom.keys())}")
                        print(f"  Attributes sample ({len(f0.get('attributes', {}))} attributes): {list(f0.get('attributes', {}).keys())[:8]}")
                    break
            except Exception as e:
                continue

print("\n--- Inspecting Completeness Files ---")
for f in glob.glob(os.path.join(DATA_DIR, "completeness_*.csv")):
    df = pd.read_csv(f)
    print(f"\n{os.path.basename(f)}: shape {df.shape}")
    print(df.head(10).to_string())

print("\n--- Inspecting DEM Files ---")
dem_files = glob.glob(os.path.join(DATA_DIR, "dem", "*.tif"))
for dem in dem_files:
    with rasterio.open(dem) as src:
        print(f"\nDEM: {os.path.basename(dem)}")
        print(f"  CRS: {src.crs}")
        print(f"  Bounds: {src.bounds}")
        print(f"  Width x Height: {src.width} x {src.height}")
        print(f"  Bands: {src.count}")
        print(f"  Transform: {src.transform}")
        print(f"  NoData: {src.nodata}")
