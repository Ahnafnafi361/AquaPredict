import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph

g = DrainageInformedRoutingGraph()
g.build_graph()

start_landmarks = [
    ("-95.3740,29.7610", "Walker & Sabine"),
    ("-95.3705,29.7580", "Bagby & McKinney"),
    ("-95.3730,29.7570", "Allen Pkwy & Clay"),
    ("-95.3670,29.7600", "Milam & Capitol"),
    ("-95.3710,29.7640", "Franklin & Bagby")
]

dest_landmarks = [
    ("-95.3680,29.7645", "Milam & Franklin"),
    ("-95.3660,29.7610", "Main & Capitol"),
    ("-95.3670,29.7570", "Travis & Bell"),
    ("-95.3720,29.7625", "Preston & Heiner")
]

print("=== CHECKING DIFFERENCES AMONG ALTERNATIVES AT 100mm STORM @ MINUTE 60 ===")
diff_found = []
for s_coords, s_name in start_landmarks:
    s_lon, s_lat = map(float, s_coords.split(','))
    for d_coords, d_name in dest_landmarks:
        d_lon, d_lat = map(float, d_coords.split(','))
        comp = g.compare_alternatives([s_lon, s_lat], [d_lon, d_lat], preset_mm=100, timestep_idx=12, mode="pedestrian")
        alts = comp["alternatives"]
        b = alts["baseline_shortest"]
        d = alts["drainage_informed"]
        s = alts["low_susceptibility"]
        if b["status"] == "SUCCESS" and d["status"] == "SUCCESS" and s["status"] == "SUCCESS":
            b_coords = b["coordinates"]
            d_coords = d["coordinates"]
            s_coords_list = s["coordinates"]
            is_diff = (b_coords != d_coords) or (b_coords != s_coords_list) or (d_coords != s_coords_list)
            if is_diff:
                diff_found.append((s_name, d_name, b["total_distance_m"], d["total_distance_m"], s["total_distance_m"],
                                   b["prototype_hazard_score"], d["prototype_hazard_score"], s["prototype_hazard_score"],
                                   b["max_modelled_depth_m"], d["max_modelled_depth_m"]))
                print(f"DIFF: {s_name} -> {d_name}:")
                print(f"  Baseline:  dist={b['total_distance_m']}m, score={b['prototype_hazard_score']}, depth={b['max_modelled_depth_m']}m")
                print(f"  Drainage:  dist={d['total_distance_m']}m, score={d['prototype_hazard_score']}, depth={d['max_modelled_depth_m']}m")
                print(f"  Low-Susc:  dist={s['total_distance_m']}m, score={s['prototype_hazard_score']}, depth={s['max_modelled_depth_m']}m")

print(f"\nTotal landmark pairs with distinct alternative paths: {len(diff_found)} / 20")
