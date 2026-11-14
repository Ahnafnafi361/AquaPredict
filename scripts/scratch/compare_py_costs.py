import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph

g = DrainageInformedRoutingGraph()
g.build_graph()

print("Python Edge Costs (50mm, step 12):")
for eId in [0, 10, 20, 22, 50, 100]:
    cost = g.calculate_edge_cost(eId, preset_mm=50, timestep_idx=12, mode="pedestrian")
    print(f"  Edge {eId} ({g.edges[eId]['name']}): totalCost={cost['total_cost']}, cBase={cost['c_base']}, pDepth={cost['p_depth']}, pDrain={cost['p_drain']}, pUncert={cost['p_uncert']}")
