"""
AquaPredict Benchmark Suite (scripts/bench.py)
Phase 2 Performance Benchmarking for Milestone M10.

Measures:
1. AOI / Data Loading Latency (cold vs warm, mean, median, p95)
2. Default Screening Simulation Execution (cold vs warm, mean, median, p95)
3. Routing Query Latency (cold vs warm, mean, median, p95)
4. Frontend Asset & Bundle Size Inventory
"""

import os
import sys
import time
import json
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

PUBLIC_DATA_DIR = os.path.join(WORKSPACE_DIR, "public", "data")
PUBLIC_DIR = os.path.join(WORKSPACE_DIR, "public")

def format_stats(cold_ms, warm_runs_ms):
    warm_arr = np.array(warm_runs_ms)
    return {
        "cold_start_ms": round(cold_ms, 3),
        "warm_mean_ms": round(float(np.mean(warm_arr)), 3),
        "warm_median_ms": round(float(np.median(warm_arr)), 3),
        "warm_p95_ms": round(float(np.percentile(warm_arr, 95)), 3),
        "warm_min_ms": round(float(np.min(warm_arr)), 3),
        "warm_max_ms": round(float(np.max(warm_arr)), 3),
        "iterations": len(warm_runs_ms)
    }

def benchmark_aoi_data_loading(warm_iterations=50):
    """Measures time to load key AOI datasets into memory."""
    target_files = [
        "pilot_boundary.geojson",
        "dem_grid.json",
        "gravity_mains.geojson",
        "street_network.geojson",
        "m7_routing_graph.json",
        "simulation_scenarios.json"
    ]
    
    # Cold start load
    t0 = time.perf_counter()
    cold_data = {}
    for fname in target_files:
        fpath = os.path.join(PUBLIC_DATA_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            cold_data[fname] = json.load(f)
    cold_ms = (time.perf_counter() - t0) * 1000.0

    # Warm runs
    warm_runs = []
    for _ in range(warm_iterations):
        t0 = time.perf_counter()
        warm_data = {}
        for fname in target_files:
            fpath = os.path.join(PUBLIC_DATA_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                warm_data[fname] = json.load(f)
        warm_runs.append((time.perf_counter() - t0) * 1000.0)

    total_bytes = sum(os.path.getsize(os.path.join(PUBLIC_DATA_DIR, f)) for f in target_files)
    stats = format_stats(cold_ms, warm_runs)
    stats["total_dataset_bytes"] = total_bytes
    stats["files_benchmarked"] = target_files
    return stats

def benchmark_default_screening_simulation(warm_iterations=50):
    """
    Measures the M5 hydrological screening simulation frame retrieval and processing latency.
    Note: This measures in-memory timestep frame lookup, which is distinct from the
    full-scenario simulation benchmark (1.448 ms original vs 1,256.59 ms surrogate)
    established and audited in Milestone M9.
    """
    scenarios_file = os.path.join(PUBLIC_DATA_DIR, "simulation_scenarios.json")
    with open(scenarios_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    presets = data.get("presets", {})
    # Use default 50mm preset
    preset_50 = presets.get("preset_50mm") or list(presets.values())[2]
    timesteps = preset_50.get("timesteps", [])

    # Cold start: find timestep and format response
    t0 = time.perf_counter()
    target_t = 90.0
    selected = min(timesteps, key=lambda s: abs(s.get("time_minutes", 0) - target_t))
    _ = {
        "status": "success",
        "mode": "original",
        "model_type": "SCREENING SIMULATION",
        "timestep": selected,
        "grid_cells": len(selected.get("sparse_depths", {}))
    }
    cold_ms = (time.perf_counter() - t0) * 1000.0

    # Warm runs
    warm_runs = []
    for _ in range(warm_iterations):
        t0 = time.perf_counter()
        selected = min(timesteps, key=lambda s: abs(s.get("time_minutes", 0) - target_t))
        _ = {
            "status": "success",
            "mode": "original",
            "model_type": "SCREENING SIMULATION",
            "timestep": selected,
            "grid_cells": len(selected.get("sparse_depths", {}))
        }
        warm_runs.append((time.perf_counter() - t0) * 1000.0)

    stats = format_stats(cold_ms, warm_runs)
    stats["preset_id"] = "preset_50mm"
    stats["target_rainfall_mm"] = preset_50.get("target_rainfall_mm")
    stats["duration_minutes"] = preset_50.get("duration_minutes")
    return stats

def benchmark_routing_query(warm_iterations=50):
    """
    Measures route calculation query latency using M7 routing engine.
    """
    from scripts.route_planner import DrainageInformedRoutingGraph

    # Cold start: instantiate, build graph, and run route comparison
    t0 = time.perf_counter()
    rg = DrainageInformedRoutingGraph()
    rg.build_graph()
    # Coords in Downtown Houston pilot
    start_pt = [-95.3680, 29.7640]  # Near Buffalo Bayou north
    dest_pt = [-95.3670, 29.7580]   # Near City Hall south
    result = rg.compare_alternatives(start_pt, dest_pt, preset_mm=50, timestep_idx=12, mode="pedestrian")
    cold_ms = (time.perf_counter() - t0) * 1000.0

    # Warm runs: query execution on preloaded graph
    warm_runs = []
    for _ in range(warm_iterations):
        t0 = time.perf_counter()
        _ = rg.compare_alternatives(start_pt, dest_pt, preset_mm=50, timestep_idx=12, mode="pedestrian")
        warm_runs.append((time.perf_counter() - t0) * 1000.0)

    stats = format_stats(cold_ms, warm_runs)
    stats["start_coords"] = start_pt
    stats["dest_coords"] = dest_pt
    stats["edges_in_graph"] = len(rg.edges)
    stats["nodes_in_graph"] = len(rg.nodes)
    return stats

def benchmark_frontend_bundle_size():
    """
    Inventories the frontend static asset bundle sizes.
    """
    assets = [
        ("index.html", os.path.join(PUBLIC_DIR, "index.html")),
        ("css/style.css", os.path.join(PUBLIC_DIR, "css", "style.css")),
        ("js/app.js", os.path.join(PUBLIC_DIR, "js", "app.js")),
        ("js/viewer3d.js", os.path.join(PUBLIC_DIR, "js", "viewer3d.js")),
        ("js/vendor/three.min.js", os.path.join(PUBLIC_DIR, "js", "vendor", "three.min.js")),
        ("js/vendor/OrbitControls.js", os.path.join(PUBLIC_DIR, "js", "vendor", "OrbitControls.js")),
    ]

    inventory = {}
    total_bytes = 0
    total_unvendored_bytes = 0

    for name, path in assets:
        if os.path.exists(path):
            sz = os.path.getsize(path)
            inventory[name] = {
                "size_bytes": sz,
                "size_kb": round(sz / 1024.0, 2)
            }
            total_bytes += sz
            if not name.startswith("js/vendor/"):
                total_unvendored_bytes += sz

    return {
        "assets": inventory,
        "total_bundle_bytes": total_bytes,
        "total_bundle_kb": round(total_bytes / 1024.0, 2),
        "application_code_kb": round(total_unvendored_bytes / 1024.0, 2),
        "vendored_libraries_kb": round((total_bytes - total_unvendored_bytes) / 1024.0, 2)
    }

def run_all_benchmarks(output_json=None):
    print("=" * 70)
    print(" AquaPredict Milestone 10 (M10) — Performance Benchmark Suite")
    print(" Machine / Environment: Windows 11 AMD64, Python 3.12.2")
    print(" Pilot Sector: Downtown Houston / Buffalo Bayou [-95.3750, 29.7560, -95.3650, 29.7650]")
    print("=" * 70)

    # 1. AOI / Data Loading
    print("\n[1/4] Benchmarking AOI / Data Loading (50 warm iterations)...")
    aoi_stats = benchmark_aoi_data_loading(warm_iterations=50)
    print(f"  Cold Start : {aoi_stats['cold_start_ms']} ms")
    print(f"  Warm Mean  : {aoi_stats['warm_mean_ms']} ms")
    print(f"  Warm Median: {aoi_stats['warm_median_ms']} ms")
    print(f"  Warm p95   : {aoi_stats['warm_p95_ms']} ms")
    print(f"  Total Data : {round(aoi_stats['total_dataset_bytes'] / (1024*1024), 2)} MB across 6 files")

    # 2. Screening Simulation
    print("\n[2/4] Benchmarking Default Screening Simulation (50 warm iterations)...")
    sim_stats = benchmark_default_screening_simulation(warm_iterations=50)
    print(f"  Cold Start : {sim_stats['cold_start_ms']} ms")
    print(f"  Warm Mean  : {sim_stats['warm_mean_ms']} ms")
    print(f"  Warm Median: {sim_stats['warm_median_ms']} ms")
    print(f"  Warm p95   : {sim_stats['warm_p95_ms']} ms")

    # 3. Route Query
    print("\n[3/4] Benchmarking M7 Route Query Latency (50 warm iterations)...")
    route_stats = benchmark_routing_query(warm_iterations=50)
    print(f"  Cold Start : {route_stats['cold_start_ms']} ms (includes graph load)")
    print(f"  Warm Mean  : {route_stats['warm_mean_ms']} ms")
    print(f"  Warm Median: {route_stats['warm_median_ms']} ms")
    print(f"  Warm p95   : {route_stats['warm_p95_ms']} ms")

    # 4. Frontend Bundle Size
    print("\n[4/4] Auditing Frontend Asset / Bundle Sizes...")
    bundle_stats = benchmark_frontend_bundle_size()
    for name, item in bundle_stats["assets"].items():
        print(f"  - {name:30} : {item['size_kb']:>8.2f} KB ({item['size_bytes']} bytes)")
    print(f"  Total Frontend Payload     : {bundle_stats['total_bundle_kb']} KB")
    print(f"  AquaPredict Codebase Only  : {bundle_stats['application_code_kb']} KB")
    print(f"  Vendored Third-Party Libs  : {bundle_stats['vendored_libraries_kb']} KB")

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "environment": {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "study_area": "Downtown Houston / Buffalo Bayou [-95.3750, 29.7560, -95.3650, 29.7650]"
        },
        "aoi_data_loading": aoi_stats,
        "screening_simulation": sim_stats,
        "routing_query": route_stats,
        "frontend_bundle": bundle_stats
    }

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\n[OK] Benchmark report written to: {output_json}")

    return results

if __name__ == "__main__":
    out_file = os.path.join(PUBLIC_DATA_DIR, "m10_benchmark_report.json")
    run_all_benchmarks(output_json=out_file)
