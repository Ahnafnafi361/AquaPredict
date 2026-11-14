"""
AquaPredict Milestone M9: ML Surrogate Predictor Module

Provides inference capability for the trained ML surrogate of the AquaPredict screening model.

IMPORTANT SCIENTIFIC DISCLAIMER:
- This is an ML surrogate that emulates the synthetic screening simulator.
- It is NOT a real-world flood prediction model.
- Outputs are labeled SYNTHETIC SURROGATE and UNVALIDATED against real-world flood observations.
- It does not claim real-world flood accuracy.
"""

import os
import sys
import time
import math
import json
import numpy as np
import joblib

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from ml.surrogate.generate_dataset import (
    load_cell_features,
    generate_hyetograph_intervals,
    compute_nrcs_runoff,
    FEATURE_NAMES,
    GRID_ROWS,
    GRID_COLS,
    TOTAL_CELLS
)

MODELS_DIR = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "models")
MODEL_PATH = os.path.join(MODELS_DIR, "surrogate_model.joblib")
META_PATH = os.path.join(MODELS_DIR, "surrogate_metadata.json")

_CACHED_MODEL = None
_CACHED_META = None
_CACHED_STATIC_X = None  # (10000, 6) matrix of static features
_CACHED_DEP = None
_CACHED_CN = None

def is_model_available():
    return os.path.isfile(MODEL_PATH)

def load_surrogate_model(force_reload=False):
    global _CACHED_MODEL, _CACHED_META
    if _CACHED_MODEL is not None and not force_reload:
        return _CACHED_MODEL, _CACHED_META

    if not is_model_available():
        raise FileNotFoundError(
            f"Surrogate model artifact not found at {MODEL_PATH}. "
            "Please run 'python ml/surrogate/train.py' first."
        )

    _CACHED_MODEL = joblib.load(MODEL_PATH)
    if os.path.isfile(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            _CACHED_META = json.load(f)
    else:
        _CACHED_META = {}
    return _CACHED_MODEL, _CACHED_META

def _get_static_features():
    global _CACHED_STATIC_X, _CACHED_DEP, _CACHED_CN
    if _CACHED_STATIC_X is not None:
        return _CACHED_STATIC_X, _CACHED_DEP, _CACHED_CN

    cell_feats = load_cell_features()
    elev = cell_feats["elev"].flatten()
    slope = cell_feats["slope"].flatten()
    tpi = cell_feats["tpi"].flatten()
    dep = cell_feats["dep"].flatten()
    inlet_dist = cell_feats["inlet_dist"].flatten()
    cn = cell_feats["cn"].flatten()

    _CACHED_STATIC_X = np.column_stack([elev, slope, tpi, dep, inlet_dist, cn])
    _CACHED_DEP = dep
    _CACHED_CN = cn
    return _CACHED_STATIC_X, _CACHED_DEP, _CACHED_CN

def predict_surrogate_frame(
    rainfall_total_mm=50.0,
    duration_min=180,
    time_min=90,
    temporal_shape=0.33,
    drain_rate=0.05
):
    """
    Run fast vector inference of the screening surrogate for a single timestep.

    Returns:
        Dictionary containing the depth frame, metrics, and required provenance labels.
    """
    # 1. Input validation
    if rainfall_total_mm is None or rainfall_total_mm < 0:
        raise ValueError(f"Invalid rainfall_total_mm: {rainfall_total_mm}. Must be non-negative.")
    if duration_min is None or duration_min <= 0:
        raise ValueError(f"Invalid duration_min: {duration_min}. Must be strictly positive.")
    if time_min is None or time_min < 0 or time_min > duration_min:
        raise ValueError(f"Invalid time_min: {time_min}. Must be between 0 and {duration_min}.")
    if drain_rate is None or drain_rate < 0.0 or drain_rate > 1.0:
        raise ValueError(f"Invalid drain_rate: {drain_rate}. Must be between 0.0 and 1.0.")

    # 2. Load model
    model, meta = load_surrogate_model()

    # 3. Static features (10,000 cells)
    static_X, dep, cn = _get_static_features()

    t0 = time.perf_counter()

    # 4. Temporal rainfall dynamics at time_min
    interval_min = 5
    rain_intervals = generate_hyetograph_intervals(
        float(rainfall_total_mm), int(duration_min), float(temporal_shape), interval_min
    )
    cum_rain_series = np.insert(np.cumsum(rain_intervals), 0, 0.0)
    cum_runoff_series = compute_nrcs_runoff(cum_rain_series)

    step_idx = min(len(rain_intervals), int(round(time_min / interval_min)))
    cum_rain_mm = float(cum_rain_series[step_idx])
    cum_runoff_mm = float(cum_runoff_series[step_idx])
    
    if step_idx > 0 and step_idx <= len(rain_intervals):
        intensity_mm_hr = float(rain_intervals[step_idx - 1] * (60.0 / interval_min))
    else:
        intensity_mm_hr = 0.0

    # 5. Construct full 13-feature matrix X (10000, 13)
    # Features order: elev, slope, tpi, dep, inlet_dist, cn, rainfall_total, duration_min, time_min, cum_rain_mm, intensity_mm_hr, cum_runoff_mm, drain_rate
    n_cells = len(static_X)
    scenario_feats = np.array([
        float(rainfall_total_mm),
        float(duration_min),
        float(time_min),
        cum_rain_mm,
        intensity_mm_hr,
        cum_runoff_mm,
        float(drain_rate)
    ], dtype=np.float32)
    dynamic_X = np.tile(scenario_feats, (n_cells, 1))
    X = np.hstack([static_X, dynamic_X])

    # 6. Model prediction
    raw_preds = model.predict(X)
    depths = np.maximum(0.0, raw_preds)

    inference_time_ms = (time.perf_counter() - t0) * 1000.0

    # 7. Compute summary statistics
    max_depth_m = float(np.max(depths))
    wet_mask = depths >= 0.05
    flooded_cells_count = int(np.sum(wet_mask))
    flooded_area_km2 = round(flooded_cells_count * 0.0001, 4)
    mean_depth_m = float(np.mean(depths[wet_mask])) if flooded_cells_count > 0 else 0.0

    # Hazard classes matching M5 thresholds
    class_counts = {
        "dry_c0": int(np.sum(depths < 0.05)),
        "shallow_c1": int(np.sum((depths >= 0.05) & (depths < 0.15))),
        "moderate_c2": int(np.sum((depths >= 0.15) & (depths < 0.30))),
        "deep_c3": int(np.sum((depths >= 0.30) & (depths < 0.60))),
        "very_deep_c4": int(np.sum(depths >= 0.60))
    }

    # Sparse depths encoding (> 1 mm depth)
    significant_indices = np.where(depths >= 0.001)[0]
    sparse_depths = [[int(idx), round(float(depths[idx]), 3)] for idx in significant_indices]

    # Mass balance surrogate approximation / conservation tracking
    # precip_vol = (cum_rain_mm / 1000.0) * 970000.0
    # storage_vol = float(np.sum(depths) * 97.0)
    # outfall_est = max(0.0, precip_vol - storage_vol)

    return {
        "status": "success",
        "mode": "surrogate",
        "model_type": "SYNTHETIC SURROGATE",
        "provenance_label": "SYNTHETIC SURROGATE",
        "validation_status": "UNVALIDATED against real-world flood observations",
        "scientific_disclaimer": "These metrics measure how closely the ML surrogate reproduces the AquaPredict screening model. They do not measure real-world flood prediction accuracy.",
        "timestep": {
            "time_minutes": int(time_min),
            "cumulative_rain_mm": round(float(cum_rain_mm), 2),
            "intensity_mm_hr": round(float(intensity_mm_hr), 2),
            "max_depth_m": round(max_depth_m, 3),
            "mean_depth_m": round(mean_depth_m, 3),
            "flooded_area_km2": flooded_area_km2,
            "flooded_cells_count": flooded_cells_count,
            "class_counts": class_counts,
            "sparse_depths": sparse_depths
        },
        "metadata": {
            "target_rainfall_mm": float(rainfall_total_mm),
            "duration_minutes": int(duration_min),
            "drain_rate": float(drain_rate),
            "cells_evaluated": n_cells,
            "inference_time_ms": round(inference_time_ms, 2),
            "framework": "scikit-learn (HistGradientBoostingRegressor)"
        }
    }
