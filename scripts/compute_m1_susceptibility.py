import os
import json
import numpy as np
import rasterio
from rasterio.warp import transform, reproject, Resampling
from scipy import ndimage
from scipy.spatial import KDTree
from PIL import Image

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_SRC_DIR = r"C:\AquaPredict_tests"
OUTPUT_DATA_DIR = os.path.join(WORKSPACE_DIR, "public", "data")
os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)

PILOT_BBOX = {
    "west": -95.3750,
    "south": 29.7560,
    "east": -95.3650,
    "north": 29.7650
}

dem_path = os.path.join(DATA_SRC_DIR, "dem", "stratmap18-1m_2995143c3.tif")

print("==========================================================")
print(" AquaPredict M1 - Terrain-Based Waterlogging Susceptibility")
print("==========================================================")
print(f"Reading DEM: {dem_path}")

grid_w = 800
grid_h = 800
dst_transform = rasterio.transform.from_bounds(
    PILOT_BBOX["west"], PILOT_BBOX["south"], PILOT_BBOX["east"], PILOT_BBOX["north"],
    grid_w, grid_h
)
dem = np.full((grid_h, grid_w), np.nan, dtype=np.float32)

with rasterio.open(dem_path) as src:
    reproject(
        source=rasterio.band(src, 1),
        destination=dem,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=dst_transform,
        dst_crs='EPSG:4326',
        resampling=Resampling.bilinear,
        dst_nodata=np.nan
    )

valid_mask = ~np.isnan(dem)
min_elev = float(np.nanmin(dem))
max_elev = float(np.nanmax(dem))
mean_elev = float(np.nanmean(dem))
print(f"DEM loaded: min={min_elev:.2f}m, max={max_elev:.2f}m, mean={mean_elev:.2f}m")

# ----------------------------------------------------
# 1. Slope & Flatness Calculation
# ----------------------------------------------------
print("1. Calculating surface slope...")
dx = (PILOT_BBOX["east"] - PILOT_BBOX["west"]) * 96500.0 / grid_w
dy = (PILOT_BBOX["north"] - PILOT_BBOX["south"]) * 111000.0 / grid_h
d_elev_y, d_elev_x = np.gradient(dem, dy, dx)
slope_rad = np.arctan(np.sqrt(d_elev_x**2 + d_elev_y**2))
slope_deg = np.degrees(slope_rad)

# Flatness score (0 to 1): slopes < 1° -> 1.0; slopes > 3.5° -> 0.0
score_slope = np.clip(1.0 - (slope_deg - 0.5) / 3.0, 0.0, 1.0)

# ----------------------------------------------------
# 2. Topographic Position Index (TPI) / Relative Elevation
# ----------------------------------------------------
print("2. Calculating Topographic Position Index (TPI)...")
kernel_radius_px = 25  # ~30m radius neighborhood
tpi = dem - ndimage.uniform_filter(dem, size=kernel_radius_px * 2 + 1)

# TPI score (0 to 1): TPI < -1.0m (deep hollow) -> 1.0; TPI > 0.0m (ridge/plain) -> 0.0
score_tpi = np.clip(-tpi / 1.0, 0.0, 1.0)

# ----------------------------------------------------
# 3. Morphological Sinks / Depression Filling
# ----------------------------------------------------
print("3. Performing morphological depression detection...")
def fill_depressions(elevation, max_iters=1500):
    h_max = np.nanmax(elevation)
    mask = h_max - elevation
    seed = np.zeros_like(mask)
    seed[0, :] = mask[0, :]
    seed[-1, :] = mask[-1, :]
    seed[:, 0] = mask[:, 0]
    seed[:, -1] = mask[:, -1]
    
    filled = seed.copy()
    for it in range(max_iters):
        dilated = ndimage.grey_dilation(filled, size=(3, 3))
        new_filled = np.minimum(dilated, mask)
        if np.array_equal(new_filled, filled):
            print(f"  Depression filling converged in {it} iterations")
            break
        filled = new_filled
    return h_max - filled

filled_dem = fill_depressions(dem)
depression_depth = np.maximum(0.0, filled_dem - dem)
# Depression score (0 to 1): depth >= 0.25m -> 1.0; depth < 0.05m -> 0.0
score_depression = np.clip((depression_depth - 0.04) / 0.25, 0.0, 1.0)
print(f"  Max depression depth: {np.max(depression_depth):.2f}m")

# ----------------------------------------------------
# 4. Drainage Proximity (Metric Distance to Nearest Inlet)
# ----------------------------------------------------
print("4. Calculating metric proximity to storm inlets...")
inlets_path = os.path.join(OUTPUT_DATA_DIR, "inlets.geojson")
with open(inlets_path, "r", encoding="utf-8") as f:
    inlets_fc = json.load(f)

inlet_coords = np.array([feat["geometry"]["coordinates"] for feat in inlets_fc["features"]])
# Transform inlet coords to UTM 15N (EPSG:6344) meters
inlet_xs, inlet_ys = transform('EPSG:4326', 'EPSG:6344', inlet_coords[:, 0], inlet_coords[:, 1])
inlet_pts_utm = np.column_stack([inlet_xs, inlet_ys])

# Meshgrid coordinates in UTM
lon_line = np.linspace(PILOT_BBOX["west"], PILOT_BBOX["east"], grid_w)
lat_line = np.linspace(PILOT_BBOX["north"], PILOT_BBOX["south"], grid_h)
grid_lons, grid_lats = np.meshgrid(lon_line, lat_line)
grid_xs, grid_ys = transform('EPSG:4326', 'EPSG:6344', grid_lons.ravel(), grid_lats.ravel())
grid_pts_utm = np.column_stack([grid_xs, grid_ys])

kdtree = KDTree(inlet_pts_utm)
dists, _ = kdtree.query(grid_pts_utm)
dist_to_inlet_m = dists.reshape((grid_h, grid_w)).astype(np.float32)

# Inlet distance score (0 to 1): > 80m -> 1.0; < 20m -> 0.0
score_inlet_dist = np.clip((dist_to_inlet_m - 20.0) / 60.0, 0.0, 1.0)
print(f"  Inlet distance: min={np.min(dist_to_inlet_m):.1f}m, max={np.max(dist_to_inlet_m):.1f}m, mean={np.mean(dist_to_inlet_m):.1f}m")

# ----------------------------------------------------
# 5. Composite Exploratory Waterlogging Susceptibility Index (EWSI)
# ----------------------------------------------------
print("5. Computing Composite Exploratory Waterlogging Susceptibility Index (EWSI)...")
# Weighting:
# Depression presence: 0.35 (strongest physical pooling constraint)
# Relative Low / TPI: 0.25 (valley/swale effect)
# Slope Flatness: 0.20 (sluggish surface conveyance)
# Inlet Distance: 0.20 (surface drainage access distance)
ewsi_score = (
    0.35 * score_depression +
    0.25 * score_tpi +
    0.20 * score_slope +
    0.20 * score_inlet_dist
)
ewsi_score = np.clip(ewsi_score, 0.0, 1.0)

# Categorize into 4 explainable susceptibility tiers:
# Low: < 0.30
# Moderate: 0.30 - 0.50
# Elevated: 0.50 - 0.70
# High: >= 0.70
pct_low = float(np.sum(ewsi_score < 0.30) / ewsi_score.size * 100)
pct_mod = float(np.sum((ewsi_score >= 0.30) & (ewsi_score < 0.50)) / ewsi_score.size * 100)
pct_elev = float(np.sum((ewsi_score >= 0.50) & (ewsi_score < 0.70)) / ewsi_score.size * 100)
pct_high = float(np.sum(ewsi_score >= 0.70) / ewsi_score.size * 100)

print(f"  Tier Breakdown:")
print(f"    Low Susceptibility:      {pct_low:.1f}%")
print(f"    Moderate Susceptibility: {pct_mod:.1f}%")
print(f"    Elevated Susceptibility: {pct_elev:.1f}%")
print(f"    High Susceptibility:     {pct_high:.1f}%")

# ----------------------------------------------------
# 6. Render Geo-Referenced Raster Overlays (PNG)
# ----------------------------------------------------
print("6. Rendering raster overlays...")

# A. Susceptibility Map (Color-coded RGBA)
# Low: Sage/Emerald [34, 197, 94]
# Moderate: Yellow/Amber [234, 179, 8]
# Elevated: Orange/Coral [249, 115, 22]
# High: Crimson/Rose [225, 29, 72]
rgba_susc = np.zeros((grid_h, grid_w, 4), dtype=np.uint8)

# Continuous multi-stop color blending for smooth transitions
stops = [0.0, 0.30, 0.50, 0.70, 1.0]
colors = np.array([
    [34, 197, 94],    # Low (Emerald)
    [132, 204, 22],   # Mild (Lime)
    [234, 179, 8],    # Moderate (Amber-Yellow)
    [249, 115, 22],   # Elevated (Orange)
    [225, 29, 72]     # High (Crimson)
], dtype=np.float32)

rgb_susc = np.zeros((grid_h, grid_w, 3), dtype=np.float32)
for c in range(3):
    rgb_susc[:, :, c] = np.interp(ewsi_score, stops, colors[:, c])

# Vary alpha slightly by score: low areas are softer (140), high areas are prominent (215)
alpha_susc = np.interp(ewsi_score, [0.0, 0.3, 0.7, 1.0], [130, 160, 200, 225]).astype(np.uint8)
rgba_susc[:, :, :3] = np.clip(rgb_susc, 0, 255).astype(np.uint8)
rgba_susc[:, :, 3] = alpha_susc

img_susc = Image.fromarray(rgba_susc, 'RGBA')
susc_png_path = os.path.join(OUTPUT_DATA_DIR, "susceptibility.png")
img_susc.save(susc_png_path, "PNG", optimize=True)
print(f"  Saved {os.path.basename(susc_png_path)}")

# B. Depressions Raster Overlay (Ponding Sinks)
# Highlights enclosed sinks where depression depth > 0.05m
rgba_dep = np.zeros((grid_h, grid_w, 4), dtype=np.uint8)
dep_norm = np.clip(depression_depth / 1.0, 0.0, 1.0)
# Deep cyan-blue pooling color: [6, 182, 212] -> [30, 64, 175]
dep_mask = depression_depth >= 0.04
rgba_dep[dep_mask, 0] = (14 + 16 * dep_norm[dep_mask]).astype(np.uint8)
rgba_dep[dep_mask, 1] = (165 - 80 * dep_norm[dep_mask]).astype(np.uint8)
rgba_dep[dep_mask, 2] = (233 - 50 * dep_norm[dep_mask]).astype(np.uint8)
rgba_dep[dep_mask, 3] = np.clip(160 + dep_norm[dep_mask] * 70, 0, 230).astype(np.uint8)

img_dep = Image.fromarray(rgba_dep, 'RGBA')
dep_png_path = os.path.join(OUTPUT_DATA_DIR, "depressions.png")
img_dep.save(dep_png_path, "PNG", optimize=True)
print(f"  Saved {os.path.basename(dep_png_path)}")

# C. Inlet Proximity Raster Overlay (Distance Rings)
rgba_prox = np.zeros((grid_h, grid_w, 4), dtype=np.uint8)
prox_norm = np.clip(dist_to_inlet_m / 120.0, 0.0, 1.0)
# Gradient: Teal (near < 25m) -> Purple (far > 80m)
rgba_prox[:, :, 0] = (20 + prox_norm * 160).astype(np.uint8)
rgba_prox[:, :, 1] = (180 - prox_norm * 110).astype(np.uint8)
rgba_prox[:, :, 2] = (160 + prox_norm * 80).astype(np.uint8)
rgba_prox[:, :, 3] = (120 + prox_norm * 80).astype(np.uint8)

img_prox = Image.fromarray(rgba_prox, 'RGBA')
prox_png_path = os.path.join(OUTPUT_DATA_DIR, "inlet_proximity.png")
img_prox.save(prox_png_path, "PNG", optimize=True)
print(f"  Saved {os.path.basename(prox_png_path)}")

# ----------------------------------------------------
# 7. Generate Downsampled Lookup Grid (100x100) for UI Inspector
# ----------------------------------------------------
print("7. Generating downsampled lookup grid for client-side factor inspection...")
sample_h = 100
sample_w = 100

def resample_arr(arr):
    img = Image.fromarray(arr)
    return np.array(img.resize((sample_w, sample_h), Image.Resampling.BILINEAR))

dem_s = resample_arr(dem)
slope_s = resample_arr(slope_deg)
tpi_s = resample_arr(tpi)
dep_s = resample_arr(depression_depth)
dist_s = resample_arr(dist_to_inlet_m)
ewsi_s = resample_arr(ewsi_score)

grid_cells = []
for r in range(sample_h):
    row_data = []
    for c in range(sample_w):
        score_val = round(float(ewsi_s[r, c]), 3)
        tier = "Low"
        if score_val >= 0.70:
            tier = "High"
        elif score_val >= 0.50:
            tier = "Elevated"
        elif score_val >= 0.30:
            tier = "Moderate"
            
        row_data.append({
            "elev": round(float(dem_s[r, c]), 2),
            "slope": round(float(slope_s[r, c]), 1),
            "tpi": round(float(tpi_s[r, c]), 2),
            "dep": round(float(dep_s[r, c]), 2),
            "inlet_dist": round(float(dist_s[r, c]), 1),
            "score": score_val,
            "tier": tier
        })
    grid_cells.append(row_data)

grid_json_path = os.path.join(OUTPUT_DATA_DIR, "susceptibility_grid.json")
with open(grid_json_path, "w", encoding="utf-8") as f:
    json.dump({
        "bbox": PILOT_BBOX,
        "rows": sample_h,
        "cols": sample_w,
        "grid": grid_cells
    }, f)
print(f"  Saved {os.path.basename(grid_json_path)}")

# ----------------------------------------------------
# 8. M1 Methodology & Analysis Metadata
# ----------------------------------------------------
print("8. Saving M1 Analysis Metadata...")
meta = {
    "title": "AquaPredict M1 Exploratory Waterlogging Susceptibility Analysis",
    "disclaimer": "EXPLORATORY WATERLOGGING SUSCEPTIBILITY — NOT A VALIDATED FLOOD FORECAST",
    "pilot_boundary": PILOT_BBOX,
    "pilot_area_km2": 0.97,
    "elevation_model": {
        "source": "NOAA 2018 Coastal Texas DEM (StratMap18 1-meter)",
        "resolution": "1 metre",
        "vertical_datum": "UNVERIFIED - Raw relative elevation",
        "min_elev_m": round(min_elev, 2),
        "max_elev_m": round(max_elev, 2),
        "mean_elev_m": round(mean_elev, 2)
    },
    "indicators": {
        "terrain_depressions": {
            "name": "Local Topographic Depressions (Ponding Sinks)",
            "method": "Morphological reconstruction sink filling on 1m DEM",
            "max_depression_depth_m": round(float(np.max(depression_depth)), 2),
            "sink_area_pct": round(float(np.sum(depression_depth > 0.05) / depression_depth.size * 100), 1),
            "weight": 0.35,
            "rationale": "Closed topographical depressions collect overland runoff before spilling over."
        },
        "relative_elevation": {
            "name": "Topographic Position Index (TPI)",
            "method": "Elevation relative to 30m moving neighborhood mean",
            "kernel_radius_m": 30,
            "weight": 0.25,
            "rationale": "Identifies local swales, hollows, and valleys regardless of absolute sea level elevation."
        },
        "slope_flatness": {
            "name": "Surface Slope Flatness",
            "method": "Terrain gradient magnitude in degrees",
            "mean_slope_deg": round(float(np.mean(slope_deg)), 1),
            "flat_area_pct": round(float(np.sum(slope_deg < 1.5) / slope_deg.size * 100), 1),
            "weight": 0.20,
            "rationale": "Slopes < 1.5° impede overland runoff evacuation velocity and promote surface ponding."
        },
        "drainage_proximity": {
            "name": "Distance to Nearest Storm Inlet",
            "method": "CRS-aware 2D Euclidean distance to nearest City of Houston storm inlet",
            "crs_used": "EPSG:6344 (UTM 15N Metric Coordinates)",
            "total_inlets_evaluated": len(inlet_coords),
            "mean_inlet_distance_m": round(float(np.mean(dist_to_inlet_m)), 1),
            "weight": 0.20,
            "rationale": "Screening indicator for overland flow path travel distance to mapped municipal intake points."
        }
    },
    "tier_distribution_pct": {
        "Low": round(pct_low, 1),
        "Moderate": round(pct_mod, 1),
        "Elevated": round(pct_elev, 1),
        "High": round(pct_high, 1)
    },
    "limitations_and_guardrails": [
        "Screening Tool Only: This analysis highlights terrain-based ponding tendencies; it is NOT a certified 1D/2D hydrodynamic model or real-time flood warning system.",
        "DEM Artifacts: Highway overpasses, bridges, or culverts not burned into the raw LiDAR may create false artificial dams in depression calculations.",
        "Subsurface Drainage Not Modeled: Proximity to an inlet does not evaluate whether that inlet or pipe has hydraulic capacity, is clogged, or suffers from bayou backwater.",
        "Rainfall Excluded: No rainfall intensity or storm events (e.g. 10-yr, 100-yr) are modeled in this milestone.",
        "Pilot Domain Restriction: Analysis is strictly confined to the 0.97 km² Downtown Houston study sector and cannot be extrapolated citywide."
    ]
}

meta_path = os.path.join(OUTPUT_DATA_DIR, "m1_analysis_meta.json")
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
print(f"  Saved {os.path.basename(meta_path)}")
print("==========================================================")
print("M1 Analysis Completed Successfully!")
