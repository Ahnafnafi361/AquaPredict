import numpy as np
import json
from PIL import Image

# Check dem_grid.json
with open('public/data/dem_grid.json') as f:
    grid_obj = json.load(f)

grid = np.array(grid_obj['grid'])
print("dem_grid shape:", grid.shape)
print("Row 0 (North) elevation mean:", np.mean(grid[0, :]))
print("Row 0 min:", np.min(grid[0, :]), "max:", np.max(grid[0, :]))
print("Row 99 (South) elevation mean:", np.mean(grid[-1, :]))
print("Row 99 min:", np.min(grid[-1, :]), "max:", np.max(grid[-1, :]))

# Let's inspect where min elevation occurs in the grid
min_idx = np.unravel_index(np.argmin(grid), grid.shape)
print("Min elevation in grid:", grid[min_idx], "at (row, col):", min_idx)
# If min is at small row index (near 0), that corresponds to North (Buffalo Bayou)!
# Buffalo Bayou is at North (~29.764 N).

# Let's also check Discharge points latitude
with open('public/data/discharge.geojson') as f:
    dis = json.load(f)
for f in dis['features']:
    print("Discharge point:", f['geometry']['coordinates'], "props:", f['properties']['DISCHRGTYP'])
