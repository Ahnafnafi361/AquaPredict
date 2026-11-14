import os
import json
import numpy as np
import rasterio
from rasterio.warp import transform, reproject, Resampling
from scipy import ndimage
from scipy.spatial import KDTree

DATA_SRC_DIR = r"C:\AquaPredict_tests"
PILOT_BBOX = {
    "west": -95.3750,
    "south": 29.7560,
    "east": -95.3650,
    "north": 29.7650
}

dem_path = os.path.join(DATA_SRC_DIR, "dem", "stratmap18-1m_2995143c3.tif")

print("--- Testing M1 Terrain & Drainage Analysis ---")
with rasterio.open(dem_path) as src:
    print(f"DEM CRS: {src.crs}, Resolution: {src.res}")
    
    # Reproject to pilot grid in EPSG:4326 (800x800)
    # 800x800 over 0.01 deg lon x 0.009 deg lat -> ~1.2m cell size
    grid_w = 800
    grid_h = 800
    dst_transform = rasterio.transform.from_bounds(
        PILOT_BBOX["west"], PILOT_BBOX["south"], PILOT_BBOX["east"], PILOT_BBOX["north"],
        grid_w, grid_h
    )
    dem = np.full((grid_h, grid_w), np.nan, dtype=np.float32)
    
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

print(f"DEM shape: {dem.shape}, Min: {np.nanmin(dem):.2f}m, Max: {np.nanmax(dem):.2f}m, Mean: {np.nanmean(dem):.2f}m")

# 1. Slope Calculation (in meters)
dx = (PILOT_BBOX["east"] - PILOT_BBOX["west"]) * 96500.0 / grid_w
dy = (PILOT_BBOX["north"] - PILOT_BBOX["south"]) * 111000.0 / grid_h
d_elev_y, d_elev_x = np.gradient(dem, dy, dx)
slope_rad = np.arctan(np.sqrt(d_elev_x**2 + d_elev_y**2))
slope_deg = np.degrees(slope_rad)
print(f"Slope (deg): Min: {np.min(slope_deg):.2f}°, Max: {np.max(slope_deg):.2f}°, Mean: {np.mean(slope_deg):.2f}°")
print(f"Flat areas (< 1.5°): {np.sum(slope_deg < 1.5) / slope_deg.size * 100:.1f}%")

# 2. Relative Elevation / TPI (Topographic Position Index)
# Kernel size ~ 40m radius (~33 pixels)
kernel_radius_px = 25 # ~30 meters
tpi = dem - ndimage.uniform_filter(dem, size=kernel_radius_px*2+1)
print(f"TPI (m): Min: {np.min(tpi):.2f}m, Max: {np.max(tpi):.2f}m, Mean: {np.mean(tpi):.2f}m")
print(f"Local hollows (TPI < -0.5m): {np.sum(tpi < -0.5) / tpi.size * 100:.1f}%")

# 3. Morphological Sinks / Depression Filling (Priority-Flood / Morphological Reconstruction)
# For raster sink filling:
def fill_depressions(elevation, max_iters=2000):
    """
    Morphological reconstruction by erosion of a marker image that equals
    the DEM on boundary and +inf in interior.
    """
    marker = np.full_like(elevation, np.nanmax(elevation))
    # Boundary pixels retain raw elevation
    marker[0, :] = elevation[0, :]
    marker[-1, :] = elevation[-1, :]
    marker[:, 0] = elevation[:, 0]
    marker[:, -1] = elevation[:, -1]
    
    # 8-connectivity footprint
    footprint = np.ones((3, 3), dtype=bool)
    
    # Fast reconstruction: iterative minimum filter bounded below by raw elevation
    # Using scipy morphological reconstruction by erosion on inverted heights
    # Alternatively: inverted DEM reconstruction
    # Invert: h_inv = max_elev - dem
    # Mask = h_inv
    # Marker: interior = 0, boundary = h_inv
    h_max = np.nanmax(elevation)
    mask = h_max - elevation
    seed = np.zeros_like(mask)
    seed[0, :] = mask[0, :]
    seed[-1, :] = mask[-1, :]
    seed[:, 0] = mask[:, 0]
    seed[:, -1] = mask[:, -1]
    
    # Dilate seed restricted by mask
    reconstructed = ndimage.binary_dilation # wait, grey_dilation
    # Let's test scipy grey_dilation reconstruction or iterative dilation
    filled = seed.copy()
    for it in range(max_iters):
        dilated = ndimage.grey_dilation(filled, size=(3, 3))
        new_filled = np.minimum(dilated, mask)
        if np.array_equal(new_filled, filled):
            print(f"Morphological fill converged in {it} iterations")
            break
        filled = new_filled
    else:
        print("Reached max iterations in sink filling")
        
    filled_dem = h_max - filled
    return filled_dem

filled_dem = fill_depressions(dem, max_iters=1500)
dep_depth = np.maximum(0, filled_dem - dem)
print(f"Depression depth (m): Max: {np.max(dep_depth):.2f}m, Sinks count (>5cm): {np.sum(dep_depth > 0.05)}")
print(f"Depression area (>10cm depth): {np.sum(dep_depth > 0.10) / dep_depth.size * 100:.2f}%")

# 4. Inlets Proximity (in meters)
with open("public/data/inlets.geojson", "r") as f:
    inlets_fc = json.load(f)

# Collect inlet coordinates in WGS84 and convert to grid pixel coords or metric distance
inlet_coords = np.array([feat["geometry"]["coordinates"] for feat in inlets_fc["features"]])
print(f"Total inlets: {len(inlet_coords)}")

# Create coordinate meshgrid in meters
lon_line = np.linspace(PILOT_BBOX["west"], PILOT_BBOX["east"], grid_w)
lat_line = np.linspace(PILOT_BBOX["north"], PILOT_BBOX["south"], grid_h) # row 0 is North
# Convert lon/lat to UTM 15N (EPSG:6344) meters
inlet_xs, inlet_ys = transform('EPSG:4326', 'EPSG:6344', inlet_coords[:, 0], inlet_coords[:, 1])
inlet_pts_utm = np.column_stack([inlet_xs, inlet_ys])

# Meshgrid corners in UTM
grid_lons, grid_lats = np.meshgrid(lon_line, lat_line)
grid_xs, grid_ys = transform('EPSG:4326', 'EPSG:6344', grid_lons.ravel(), grid_lats.ravel())
grid_pts_utm = np.column_stack([grid_xs, grid_ys])

kdtree = KDTree(inlet_pts_utm)
dists, _ = kdtree.query(grid_pts_utm)
dist_to_inlet_m = dists.reshape((grid_h, grid_w)).astype(np.float32)

print(f"Distance to nearest inlet (m): Min: {np.min(dist_to_inlet_m):.1f}m, Max: {np.max(dist_to_inlet_m):.1f}m, Mean: {np.mean(dist_to_inlet_m):.1f}m")
print(f"Areas within 25m of inlet: {np.sum(dist_to_inlet_m <= 25) / dist_to_inlet_m.size * 100:.1f}%")
print(f"Areas > 75m from inlet: {np.sum(dist_to_inlet_m > 75) / dist_to_inlet_m.size * 100:.1f}%")
