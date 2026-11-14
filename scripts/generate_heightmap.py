"""
AquaPredict - Terrain Heightmap Generator (Milestone M8)
Extracts downsampled elevation grid from DEM GeoTIFF (NOAA StratMap18)
with configurable grid resolution (default 256x256), geographic bounds,
and scientific provenance metadata.
"""

import os
import json
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEM_TIF = r"C:\AquaPredict_tests\dem\stratmap18-1m_2995143c3.tif"
FALLBACK_GRID_JSON = os.path.join(WORKSPACE_DIR, "public", "data", "dem_grid.json")
OUTPUT_HEIGHTMAP_256 = os.path.join(WORKSPACE_DIR, "public", "data", "terrain_heightmap_256.json")

# Pilot Area WGS84 Bounding Box (NOAA StratMap18 Verified Extent)
PILOT_BBOX = {
    "west": -95.3750,
    "south": 29.7560,
    "east": -95.3650,
    "north": 29.7650
}

def extract_heightmap(resolution=256, dem_tif_path=DEFAULT_DEM_TIF):
    """
    Extract elevation grid at specified resolution.
    Returns heightmap dictionary or None if DEM source is completely unavailable.
    Does NOT fabricate artificial elevation or silently replace missing data with zeros.
    """
    # Clamp resolution within safe limits (16 to 512)
    res = max(16, min(512, int(resolution)))
    
    # 1. Primary Source: High-resolution GeoTIFF via rasterio
    if os.path.exists(dem_tif_path):
        try:
            import rasterio
            from rasterio.warp import reproject, Resampling

            with rasterio.open(dem_tif_path) as src:
                dst_transform = rasterio.transform.from_bounds(
                    PILOT_BBOX["west"], PILOT_BBOX["south"],
                    PILOT_BBOX["east"], PILOT_BBOX["north"],
                    res, res
                )
                dem_data = np.full((res, res), np.nan, dtype=np.float32)

                reproject(
                    source=rasterio.band(src, 1),
                    destination=dem_data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear,
                    dst_nodata=np.nan
                )

                valid_mask = ~np.isnan(dem_data)
                if not np.any(valid_mask):
                    return None

                min_elev = float(np.nanmin(dem_data))
                max_elev = float(np.nanmax(dem_data))
                mean_elev = float(np.nanmean(dem_data))

                # Build 2D elevation grid; preserve nulls for missing pixels
                grid = []
                for r in range(res):
                    row_vals = []
                    for c in range(res):
                        val = dem_data[r, c]
                        if np.isnan(val):
                            row_vals.append(None)
                        else:
                            row_vals.append(round(float(val), 2))
                    grid.append(row_vals)

                dx_deg = round((PILOT_BBOX["east"] - PILOT_BBOX["west"]) / (res - 1), 8)
                dy_deg = round((PILOT_BBOX["north"] - PILOT_BBOX["south"]) / (res - 1), 8)

                return {
                    "status": "AVAILABLE",
                    "bounds": PILOT_BBOX,
                    "dimensions": {
                        "rows": res,
                        "cols": res,
                        "dx_deg": dx_deg,
                        "dy_deg": dy_deg
                    },
                    "units": "meters",
                    "min_elev_m": round(min_elev, 2),
                    "max_elev_m": round(max_elev, 2),
                    "mean_elev_m": round(mean_elev, 2),
                    "elevations": grid,
                    "provenance": {
                        "dataset": "NOAA 2018 Coastal Texas DEM, Mission 8899 (StratMap18)",
                        "tile_used": os.path.basename(dem_tif_path),
                        "native_crs": str(src.crs),
                        "reprojected_crs": "EPSG:4326 (WGS84)",
                        "native_resolution": "1 metre",
                        "vertical_datum": "NAVD88 (meters)",
                        "vertical_datum_status": "UNVERIFIED (Requires survey benchmark calibration)",
                        "processing": f"rasterio bilinear downsampling to {res}x{res} grid",
                        "study_area": "Downtown Houston / Buffalo Bayou Pilot (0.97 km²)"
                    }
                }
        except Exception as e:
            print(f"Warning: rasterio extraction failed ({e}), checking fallback...")

    # 2. Secondary Fallback: Resample existing 100x100 dem_grid.json if GeoTIFF missing
    if os.path.exists(FALLBACK_GRID_JSON):
        try:
            from PIL import Image
            with open(FALLBACK_GRID_JSON, "r", encoding="utf-8") as f:
                base_data = json.load(f)

            base_grid = np.array(base_data["grid"], dtype=np.float32)
            img = Image.fromarray(base_grid)
            resized = img.resize((res, res), Image.Resampling.BILINEAR)
            res_arr = np.array(resized)

            grid = [[round(float(val), 2) for val in row] for row in res_arr]
            min_elev = float(np.min(res_arr))
            max_elev = float(np.max(res_arr))
            mean_elev = float(np.mean(res_arr))

            dx_deg = round((PILOT_BBOX["east"] - PILOT_BBOX["west"]) / (res - 1), 8)
            dy_deg = round((PILOT_BBOX["north"] - PILOT_BBOX["south"]) / (res - 1), 8)

            return {
                "status": "AVAILABLE",
                "bounds": PILOT_BBOX,
                "dimensions": {
                    "rows": res,
                    "cols": res,
                    "dx_deg": dx_deg,
                    "dy_deg": dy_deg
                },
                "units": "meters",
                "min_elev_m": round(min_elev, 2),
                "max_elev_m": round(max_elev, 2),
                "mean_elev_m": round(mean_elev, 2),
                "elevations": grid,
                "provenance": {
                    "dataset": "NOAA StratMap18 (Resampled from M0 DEM Grid)",
                    "tile_used": "dem_grid.json",
                    "native_crs": "EPSG:6344",
                    "reprojected_crs": "EPSG:4326 (WGS84)",
                    "native_resolution": "1 metre",
                    "vertical_datum": "NAVD88 (meters)",
                    "vertical_datum_status": "UNVERIFIED (Requires survey benchmark calibration)",
                    "processing": f"bilinear grid resampling to {res}x{res}",
                    "study_area": "Downtown Houston / Buffalo Bayou Pilot (0.97 km²)"
                }
            }
        except Exception as e:
            print(f"Warning: Fallback dem_grid.json extraction failed: {e}")

    # 3. Source completely unavailable: Return explicit unavailable structure without synthetic zeros
    return {
        "status": "UNAVAILABLE",
        "error": "DEM source raster and elevation grid not found",
        "bounds": PILOT_BBOX,
        "dimensions": {
            "rows": 0,
            "cols": 0
        },
        "units": "meters",
        "elevations": None,
        "provenance": {
            "dataset": "NOAA StratMap18",
            "status": "UNAVAILABLE"
        }
    }

def pregenerate_default_heightmap():
    """Generates and writes default 256x256 heightmap to public/data/."""
    os.makedirs(os.path.dirname(OUTPUT_HEIGHTMAP_256), exist_ok=True)
    heightmap = extract_heightmap(resolution=256)
    with open(OUTPUT_HEIGHTMAP_256, "w", encoding="utf-8") as f:
        json.dump(heightmap, f)
    print(f"Pregenerated 256x256 heightmap at {OUTPUT_HEIGHTMAP_256}")
    print(f"Dimensions: {heightmap['dimensions']['rows']}x{heightmap['dimensions']['cols']}, "
          f"Elevation Range: {heightmap.get('min_elev_m')}m to {heightmap.get('max_elev_m')}m")
    return heightmap

if __name__ == "__main__":
    pregenerate_default_heightmap()
