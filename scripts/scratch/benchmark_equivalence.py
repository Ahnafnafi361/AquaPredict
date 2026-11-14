"""
Standalone read-only benchmark comparing full 37-timestep scenario execution:
Original screening simulator vs ML surrogate pipeline
"""

import os
import sys
import time
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORKSPACE_DIR)

from ml.surrogate.generate_dataset import run_screening_simulation, load_cell_features
from ml.surrogate.predict import predict_surrogate_frame, load_surrogate_model

def run_benchmark():
    print("=" * 70)
    print(" BENCHMARK EQUIVALENCE: FULL 37-TIMESTEP SCENARIO COMPARISON")
    print("=" * 70)

    cell_feats = load_cell_features()
    dep_arr = cell_feats["dep"]
    model, meta = load_surrogate_model()

    # Hardware & Environment Report
    import platform
    print(f"Platform: {platform.platform()}")
    print(f"Processor: {platform.processor()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Domain: 10,000 spatial cells (100x100 grid), 37 timesteps (180 min storm)")

    # Warm-up iterations (5 full scenario runs each)
    print("\nWarming up...")
    for _ in range(5):
        _ = run_screening_simulation(50.0, 180, 0.33, 0.05, dep_arr)
    for step in range(5):
        _ = predict_surrogate_frame(50.0, 180, step * 5, 0.33, 0.05)

    # 1. Full 37-timestep scenario for Original Physical Screening Simulator (50 repetitions)
    print("Profiling Original Physical Screening Simulator (50 repetitions)...")
    orig_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        frames = run_screening_simulation(50.0, 180, 0.33, 0.05, dep_arr)
        t1 = time.perf_counter()
        assert len(frames) == 37
        orig_times.append((t1 - t0) * 1000.0)

    # 2. Full 37-timestep scenario for ML Surrogate (25 repetitions, each executing 37 sequential frames)
    print("Profiling ML Surrogate Pipeline (25 repetitions of 37 frames = 925 predictions)...")
    surr_times = []
    for rep in range(25):
        t0 = time.perf_counter()
        surr_frames = []
        for step in range(37):
            t_min = step * 5
            frame = predict_surrogate_frame(50.0, 180, t_min, 0.33, 0.05)
            surr_frames.append(frame)
        t1 = time.perf_counter()
        assert len(surr_frames) == 37
        surr_times.append((t1 - t0) * 1000.0)

    def compute_stats(arr):
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "p95": float(np.percentile(arr, 95)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr))
        }

    s_orig = compute_stats(orig_times)
    s_surr = compute_stats(surr_times)

    print("\n" + "-" * 70)
    print(" RESULTS: FULL 37-TIMESTEP SCENARIO RUNTIME")
    print("-" * 70)
    print("Original Screening Simulator (Complete 37-step Scenario):")
    print(f"  Mean:   {s_orig['mean']:.3f} ms")
    print(f"  Median: {s_orig['median']:.3f} ms")
    print(f"  p95:    {s_orig['p95']:.3f} ms")
    print(f"  Per-timestep frame (median / 37): {s_orig['median'] / 37.0:.4f} ms ({s_orig['median']*1000.0 / 37.0:.1f} microseconds)")

    print("\nML Surrogate Pipeline (Complete 37-step Scenario):")
    print(f"  Mean:   {s_surr['mean']:.2f} ms ({s_surr['mean']/1000.0:.3f} seconds)")
    print(f"  Median: {s_surr['median']:.2f} ms ({s_surr['median']/1000.0:.3f} seconds)")
    print(f"  p95:    {s_surr['p95']:.2f} ms ({s_surr['p95']/1000.0:.3f} seconds)")
    print(f"  Per-timestep frame (median / 37): {s_surr['median'] / 37.0:.2f} ms")

    speedup = s_surr['median'] / s_orig['median']
    print("\n" + "=" * 70)
    print(f" CONCLUSION: The original simulator is {speedup:.1f}x FASTER than the ML surrogate")
    print(" for the complete 37-timestep scenario.")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
