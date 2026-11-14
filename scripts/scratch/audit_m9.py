"""
Audit script for Milestone M9:
Priority 1: Benchmark validity & latency profiling
Priority 2: Extreme prediction errors & error distribution
Priority 3: Scenario coverage
Priority 4: Feature relevance
"""

import os
import sys
import json
import time
import numpy as np
import joblib

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORKSPACE_DIR)

from ml.surrogate.generate_dataset import (
    load_cell_features,
    run_screening_simulation,
    generate_hyetograph_intervals,
    compute_nrcs_runoff,
    FEATURE_NAMES
)
from ml.surrogate.predict import (
    predict_surrogate_frame,
    load_surrogate_model,
    _get_static_features
)

def audit_priority_1_benchmarks():
    print("=" * 70)
    print(" PRIORITY 1: BENCHMARK VALIDITY & LATENCY AUDIT")
    print("=" * 70)

    model, meta = load_surrogate_model()
    static_X, dep, cn = _get_static_features()
    n_cells = len(static_X)  # 10,000 cells

    # 1. Warm-up iterations
    scenario_feats = np.array([50.0, 180.0, 90.0, 46.1, 23.84, 18.5, 0.05], dtype=np.float32)
    dynamic_X = np.tile(scenario_feats, (n_cells, 1))
    X_sample = np.hstack([static_X, dynamic_X])

    for _ in range(10):
        _ = model.predict(X_sample)

    # 2. Repeated measurements for Surrogate Predict alone (core model inference on 10,000 cells)
    surr_predict_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        _ = model.predict(X_sample)
        t1 = time.perf_counter()
        surr_predict_times.append((t1 - t0) * 1000.0)

    # 3. Repeated measurements for Full Surrogate Pipeline (predict_surrogate_frame including feature tiling & sparse extraction)
    surr_full_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        _ = predict_surrogate_frame(50.0, 180, 90, 0.33, 0.05)
        t1 = time.perf_counter()
        surr_full_times.append((t1 - t0) * 1000.0)

    # 4. Repeated measurements for Original Physical Screening Simulator
    # Original simulation produces all 37 timesteps for 10,000 cells
    # We test:
    # A) Simulating the entire 180-min scenario (37 timesteps)
    # B) Time per single frame within that run
    # C) Extracting / slicing a single frame
    for _ in range(5):
        _ = run_screening_simulation(50.0, 180, 0.33, 0.05, dep)

    sim_full_scenario_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        frames = run_screening_simulation(50.0, 180, 0.33, 0.05, dep)
        t1 = time.perf_counter()
        sim_full_scenario_times.append((t1 - t0) * 1000.0)

    sim_per_frame_times = [t / 37.0 for t in sim_full_scenario_times]

    # 5. Measure model loading time from disk
    model_load_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        _ = joblib.load(os.path.join(WORKSPACE_DIR, "ml", "surrogate", "models", "surrogate_model.joblib"))
        t1 = time.perf_counter()
        model_load_times.append((t1 - t0) * 1000.0)

    def stats(arr):
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "p95": float(np.percentile(arr, 95)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr))
        }

    p_stats = stats(surr_predict_times)
    f_stats = stats(surr_full_times)
    sim_scen_stats = stats(sim_full_scenario_times)
    sim_frame_stats = stats(sim_per_frame_times)
    load_stats = stats(model_load_times)

    print("\n[A] Model Loading Time from Disk:")
    print(f"  Mean: {load_stats['mean']:.2f} ms | Median: {load_stats['median']:.2f} ms | p95: {load_stats['p95']:.2f} ms")

    print("\n[B] ML Surrogate Inference on 10,000 cells (predict only):")
    print(f"  Mean: {p_stats['mean']:.2f} ms | Median: {p_stats['median']:.2f} ms | p95: {p_stats['p95']:.2f} ms")

    print("\n[C] ML Surrogate Full Pipeline (Feature assembly + predict + postprocessing):")
    print(f"  Mean: {f_stats['mean']:.2f} ms | Median: {f_stats['median']:.2f} ms | p95: {f_stats['p95']:.2f} ms")

    print("\n[D] Original Physical Screening Simulator (37 timesteps x 10,000 cells):")
    print(f"  Entire 180-min scenario: Mean {sim_scen_stats['mean']:.2f} ms | Median {sim_scen_stats['median']:.2f} ms | p95: {sim_scen_stats['p95']:.2f} ms")
    print(f"  Per single depth frame: Mean {sim_frame_stats['mean']:.3f} ms | Median {sim_frame_stats['median']:.3f} ms | p95: {sim_frame_stats['p95']:.3f} ms")

    print("\n[E] Comparison & Actual Speed Ratio:")
    print(f"  Original Simulator is {p_stats['median'] / sim_frame_stats['median']:.1f}x FASTER than Surrogate core predict!")
    print(f"  Original Simulator is {f_stats['median'] / sim_frame_stats['median']:.1f}x FASTER than Surrogate full pipeline!")
    print(f"  In fact, running the ENTIRE 37-timestep physical simulation ({sim_scen_stats['median']:.2f} ms) is faster than predicting a SINGLE surrogate frame ({f_stats['median']:.2f} ms)!")


def audit_priority_2_extreme_errors():
    print("\n" + "=" * 70)
    print(" PRIORITY 2: EXTREME PREDICTION ERRORS & ERROR DISTRIBUTION")
    print("=" * 70)

    model, meta = load_surrogate_model()

    heldout_npz = np.load(os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data", "heldout_dataset.npz"))
    X_heldout = heldout_npz["X"]
    y_heldout = heldout_npz["y"]
    features = list(heldout_npz["features"])

    y_pred = model.predict(X_heldout)
    y_pred = np.maximum(0.0, y_pred)
    abs_errors = np.abs(y_heldout - y_pred)

    max_err_idx = int(np.argmax(abs_errors))
    max_err = float(abs_errors[max_err_idx])
    y_true_max = float(y_heldout[max_err_idx])
    y_pred_max = float(y_pred[max_err_idx])
    feats_max = X_heldout[max_err_idx]

    print(f"Max Absolute Error: {max_err:.4f} m ({max_err*1000:.1f} mm)")
    print(f"  Sample Index: {max_err_idx}")
    print(f"  Original Simulator Depth: {y_true_max:.4f} m")
    print(f"  Surrogate Predicted Depth: {y_pred_max:.4f} m")
    print("  Feature values at max error:")
    for fn, fv in zip(features, feats_max):
        print(f"    {fn:16s}: {fv:.4f}")

    # Identify exact scenario and timestep
    # In generate_dataset.py, held-out dataset has 5 scenarios.
    # Each scenario samples 1,800 cells x some number of timesteps, or how were 9,000 samples generated?
    with open(os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data", "scenarios_metadata.json"), "r") as f:
        meta_json = json.load(f)

    # Let's inspect the rainfall_total, duration_min, time_min of this sample:
    rain_tot = feats_max[features.index("rainfall_total")]
    dur_min = feats_max[features.index("duration_min")]
    t_min = feats_max[features.index("time_min")]
    dep_val = feats_max[features.index("dep")]
    elev_val = feats_max[features.index("elev")]
    slope_val = feats_max[features.index("slope")]

    # Find matching scenario in scenarios_plan
    matching_scen = None
    for sc in meta_json["scenarios_plan"]:
        if abs(sc["total_mm"] - rain_tot) < 0.1 and abs(sc["duration_min"] - dur_min) < 0.1:
            matching_scen = sc
            break

    print(f"\n  Matched Held-Out Scenario: {matching_scen['id'] if matching_scen else 'Unknown'}")
    if matching_scen:
        print(f"    Rainfall Total: {matching_scen['total_mm']} mm")
        print(f"    Duration: {matching_scen['duration_min']} min")
        print(f"    Temporal Peak Fraction: {matching_scen['peak_fraction']}")
        print(f"    Drain Rate: {matching_scen['drain_rate']}")
    print(f"    Timestep Time: {t_min} minutes")
    print(f"    Depression Storage (dep): {dep_val:.4f} m (Significant deep depression sink!)")
    print(f"    Elevation: {elev_val:.4f} m NAVD88")

    # Error distribution percentiles
    p50 = float(np.percentile(abs_errors, 50))
    p75 = float(np.percentile(abs_errors, 75))
    p90 = float(np.percentile(abs_errors, 90))
    p95 = float(np.percentile(abs_errors, 95))
    p99 = float(np.percentile(abs_errors, 99))
    p99_9 = float(np.percentile(abs_errors, 99.9))

    print("\nAbsolute Error Percentiles (Held-Out Data, 9,000 samples):")
    print(f"  50th percentile (median): {p50*1000:.2f} mm ({p50:.4f} m)")
    print(f"  75th percentile:          {p75*1000:.2f} mm ({p75:.4f} m)")
    print(f"  90th percentile:          {p90*1000:.2f} mm ({p90:.4f} m)")
    print(f"  95th percentile:          {p95*1000:.2f} mm ({p95:.4f} m)")
    print(f"  99th percentile:          {p99*1000:.2f} mm ({p99:.4f} m)")
    print(f"  99.9th percentile:        {p99_9*1000:.2f} mm ({p99_9:.4f} m)")
    print(f"  Maximum:                  {max_err*1000:.2f} mm ({max_err:.4f} m)")

    # Breakdown by Depth Hazard Tier (based on True Depth y_heldout)
    tiers = [
        ("Dry (< 0.05m)", y_heldout < 0.05),
        ("Shallow (0.05-0.15m)", (y_heldout >= 0.05) & (y_heldout < 0.15)),
        ("Moderate (0.15-0.30m)", (y_heldout >= 0.15) & (y_heldout < 0.30)),
        ("Deep (0.30-0.60m)", (y_heldout >= 0.30) & (y_heldout < 0.60)),
        ("Very Deep (>= 0.60m)", y_heldout >= 0.60),
    ]

    print("\nError Metrics by True Water Depth Class:")
    print(f"{'Depth Class':<24s} | {'Count':<7s} | {'Pct':<6s} | {'MAE (m)':<9s} | {'RMSE (m)':<9s} | {'Max AE (m)':<10s}")
    print("-" * 75)
    for name, mask in tiers:
        cnt = int(np.sum(mask))
        if cnt == 0:
            continue
        pct = (cnt / len(y_heldout)) * 100.0
        mae_tier = float(np.mean(abs_errors[mask]))
        rmse_tier = float(np.sqrt(np.mean((y_heldout[mask] - y_pred[mask]) ** 2)))
        max_tier = float(np.max(abs_errors[mask]))
        print(f"{name:<24s} | {cnt:<7d} | {pct:5.1f}% | {mae_tier:<9.4f} | {rmse_tier:<9.4f} | {max_tier:<10.4f}")


def audit_priority_3_scenarios():
    print("\n" + "=" * 70)
    print(" PRIORITY 3: TRAINING SCENARIO COVERAGE AUDIT")
    print("=" * 70)
    with open(os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data", "scenarios_metadata.json"), "r") as f:
        meta_json = json.load(f)

    plan = meta_json["scenarios_plan"]
    train_ids = set(meta_json["train_scenario_ids"])
    heldout_ids = set(meta_json["heldout_scenario_ids"])

    print(f"Total Scenarios: {len(plan)}")
    print(f"Train Scenarios: {len(train_ids)} ({sorted(list(train_ids))})")
    print(f"Held-Out Scenarios: {len(heldout_ids)} ({sorted(list(heldout_ids))})")

    overlap = train_ids.intersection(heldout_ids)
    print(f"Scenario Overlap (Leakage): {len(overlap)} (Disjoint: {len(overlap) == 0})")

    print("\nScenario Parameter Matrix:")
    print(f"{'ID':<8s} | {'Split':<8s} | {'Rain (mm)':<10s} | {'Duration':<10s} | {'Peak Fraction':<14s} | {'Drain Rate':<10s}")
    print("-" * 72)
    for sc in plan:
        split = "TRAIN" if sc["id"] in train_ids else "HELDOUT"
        print(f"{sc['id']:<8s} | {split:<8s} | {sc['total_mm']:<10.1f} | {sc['duration_min']:<10d} | {sc['peak_fraction']:<14.2f} | {sc['drain_rate']:<10.2f}")


def audit_priority_4_features():
    print("\n" + "=" * 70)
    print(" PRIORITY 4: FEATURE RELEVANCE & CN REDUNDANCY AUDIT")
    print("=" * 70)

    model, meta = load_surrogate_model()
    train_npz = np.load(os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data", "train_dataset.npz"))
    X_train = train_npz["X"]
    features = list(train_npz["features"])

    print(f"{'Feature':<18s} | {'Min':<10s} | {'Max':<10s} | {'Mean':<10s} | {'Std Dev':<10s} | {'Variance Status'}")
    print("-" * 75)
    for i, fn in enumerate(features):
        col = X_train[:, i]
        c_min = float(np.min(col))
        c_max = float(np.max(col))
        c_mean = float(np.mean(col))
        c_std = float(np.std(col))
        status = "ZERO VARIANCE (CONSTANT)" if c_std < 1e-6 else "VARIED"
        print(f"{fn:<18s} | {c_min:<10.3f} | {c_max:<10.3f} | {c_mean:<10.3f} | {c_std:<10.3f} | {status}")


if __name__ == "__main__":
    audit_priority_1_benchmarks()
    audit_priority_2_extreme_errors()
    audit_priority_3_scenarios()
    audit_priority_4_features()
