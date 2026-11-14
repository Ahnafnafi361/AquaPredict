import os
import json
import glob
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling, transform
from PIL import Image

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_SRC_DIR = r"C:\AquaPredict_tests"
OUTPUT_DATA_DIR = os.path.join(WORKSPACE_DIR, "public", "data")
os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)

# Pilot Area WGS84 Bounding Box from DEM_VERIFICATION.txt
PILOT_BBOX = {
    "west": -95.3750,
    "south": 29.7560,
    "east": -95.3650,
    "north": 29.7650
}

print(f"Starting M0 Data Preparation...")
print(f"Source Directory: {DATA_SRC_DIR}")
print(f"Target Directory: {OUTPUT_DATA_DIR}")

# 1. Pilot Boundary GeoJSON
pilot_poly = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Houston Pilot Area",
                "description": "Selected pilot area in Downtown Houston / Buffalo Bayou",
                "west": PILOT_BBOX["west"],
                "south": PILOT_BBOX["south"],
                "east": PILOT_BBOX["east"],
                "north": PILOT_BBOX["north"],
                "area_km2": 0.97
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [PILOT_BBOX["west"], PILOT_BBOX["south"]],
                    [PILOT_BBOX["east"], PILOT_BBOX["south"]],
                    [PILOT_BBOX["east"], PILOT_BBOX["north"]],
                    [PILOT_BBOX["west"], PILOT_BBOX["north"]],
                    [PILOT_BBOX["west"], PILOT_BBOX["south"]]
                ]]
            }
        }
    ]
}
with open(os.path.join(OUTPUT_DATA_DIR, "pilot_boundary.geojson"), "w", encoding="utf-8") as f:
    json.dump(pilot_poly, f, indent=2)
print("Created pilot_boundary.geojson")

# 2. Process Point Layers (Discharge, Inlets, Manholes)
def process_arcgis_points(layer_name, src_file, out_file):
    with open(src_file, "r", encoding="utf-8-sig") as f:
        src_data = json.load(f)
    
    features = src_data.get("features", [])
    if not features:
        print(f"No features in {layer_name}")
        return
    
    xs = [feat["geometry"]["x"] for feat in features]
    ys = [feat["geometry"]["y"] for feat in features]
    
    # Reproject EPSG:2278 (Texas South Central ftUS) to EPSG:4326 (WGS84)
    lons, lats = transform('EPSG:2278', 'EPSG:4326', xs, ys)
    
    geojson_features = []
    for i, feat in enumerate(features):
        lon = round(lons[i], 6)
        lat = round(lats[i], 6)
        
        # Keep original attributes without altering or fabricating values
        props = dict(feat.get("attributes", {}))
        props["_layer"] = layer_name
        
        geojson_features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        })
    
    fc = {
        "type": "FeatureCollection",
        "name": layer_name,
        "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
        "features": geojson_features
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    print(f"Processed {layer_name}: {len(geojson_features)} features saved to {os.path.basename(out_file)}")

process_arcgis_points("Discharge", os.path.join(DATA_SRC_DIR, "feat_Discharge.json"), os.path.join(OUTPUT_DATA_DIR, "discharge.geojson"))
process_arcgis_points("Inlets", os.path.join(DATA_SRC_DIR, "feat_Inlets.json"), os.path.join(OUTPUT_DATA_DIR, "inlets.geojson"))
process_arcgis_points("Manholes", os.path.join(DATA_SRC_DIR, "feat_Manholes.json"), os.path.join(OUTPUT_DATA_DIR, "manholes.geojson"))

# 3. Process Polyline Layer (Gravity Mains)
def process_gravity_mains(src_file, out_file):
    with open(src_file, "r", encoding="utf-8-sig") as f:
        src_data = json.load(f)
    
    features = src_data.get("features", [])
    
    # Collect all points to transform in batch for speed
    all_x = []
    all_y = []
    feat_index_map = [] # list of (feat_idx, path_idx, pt_count)
    
    for f_idx, feat in enumerate(features):
        paths = feat.get("geometry", {}).get("paths", [])
        for p_idx, path in enumerate(paths):
            count = len(path)
            for pt in path:
                all_x.append(pt[0])
                all_y.append(pt[1])
            feat_index_map.append((f_idx, p_idx, count))
            
    all_lons, all_lats = transform('EPSG:2278', 'EPSG:4326', all_x, all_y)
    
    # Reassemble paths
    pt_cursor = 0
    feature_paths = {f_idx: [] for f_idx in range(len(features))}
    for (f_idx, p_idx, count) in feat_index_map:
        path_coords = []
        for i in range(count):
            path_coords.append([round(all_lons[pt_cursor], 6), round(all_lats[pt_cursor], 6)])
            pt_cursor += 1
        feature_paths[f_idx].append(path_coords)
        
    geojson_features = []
    for f_idx, feat in enumerate(features):
        paths = feature_paths[f_idx]
        if not paths:
            continue
        geom_type = "LineString" if len(paths) == 1 else "MultiLineString"
        coords = paths[0] if len(paths) == 1 else paths
        props = dict(feat.get("attributes", {}))
        props["_layer"] = "GravityMains"
        
        geojson_features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": geom_type,
                "coordinates": coords
            }
        })
        
    fc = {
        "type": "FeatureCollection",
        "name": "GravityMains",
        "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
        "features": geojson_features
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    print(f"Processed GravityMains: {len(geojson_features)} features saved to {os.path.basename(out_file)}")

process_gravity_mains(os.path.join(DATA_SRC_DIR, "feat_GravityMains.json"), os.path.join(OUTPUT_DATA_DIR, "gravity_mains.geojson"))

# 4. Process DEM Raster: Elevation Hypsometric Tint & Hillshade
def process_dem(dem_tif_path, out_terrain_png, out_hillshade_png, out_grid_json, out_meta_json):
    print("Processing DEM raster...")
    with rasterio.open(dem_tif_path) as src:
        # Reproject to WGS84 for the exact pilot bounding box
        grid_w = 800
        grid_h = 800
        dst_transform = rasterio.transform.from_bounds(
            PILOT_BBOX["west"], PILOT_BBOX["south"], PILOT_BBOX["east"], PILOT_BBOX["north"],
            grid_w, grid_h
        )
        dem_data = np.full((grid_h, grid_w), np.nan, dtype=np.float32)
        
        reproject(
            source=rasterio.band(src, 1),
            destination=dem_data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs='EPSG:4326',
            resampling=Resampling.bilinear,
            dst_nodata=np.nan
        )
        
        valid = ~np.isnan(dem_data)
        min_elev = float(np.nanmin(dem_data))
        max_elev = float(np.nanmax(dem_data))
        mean_elev = float(np.nanmean(dem_data))
        print(f"Pilot DEM Elevation range: {min_elev:.2f}m to {max_elev:.2f}m (Mean: {mean_elev:.2f}m)")
        
        # A. Compute Hillshade
        # Approximate pixel size in meters (1 deg lat ~ 111,000m; 1 deg lon ~ 96,500m at 29.76 deg N)
        dx = (PILOT_BBOX["east"] - PILOT_BBOX["west"]) * 96500.0 / grid_w
        dy = (PILOT_BBOX["north"] - PILOT_BBOX["south"]) * 111000.0 / grid_h
        
        # Gradient
        d_elev_y, d_elev_x = np.gradient(dem_data, dy, dx)
        slope = np.pi / 2.0 - np.arctan(np.sqrt(d_elev_x**2 + d_elev_y**2))
        aspect = np.arctan2(-d_elev_x, d_elev_y)
        
        # Light source: 315 deg azimuth (NW), 45 deg altitude
        azimuth = 315.0 * np.pi / 180.0
        altitude = 45.0 * np.pi / 180.0
        shaded = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
        shaded = np.clip(shaded, 0, 1)
        
        # B. Color Map for Hypsometric Elevation Tint
        # Houston Pilot ranges: ~0m to ~18m.
        # Buffalo bayou water channel at < 4m, banks 4-8m, mid-ground 8-12m, high downtown ridges 12-18m
        norm_elev = (dem_data - min_elev) / (max_elev - min_elev + 1e-6)
        norm_elev = np.clip(norm_elev, 0, 1)
        
        # Define smooth custom color ramp:
        # 0.0 -> Deep Bayou Cyan/Teal (0, 75, 110)
        # 0.25 -> Lowland Emerald Green (34, 139, 34)
        # 0.50 -> Mid-elevation Meadow Green/Yellow (180, 195, 45)
        # 0.75 -> Upper Plain Amber Gold (225, 170, 45)
        # 1.0 -> High Downtown Ridge Terracotta / Coral (195, 80, 40)
        stops = [0.0, 0.25, 0.50, 0.75, 1.0]
        colors = np.array([
            [12, 74, 110],    # Deep water / Bayou channel
            [22, 101, 52],    # Riparian floodplain
            [161, 138, 28],   # Transition plain
            [202, 108, 22],   # Urban terrace
            [185, 28, 28]     # Downtown elevation crest
        ], dtype=np.float32)
        
        rgb_color = np.zeros((grid_h, grid_w, 3), dtype=np.float32)
        for c in range(3):
            rgb_color[:, :, c] = np.interp(norm_elev, stops, colors[:, c])
            
        # Blend color with hillshade for realistic 3D terrain texture
        hillshade_mult = 0.55 + 0.65 * shaded[:, :, np.newaxis]
        blended_rgb = np.clip(rgb_color * hillshade_mult, 0, 255).astype(np.uint8)
        
        # Add alpha channel (fully opaque inside pilot)
        alpha = (valid * 235).astype(np.uint8) # slight transparency so streets underneath can peek through
        rgba_terrain = np.dstack([blended_rgb, alpha])
        
        img_terrain = Image.fromarray(rgba_terrain, 'RGBA')
        img_terrain.save(out_terrain_png, "PNG", optimize=True)
        print(f"Saved terrain visualization: {os.path.basename(out_terrain_png)}")
        
        # Pure Hillshade PNG (grayscale with alpha)
        hillshade_gray = (shaded * 255).astype(np.uint8)
        hillshade_alpha = (valid * 200).astype(np.uint8)
        rgba_hillshade = np.dstack([hillshade_gray, hillshade_gray, hillshade_gray, hillshade_alpha])
        img_hill = Image.fromarray(rgba_hillshade, 'RGBA')
        img_hill.save(out_hillshade_png, "PNG", optimize=True)
        print(f"Saved hillshade overlay: {os.path.basename(out_hillshade_png)}")
        
        # C. Downsampled grid for client-side coordinate hover elevation lookup (e.g. 100x100)
        sample_h = 100
        sample_w = 100
        elev_sampled = Image.fromarray(dem_data).resize((sample_w, sample_h), Image.Resampling.BILINEAR)
        elev_arr = np.array(elev_sampled)
        # Round to 2 decimal places and serialize as nested list
        elev_list = [[round(float(val), 2) for val in row] for row in elev_arr]
        
        grid_data = {
            "bbox": PILOT_BBOX,
            "rows": sample_h,
            "cols": sample_w,
            "min_elev_m": round(min_elev, 2),
            "max_elev_m": round(max_elev, 2),
            "mean_elev_m": round(mean_elev, 2),
            "grid": elev_list
        }
        with open(out_grid_json, "w", encoding="utf-8") as f:
            json.dump(grid_data, f)
        print(f"Saved elevation lookup grid: {os.path.basename(out_grid_json)}")
        
        # Metadata
        meta_data = {
            "source": "NOAA 2018 Coastal Texas DEM, Mission 8899 (StratMap18)",
            "tile_used": os.path.basename(dem_tif_path),
            "original_crs": str(src.crs),
            "reprojected_crs": "EPSG:4326 (WGS84)",
            "native_resolution": "1 metre",
            "pilot_bbox_wgs84": PILOT_BBOX,
            "elevation_min_meters": round(min_elev, 2),
            "elevation_max_meters": round(max_elev, 2),
            "elevation_mean_meters": round(mean_elev, 2),
            "elevation_min_feet": round(min_elev * 3.28084, 1),
            "elevation_max_feet": round(max_elev * 3.28084, 1),
            "elevation_mean_feet": round(mean_elev * 3.28084, 1),
            "vertical_datum_status": "UNVERIFIED (Requires survey benchmark calibration)",
            "flood_model_status": "M0 PROTOTYPE VISUALIZATION ONLY (Not calibrated flood prediction)"
        }
        with open(out_meta_json, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)
        print(f"Saved DEM metadata: {os.path.basename(out_meta_json)}")

dem_file = os.path.join(DATA_SRC_DIR, "dem", "stratmap18-1m_2995143c3.tif")
process_dem(
    dem_file,
    os.path.join(OUTPUT_DATA_DIR, "dem_terrain.png"),
    os.path.join(OUTPUT_DATA_DIR, "dem_hillshade.png"),
    os.path.join(OUTPUT_DATA_DIR, "dem_grid.json"),
    os.path.join(OUTPUT_DATA_DIR, "dem_meta.json")
)

# 5. Process Data Quality & Completeness Summaries
def process_quality_data():
    quality_summary = {
        "pilot_extent": {
            "description": "Selected Downtown Houston / Buffalo Bayou Pilot Area",
            "bbox": PILOT_BBOX,
            "disclaimer": "This pilot represents a localized study sector (0.97 km²) and does NOT represent all of Houston."
        },
        "datasets": {
            "gravity_mains": {
                "name": "Storm Gravity Mains",
                "source": "City of Houston GIS Open Data / Public Works",
                "original_crs": "EPSG:2278 (Texas South Central ftUS)",
                "total_records": 624,
                "key_metrics": {}
            },
            "inlets": {
                "name": "Storm Inlets",
                "source": "City of Houston GIS Open Data / Public Works",
                "original_crs": "EPSG:2278 (Texas South Central ftUS)",
                "total_records": 265,
                "key_metrics": {}
            },
            "manholes": {
                "name": "Storm Manholes",
                "source": "City of Houston GIS Open Data / Public Works",
                "original_crs": "EPSG:2278 (Texas South Central ftUS)",
                "total_records": 283,
                "key_metrics": {}
            },
            "discharge": {
                "name": "Discharge / Outfalls",
                "source": "City of Houston GIS Open Data / Public Works",
                "original_crs": "EPSG:2278 (Texas South Central ftUS)",
                "total_records": 4,
                "key_metrics": {}
            },
            "dem": {
                "name": "NOAA Coastal Texas DEM (StratMap18)",
                "source": "NOAA Mission 8899 / Texas Natural Resources Information System (TNRIS)",
                "resolution": "1 metre",
                "horizontal_crs": "EPSG:6344 (Reprojected to EPSG:4326 for web map)",
                "coverage": "100% complete over pilot bounds (0 missing pixels)",
                "vertical_datum": "Unverified - raw elevation values must not be used as survey-grade datum"
            },
            "rainfall": {
                "name": "Precipitation Records",
                "source": "Raw gauge export files in C:\\AquaPredict_tests\\rainfall",
                "status": "UNVERIFIED EXPLORATORY DATA",
                "disclaimer": "Treat rainfall data as unverified. It is strictly excluded from predictive waterlogging routing."
            }
        },
        "scientific_guardrails": [
            "Pilot Boundary Restriction: Visualizations and metrics apply strictly to the 0.97 km² Downtown Houston pilot area.",
            "No Synthetic Connectivity: Drainage network features are preserved in their true raw geometry; no missing links or fictitious pipe connections are invented.",
            "No Calibrated Forecasting: This M0 prototype is an exploratory geospatial risk visualization interface, NOT a certified hydraulic model or real-time flood warning system.",
            "Unverified Rainfall: Rainfall records are exploratory and not validated against radar or NOAA Atlas 14 standards."
        ]
    }
    
    # Read completeness CSVs
    csv_map = {
        "gravity_mains": "completeness_GravityMains.csv",
        "inlets": "completeness_Inlets.csv",
        "manholes": "completeness_Manholes.csv",
        "discharge": "completeness_Discharge.csv"
    }
    
    for key, filename in csv_map.items():
        csv_path = os.path.join(DATA_SRC_DIR, filename)
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            metrics = []
            for _, row in df.iterrows():
                metrics.append({
                    "field": str(row["Field"]),
                    "pct_blank": float(row["PctBlank"]),
                    "pct_zero": float(row["PctZero"]),
                    "completeness_pct": round(100.0 - float(row["PctBlank"]), 1)
                })
            quality_summary["datasets"][key]["metrics"] = metrics
            
    with open(os.path.join(OUTPUT_DATA_DIR, "quality_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(quality_summary, f, indent=2)
    print("Saved quality_metrics.json")

process_quality_data()
print("M0 Data Preparation Completed Successfully!")
