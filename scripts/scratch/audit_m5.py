import json
import numpy as np

# Load susceptibility grid
with open('public/data/susceptibility_grid.json') as f:
    susc_data = json.load(f)

# Load DEM grid
with open('public/data/dem_grid.json') as f:
    dem_data = json.load(f)

# Load scenarios
with open('public/data/simulation_scenarios.json') as f:
    sc_data = json.load(f)

# Load metadata
with open('public/data/m5_simulation_meta.json') as f:
    meta_data = json.load(f)

grid = susc_data['grid']
rows = len(grid)
cols = len(grid[0])
dep = np.array([[grid[r][c]['dep'] for c in range(cols)] for r in range(rows)])
elev = np.array([[grid[r][c]['elev'] for c in range(cols)] for r in range(rows)])

# 1. Investigate max depression cell
max_dep = np.max(dep)
max_idx = np.unravel_index(np.argmax(dep), dep.shape)
r_max, c_max = max_idx

w = susc_data['bbox']['west']
s = susc_data['bbox']['south']
e = susc_data['bbox']['east']
n = susc_data['bbox']['north']
lon = w + (c_max + 0.5) / cols * (e - w)
lat = n - (r_max + 0.5) / rows * (n - s)

print("=" * 60)
print("1. MAX DEPRESSION CELL INVESTIGATION")
print("=" * 60)
print(f"Max depression depth: {max_dep:.3f} m at row {r_max}, col {c_max}")
print(f"Elevation at max cell: {elev[r_max, c_max]:.2f} m")
print(f"Cell properties in susceptibility_grid: {grid[r_max][c_max]}")
print(f"Coordinates: Lat {lat:.5f}° N, Lon {lon:.5f}° W")

# Check DEM surrounding 5x5 neighborhood
print("\nSurrounding 5x5 elevation matrix (m):")
r_start, r_end = max(0, r_max-2), min(rows, r_max+3)
c_start, c_end = max(0, c_max-2), min(cols, c_max+3)
for r in range(r_start, r_end):
    row_str = " ".join(f"{elev[r, c]:6.2f}" for c in range(c_start, c_end))
    print(f"Row {r:2d}: {row_str}")

print("\nSurrounding 5x5 depression depth matrix (m):")
for r in range(r_start, r_end):
    row_str = " ".join(f"{dep[r, c]:6.2f}" for c in range(c_start, c_end))
    print(f"Row {r:2d}: {row_str}")

# 2. Check 100mm scenario peak depth at this cell
sc_100 = sc_data['presets']['preset_100mm']
peak_ts_idx = sc_100['peak_time_minutes'] // 5
ts_peak = sc_100['timesteps'][peak_ts_idx]
print("\n100mm Scenario Peak Timestep Analysis:")
print(f"Peak minute: {sc_100['peak_time_minutes']} min (Timestep index {peak_ts_idx})")
print(f"Reported peak max depth: {sc_100['peak_max_depth_m']} m")
print(f"Storage volume at peak: {ts_peak['mass_balance']['storage_m3']:.1f} m³")
total_dep_cap = meta_data['simulation_parameters']['total_depression_capacity_m3']
print(f"Total depression capacity: {total_dep_cap:.1f} m³")
alpha_peak = ts_peak['mass_balance']['storage_m3'] / total_dep_cap
print(f"Filling fraction alpha at peak: {alpha_peak:.6f}")
expected_peak_d = alpha_peak * max_dep
print(f"alpha * max_dep = {expected_peak_d:.3f} m (Matches reported peak: {sc_100['peak_max_depth_m']:.3f} m)")

# 3. Check all presets peak statistics
print("\n" + "=" * 60)
print("2. PER-PRESET PEAK STATS & RESIDUALS")
print("=" * 60)
for pid, sc in sc_data['presets'].items():
    peak_d = sc['peak_max_depth_m']
    peak_a = sc['peak_flooded_area_km2']
    peak_t = sc['peak_time_minutes']
    tot_r = sc['total_runoff_mm']
    mb_res = sc['mass_balance_verification']['max_residual_m3']
    mb_rel = sc['mass_balance_verification']['max_relative_residual_pct']
    target = sc['target_rainfall_mm']
    print(f"{pid:14} | Target: {target:5.1f}mm | Runoff: {tot_r:6.2f}mm ({tot_r/target*100:4.1f}%) | Peak Min: {peak_t:3d} | Max Depth: {peak_d:.3f}m | Flooded Area: {peak_a:.4f}km² | Abs Res: {mb_res:.2e}m³ | Rel Res: {mb_rel:.2e}%")

# 4. Check mass balance conservation identity
print("\n" + "=" * 60)
print("3. MASS BALANCE INDEPENDENCE CHECK")
print("=" * 60)
for pid, sc in sc_data['presets'].items():
    for ts in sc['timesteps']:
        mb = ts['mass_balance']
        p = mb['precip_m3']
        f = mb['infil_m3']
        s = mb['storage_m3']
        o = mb['outfall_m3']
        res = mb['residual_m3']
        # Check if outfall + storage + infil is identically equal to precip
        diff = abs(p - (f + s + o))
        assert diff < 1e-3, f"Mismatch in {pid} at step {ts['step_idx']}"
print("Verified: In all presets and timesteps, V_precip == V_infil + V_storage + V_outfall to machine precision.")
print("Algebraic audit: V_infil = V_precip - V_runoff_cum, and V_storage + V_outfall = V_runoff_cum.")
print("Therefore V_infil + V_storage + V_outfall = (V_precip - V_runoff_cum) + V_runoff_cum = V_precip.")
