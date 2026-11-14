import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph

g = DrainageInformedRoutingGraph()
g.build_graph()

start = [-95.3705, 29.7580]
dest = [-95.3680, 29.7645]

comp = g.compare_alternatives(start, dest, preset_mm=10, timestep_idx=12, mode="vehicle")
for k, r in comp["alternatives"].items():
    print(f"[{k}] Status: {r.get('status')}, Message: {r.get('message')}")
