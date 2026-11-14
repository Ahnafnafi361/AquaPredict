import os
import rasterio
from rasterio.warp import transform, reproject, Resampling
import numpy as np

dem_path = r"C:\AquaPredict_tests\dem\stratmap18-1m_2995143c3.tif"

# Pilot bounds in WGS84
# West: -95.3750, South: 29.7560, East: -95.3650, North: 29.7650
pilot_bounds_wgs84 = (-95.3750, 29.7560, -95.3650, 29.7650)

with rasterio.open(dem_path) as src:
    print("DEM src CRS:", src.crs)
    print("DEM src bounds:", src.bounds)
    print("DEM src nodata:", src.nodata)
    
    # Reproject pilot corners to DEM CRS
    xs, ys = transform('EPSG:4326', src.crs, [pilot_bounds_wgs84[0], pilot_bounds_wgs84[2]], [pilot_bounds_wgs84[1], pilot_bounds_wgs84[3]])
    print("Pilot bbox in DEM CRS:", xs, ys)
    
    # Read window
    row_start, col_start = src.index(xs[0], ys[1]) # top-left
    row_end, col_end = src.index(xs[1], ys[0])     # bottom-right
    print(f"Pixel window: rows {row_start} to {row_end}, cols {col_start} to {col_end}")
    
    window = rasterio.windows.Window(col_start, row_start, col_end - col_start, row_end - row_start)
    elev = src.read(1, window=window)
    print(f"Elevation grid shape: {elev.shape}")
    print(f"Min: {np.nanmin(elev):.2f}, Max: {np.nanmax(elev):.2f}, Mean: {np.nanmean(elev):.2f}")
