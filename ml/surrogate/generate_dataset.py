"""
AquaPredict Surrogate ML - Dataset Generator (Milestone M9)
Generates synthetic screening simulation training and held-out datasets
by running the deterministic M5 simulation engine across varied:
- Rainfall totals (15 mm to 125 mm)
- Rainfall durations (60 to 240 minutes)
- Temporal hyetograph shapes (front-loaded, central Gaussian, back-loaded, uniform)
- Outfall drainage drawdown rates (0.03 to 0.07 per 5-min step)

CRITICAL DISCLAIMER:
These simulator labels are SYNTHETIC SCREENING ESTIMATES, NOT real-world flood observations.
Data leakage is prevented by splitting strictly across complete simulation scenarios.
"""

import os
import json
import math
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data")
SUSC_GRID_PATH = os.path.join(WORKSPACE_DIR, "public", "data", "susceptibility_grid.json")

# Fixed Random Seed for Reproducibility
RANDOM_SEED = 42

# Domain Constants matching M5
TOTAL_AREA_KM2 = 0.97
TOTAL_AREA_M2 = TOTAL_AREA_KM2 * 1_000_000.0
GRID_ROWS = 100
GRID_COLS = 100
TOTAL_CELLS = GRID_ROWS * GRID_COLS
CELL_AREA_M2 = TOTAL_AREA_M2 / TOTAL_CELLS
CURVE_NUMBER = 88.0
S_MM = (25400.0 / CURVE_NUMBER) - 254.0
IA_MM = 0.2 * S_MM

FEATURE_NAMES = [
    "elev",            # Terrain elevation (meters NAVD88)
    "slope",           # Terrain slope (degrees)
    "tpi",             # Topographic Position Index (meters, hollow/ridge proxy)
    "dep",             # Depression storage depth (meters)
    "inlet_dist",      # Distance to nearest inlet (meters)
    "cn",              # Imperviousness / Curve Number proxy (88.0)
    "rainfall_total",  # Total storm rainfall (mm)
    "duration_min",    # Total storm duration (minutes)
    "time_min",        # Current timestep time (minutes)
    "cum_rain_mm",     # Cumulative rain up to current timestep (mm)
    "intensity_mm_hr", # Current rainfall rate (mm/hr)
    "cum_runoff_mm",   # Cumulative NRCS runoff generated (mm)
    "drain_rate"       # Outfall drawdown fraction
]

def load_cell_features():
    """Load real cell features from public/data/susceptibility_grid.json without fabrication."""
    if not os.path.exists(SUSC_GRID_PATH):
        raise FileNotFoundError(f"Missing susceptibility grid: {SUSC_GRID_PATH}")
    with open(SUSC_GRID_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    grid = data["grid"]
    
    elev_arr = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)
    slope_arr = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)
    tpi_arr = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)
    dep_arr = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)
    inlet_dist_arr = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cell = grid[r][c]
            elev_arr[r, c] = float(cell.get("elev", 0.0))
            slope_arr[r, c] = float(cell.get("slope", 0.0))
            tpi_arr[r, c] = float(cell.get("tpi", 0.0))
            dep_arr[r, c] = max(0.0, float(cell.get("dep", 0.0)))
            inlet_dist_arr[r, c] = float(cell.get("inlet_dist", 0.0))

    return {
        "elev": elev_arr,
        "slope": slope_arr,
        "tpi": tpi_arr,
        "dep": dep_arr,
        "inlet_dist": inlet_dist_arr,
        "cn": np.full((GRID_ROWS, GRID_COLS), CURVE_NUMBER, dtype=np.float32)
    }

def generate_hyetograph_intervals(total_mm, duration_min, peak_fraction, interval_min=5):
    """Generate time-varying hyetograph for given duration and temporal shape."""
    num_intervals = duration_min // interval_min
    t_mid = np.linspace(interval_min / 2.0, duration_min - (interval_min / 2.0), num_intervals)
    peak_min = duration_min * peak_fraction
    sigma_min = max(interval_min * 2.0, duration_min * 0.12)
    
    weights = np.exp(-0.5 * ((t_mid - peak_min) / sigma_min) ** 2)
    sum_w = np.sum(weights)
    if sum_w <= 0.0:
        weights = np.ones(num_intervals) / num_intervals
    else:
        weights /= sum_w
    
    rain_intervals = total_mm * weights
    rain_intervals[-1] += (total_mm - np.sum(rain_intervals))
    return rain_intervals

def compute_nrcs_runoff(cum_rain_mm):
    """Compute NRCS runoff array from cumulative precipitation."""
    cum_runoff = np.zeros_like(cum_rain_mm)
    for i, P in enumerate(cum_rain_mm):
        if P > IA_MM:
            cum_runoff[i] = ((P - IA_MM) ** 2) / (P - IA_MM + S_MM)
        else:
            cum_runoff[i] = 0.0
    return cum_runoff

def run_screening_simulation(total_mm, duration_min, peak_fraction, drain_rate, dep_arr, interval_min=5):
    """Run exact screening simulation model to generate synthetic depth ground-truth frames."""
    rain_intervals = generate_hyetograph_intervals(total_mm, duration_min, peak_fraction, interval_min)
    num_intervals = len(rain_intervals)
    num_timesteps = num_intervals + 1
    
    cum_rain_mm = np.insert(np.cumsum(rain_intervals), 0, 0.0)
    cum_runoff_mm = compute_nrcs_runoff(cum_rain_mm)
    
    vol_runoff_cum = cum_runoff_mm * 1e-3 * TOTAL_AREA_M2
    v_dep_total = float(np.sum(dep_arr) * CELL_AREA_M2)
    
    vol_storage = np.zeros(num_timesteps, dtype=np.float64)
    vol_outfall = np.zeros(num_timesteps, dtype=np.float64)
    
    for s in range(1, num_timesteps):
        delta_runoff_vol = vol_runoff_cum[s] - vol_runoff_cum[s - 1]
        available_vol = vol_storage[s - 1] + delta_runoff_vol
        drain_vol = available_vol * drain_rate
        stored_vol = min(available_vol - drain_vol, v_dep_total)
        spill_vol = max(0.0, (available_vol - drain_vol) - v_dep_total)
        vol_storage[s] = stored_vol
        vol_outfall[s] = vol_outfall[s - 1] + (drain_vol + spill_vol)

    frames = []
    for s in range(num_timesteps):
        t_min = s * interval_min
        stored_m3 = vol_storage[s]
        alpha = (stored_m3 / v_dep_total) if v_dep_total > 0.0 else 0.0
        depth_grid = (alpha * dep_arr).astype(np.float32)
        
        c_rain = float(cum_rain_mm[s])
        c_runoff = float(cum_runoff_mm[s])
        if s > 0:
            r_step = float(rain_intervals[s - 1])
            intensity = r_step * (60.0 / interval_min)
        else:
            intensity = 0.0
            
        frames.append({
            "step_idx": s,
            "time_min": t_min,
            "cum_rain_mm": round(c_rain, 3),
            "intensity_mm_hr": round(intensity, 2),
            "cum_runoff_mm": round(c_runoff, 3),
            "alpha": round(float(alpha), 5),
            "depth_grid": depth_grid
        })

    return frames

def build_scenario_plan():
    """
    Define 20 diverse simulation scenarios with strict scenario-level split:
    - 15 Training Scenarios
    - 5 Held-out Test Scenarios (Never seen during training)
    """
    scenarios = [
        # --- 15 Training Scenarios ---
        {"id": "scen_01", "total_mm": 15.0,  "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_02", "total_mm": 25.0,  "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_03", "total_mm": 35.0,  "duration_min": 120, "peak_fraction": 0.50, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_04", "total_mm": 45.0,  "duration_min": 180, "peak_fraction": 0.25, "drain_rate": 0.03, "split": "train"},
        {"id": "scen_05", "total_mm": 50.0,  "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_06", "total_mm": 60.0,  "duration_min": 240, "peak_fraction": 0.50, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_07", "total_mm": 70.0,  "duration_min": 180, "peak_fraction": 0.67, "drain_rate": 0.07, "split": "train"},
        {"id": "scen_08", "total_mm": 75.0,  "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_09", "total_mm": 85.0,  "duration_min": 120, "peak_fraction": 0.50, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_10", "total_mm": 90.0,  "duration_min": 240, "peak_fraction": 0.25, "drain_rate": 0.03, "split": "train"},
        {"id": "scen_11", "total_mm": 100.0, "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_12", "total_mm": 110.0, "duration_min": 180, "peak_fraction": 0.50, "drain_rate": 0.07, "split": "train"},
        {"id": "scen_13", "total_mm": 120.0, "duration_min": 240, "peak_fraction": 0.67, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_14", "total_mm": 30.0,  "duration_min": 60,  "peak_fraction": 0.50, "drain_rate": 0.05, "split": "train"},
        {"id": "scen_15", "total_mm": 80.0,  "duration_min": 120, "peak_fraction": 0.33, "drain_rate": 0.07, "split": "train"},

        # --- 5 Strictly Held-Out Evaluation Scenarios ---
        {"id": "scen_16", "total_mm": 20.0,  "duration_min": 120, "peak_fraction": 0.50, "drain_rate": 0.05, "split": "heldout"},
        {"id": "scen_17", "total_mm": 40.0,  "duration_min": 180, "peak_fraction": 0.33, "drain_rate": 0.05, "split": "heldout"},
        {"id": "scen_18", "total_mm": 65.0,  "duration_min": 240, "peak_fraction": 0.67, "drain_rate": 0.03, "split": "heldout"},
        {"id": "scen_19", "total_mm": 95.0,  "duration_min": 180, "peak_fraction": 0.25, "drain_rate": 0.07, "split": "heldout"},
        {"id": "scen_20", "total_mm": 125.0, "duration_min": 180, "peak_fraction": 0.50, "drain_rate": 0.05, "split": "heldout"}
    ]
    return scenarios

def extract_samples_from_scenarios(scenarios, cell_features, rng, max_samples_per_timestep=150):
    """
    Extract structured feature matrix X and target y for train and heldout sets.
    Samples both wet and dry depression cells to prevent sampling bias.
    """
    dep_flat = cell_features["dep"].ravel()
    elev_flat = cell_features["elev"].ravel()
    slope_flat = cell_features["slope"].ravel()
    tpi_flat = cell_features["tpi"].ravel()
    inlet_flat = cell_features["inlet_dist"].ravel()
    cn_flat = cell_features["cn"].ravel()
    
    # Identify depression sinks (> 0.02 m) vs non-depression cells
    sink_indices = np.where(dep_flat > 0.02)[0]
    flat_indices = np.where(dep_flat <= 0.02)[0]

    train_X, train_y = [], []
    heldout_X, heldout_y = [], []
    
    for sc in scenarios:
        frames = run_screening_simulation(
            sc["total_mm"], sc["duration_min"], sc["peak_fraction"], sc["drain_rate"], cell_features["dep"]
        )
        
        # Subsample timesteps to maintain balanced temporal representation
        step_indices = np.linspace(0, len(frames) - 1, min(12, len(frames)), dtype=int)
        
        for s_idx in step_indices:
            frame = frames[s_idx]
            depth_flat = frame["depth_grid"].ravel()
            
            # Select balanced cell indices (half from depressions, half from dry/flat)
            n_sinks = min(len(sink_indices), max_samples_per_timestep // 2)
            n_flats = min(len(flat_indices), max_samples_per_timestep - n_sinks)
            chosen_sinks = rng.choice(sink_indices, size=n_sinks, replace=False)
            chosen_flats = rng.choice(flat_indices, size=n_flats, replace=False)
            chosen = np.concatenate([chosen_sinks, chosen_flats])
            
            # Construct feature vectors
            n_pts = len(chosen)
            f_elev = elev_flat[chosen]
            f_slope = slope_flat[chosen]
            f_tpi = tpi_flat[chosen]
            f_dep = dep_flat[chosen]
            f_inlet = inlet_flat[chosen]
            f_cn = cn_flat[chosen]
            
            f_total = np.full(n_pts, sc["total_mm"], dtype=np.float32)
            f_dur = np.full(n_pts, sc["duration_min"], dtype=np.float32)
            f_time = np.full(n_pts, frame["time_min"], dtype=np.float32)
            f_crain = np.full(n_pts, frame["cum_rain_mm"], dtype=np.float32)
            f_intensity = np.full(n_pts, frame["intensity_mm_hr"], dtype=np.float32)
            f_crunoff = np.full(n_pts, frame["cum_runoff_mm"], dtype=np.float32)
            f_drain = np.full(n_pts, sc["drain_rate"], dtype=np.float32)
            
            pts_X = np.column_stack([
                f_elev, f_slope, f_tpi, f_dep, f_inlet, f_cn,
                f_total, f_dur, f_time, f_crain, f_intensity, f_crunoff, f_drain
            ])
            pts_y = depth_flat[chosen]
            
            if sc["split"] == "train":
                train_X.append(pts_X)
                train_y.append(pts_y)
            else:
                heldout_X.append(pts_X)
                heldout_y.append(pts_y)
                
    X_train = np.vstack(train_X).astype(np.float32)
    y_train = np.concatenate(train_y).astype(np.float32)
    X_heldout = np.vstack(heldout_X).astype(np.float32)
    y_heldout = np.concatenate(heldout_y).astype(np.float32)
    
    return X_train, y_train, X_heldout, y_heldout

def generate_and_save_dataset():
    """Execute complete dataset generation pipeline and export artifacts."""
    os.makedirs(DATA_DIR, exist_ok=True)
    rng = np.random.RandomState(RANDOM_SEED)
    
    print("Loading terrain cell features...")
    cell_features = load_cell_features()
    
    print("Building scenario sampling plan...")
    scenarios = build_scenario_plan()
    
    train_ids = [s["id"] for s in scenarios if s["split"] == "train"]
    heldout_ids = [s["id"] for s in scenarios if s["split"] == "heldout"]
    
    # Verify strict data leakage prevention: ZERO scenario overlap
    overlap = set(train_ids).intersection(set(heldout_ids))
    if overlap:
        raise ValueError(f"CRITICAL: Data leakage detected! Overlapping scenarios: {overlap}")
    print(f"Leakage check passed: 0 overlapping scenarios between Train ({len(train_ids)}) and Held-Out ({len(heldout_ids)}).")
    
    print("Simulating scenarios and extracting feature samples...")
    X_train, y_train, X_heldout, y_heldout = extract_samples_from_scenarios(scenarios, cell_features, rng)
    
    # Save arrays
    train_path = os.path.join(DATA_DIR, "train_dataset.npz")
    heldout_path = os.path.join(DATA_DIR, "heldout_dataset.npz")
    np.savez_compressed(train_path, X=X_train, y=y_train, features=FEATURE_NAMES)
    np.savez_compressed(heldout_path, X=X_heldout, y=y_heldout, features=FEATURE_NAMES)
    
    # Save metadata
    meta = {
        "milestone": "M9",
        "title": "AquaPredict Screening Model Surrogate Training Dataset",
        "description": "Reproducible synthetic dataset generated from M5 screening simulation",
        "scientific_disclaimer": "SYNTHETIC SIMULATOR LABELS ONLY. NOT real-world observed floods.",
        "random_seed": RANDOM_SEED,
        "features": FEATURE_NAMES,
        "scenarios_count_total": len(scenarios),
        "scenarios_count_train": len(train_ids),
        "scenarios_count_heldout": len(heldout_ids),
        "train_scenario_ids": train_ids,
        "heldout_scenario_ids": heldout_ids,
        "train_samples_count": int(len(y_train)),
        "heldout_samples_count": int(len(y_heldout)),
        "target_variable": "depth_m",
        "pilot_bounding_box": {
            "west": -95.3750, "south": 29.7560, "east": -95.3650, "north": 29.7650
        },
        "scenarios_plan": scenarios
    }
    meta_path = os.path.join(DATA_DIR, "scenarios_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    print(f"Dataset generated successfully:")
    print(f"  Train:   {X_train.shape[0]} samples across {len(train_ids)} scenarios")
    print(f"  Held-out:{X_heldout.shape[0]} samples across {len(heldout_ids)} scenarios")
    print(f"  Metadata: {meta_path}")
    return meta

if __name__ == "__main__":
    generate_and_save_dataset()
