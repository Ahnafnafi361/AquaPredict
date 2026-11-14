import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph

g = DrainageInformedRoutingGraph()
g.build_graph()

# Default landmark route: Bagby & McKinney to Milam & Franklin
start = [-95.3705, 29.7580]
dest = [-95.3680, 29.7645]

for mode in ["pedestrian", "vehicle"]:
    for preset in [10, 50, 100]:
        comp = g.compare_alternatives(start, dest, preset_mm=preset, timestep_idx=12, mode=mode)
        print(f"\n================ Mode: {mode.upper()}, Preset: {preset}mm, Step: 12 ================")
        for k, r in comp["alternatives"].items():
            print(f"[{k.upper()}] Status: {r['status']}, Dist: {r['total_distance_m']}m, Score: {r['prototype_hazard_score']}, MaxDepth: {r['max_modelled_depth_m']}m, Submerged: {r['submerged_length_m']}m, Exceeded: {r['drainage_exceeded_conduits']}")
