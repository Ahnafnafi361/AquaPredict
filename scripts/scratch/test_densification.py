import os
import json
import math

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
M5_SIM_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)
with open(M5_SIM_PATH, 'r', encoding='utf-8') as f:
    m5_sim = json.load(f)

edges = graph['edges']
b = graph['bounding_box']
timesteps = m5_sim['presets']['preset_50mm']['timesteps']
sparse_depths = dict(timesteps[12]['sparse_depths'])

def sample_raw_vertices(coords):
    max_d = 0.0
    for pt in coords:
        lon, lat = pt[0], pt[1]
        if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
            col = min(max(int((lon - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
            row = min(max(int((b["north"] - lat) / (b["north"] - b["south"]) * 100), 0), 99)
            flat_idx = row * 100 + col
            d = sparse_depths.get(flat_idx, 0.0)
            if d > max_d:
                max_d = d
    return max_d

def sample_densified_10m(coords):
    max_d = 0.0
    # Interpolate at ~10m along each segment
    sample_pts = []
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i+1]
        dist_m = math.hypot((p2[0] - p1[0]) * 96000.0, (p2[1] - p1[1]) * 111320.0)
        num_steps = max(1, int(math.ceil(dist_m / 10.0)))
        for s in range(num_steps):
            frac = s / num_steps
            sample_pts.append((p1[0] + frac * (p2[0] - p1[0]), p1[1] + frac * (p2[1] - p1[1])))
    sample_pts.append(coords[-1])

    for pt in sample_pts:
        lon, lat = pt[0], pt[1]
        if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
            col = min(max(int((lon - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
            row = min(max(int((b["north"] - lat) / (b["north"] - b["south"]) * 100), 0), 99)
            flat_idx = row * 100 + col
            d = sparse_depths.get(flat_idx, 0.0)
            if d > max_d:
                max_d = d
    return max_d

diff_count = 0
increases = []
for e in edges:
    raw_d = sample_raw_vertices(e['coords'])
    dens_d = sample_densified_10m(e['coords'])
    if abs(raw_d - dens_d) > 0.001:
        diff_count += 1
        increases.append((e['edge_id'], e['name'], raw_d, dens_d, e['length_m']))

print(f"Edges with different depth when densified at 10m: {diff_count} / {len(edges)}")
for inc in increases[:15]:
    print(f"  Edge {inc[0]} ({inc[1]}): raw={inc[2]:.3f}m -> densified={inc[3]:.3f}m (len={inc[4]}m)")
