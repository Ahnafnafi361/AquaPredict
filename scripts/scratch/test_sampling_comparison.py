import os
import sys
import json
import math

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph, haversine_distance, PILOT_BBOX

def densify_polyline(coords, step_m=10.0):
    """
    Sample a polyline at approximately step_m intervals.
    Guarantees no duplicate consecutive points and preserves segment endpoints.
    """
    if len(coords) < 2:
        return list(coords)
    
    samples = []
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i+1]
        dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if dist <= 0.001:
            continue
        n_steps = max(1, int(round(dist / step_m)))
        for s in range(n_steps):
            frac = s / n_steps
            samples.append([
                p1[0] + frac * (p2[0] - p1[0]),
                p1[1] + frac * (p2[1] - p1[1])
            ])
    # Append final endpoint
    samples.append(list(coords[-1]))
    return samples

# Test on routing graph
g = DrainageInformedRoutingGraph()
g.build_graph()

print(f"Total Edges: {len(g.edges)}")

# Measure sampling stats
raw_pts_total = sum(len(e['coords']) for e in g.edges)
dens_pts_total = sum(len(densify_polyline(e['coords'], 10.0)) for e in g.edges)
print(f"Raw vertex count: {raw_pts_total} (avg {raw_pts_total/len(g.edges):.1f} per edge)")
print(f"Densified sample count (10m): {dens_pts_total} (avg {dens_pts_total/len(g.edges):.1f} per edge)")

# Compare costs across presets: 10mm, 50mm, 100mm at timestep 12 (minute 60)
for preset in [10, 50, 100]:
    changed_depth_edges = []
    cost_changes = []
    for e in g.edges:
        raw_depth = g._get_modelled_depth(e['coords'], preset_mm=preset, timestep_idx=12)
        dens_coords = densify_polyline(e['coords'], 10.0)
        dens_depth = g._get_modelled_depth(dens_coords, preset_mm=preset, timestep_idx=12)

        if abs(raw_depth - dens_depth) > 0.001:
            changed_depth_edges.append((e['edge_id'], e['name'], raw_depth, dens_depth, e['length_m']))

    print(f"\n--- PRESET {preset}mm @ STEP 12 ---")
    print(f"Edges with changed max depth under 10m sampling: {len(changed_depth_edges)} / {len(g.edges)}")
    for ch in changed_depth_edges[:10]:
        print(f"  Edge {ch[0]} ({ch[1]}): raw={ch[2]:.3f}m -> dens={ch[3]:.3f}m (len={ch[4]}m)")
