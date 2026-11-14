import os
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
import numpy as np
from PIL import Image

dem_path = r"C:\AquaPredict_tests\dem\stratmap18-1m_2995143c3.tif"
pilot_wgs84 = (-95.3750, 29.7560, -95.3650, 29.7650) # west, south, east, north

with rasterio.open(dem_path) as src:
    dst_crs = 'EPSG:4326'
    # Define destination bounds and resolution (~1 meter in degrees is approx 0.00001 deg)
    dst_width = 1000
    dst_height = 1000
    dst_transform = rasterio.transform.from_bounds(*pilot_wgs84, dst_width, dst_height)
    
    destination = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
    
    reproject(
        source=rasterio.band(src, 1),
        destination=destination,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
        dst_nodata=np.nan
    )
    
    valid_mask = ~np.isnan(destination)
    min_elev = np.nanmin(destination)
    max_elev = np.nanmax(destination)
    print(f"Reprojected DEM to WGS84: shape {destination.shape}")
    print(f"Min elevation: {min_elev:.2f} m, Max elevation: {max_elev:.2f} m, Mean: {np.nanmean(destination):.2f} m")
    print(f"Valid pixels: {np.sum(valid_mask)} / {destination.size} ({np.sum(valid_mask)/destination.size*100:.1f}%)")
