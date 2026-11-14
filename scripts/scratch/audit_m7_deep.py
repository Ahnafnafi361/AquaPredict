import os
import json
import math

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEOJSON_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'street_network.geojson')
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
META_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_route_planner_meta.json')
M5_SIM_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json')
M5_META_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm5_simulation_meta.json')
M6_NET_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm6_drainage_network.json')
SUSC_GRID_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'susceptibility_grid.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)
with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
    geojson = json.load(f)

edges = graph['edges']
nodes = graph['nodes']

print("--- SELF-LOOP INSPECTION ---")
self_loops = [e for e in edges if e['from_node'] == e['to_node']]
for sl in self_loops:
    print(f"Edge ID: {sl['edge_id']}, Name: {sl['name']}, Length: {sl['length_m']}m, Coords count: {len(sl['coords'])}")
    print(f"From node {sl['from_node']} coords: {nodes[sl['from_node']]['coords']}")
    print(f"Start pt: {sl['coords'][0]}, End pt: {sl['coords'][-1]}")
    # Why is from_node == to_node?
    d_endpoints = math.dist(sl['coords'][0], sl['coords'][-1])
    print(f"Distance between polyline endpoints (deg): {d_endpoints}")

print("\n--- OUT OF BBOX INSPECTION ---")
b = graph['bounding_box']
out_edges = []
for e in edges:
    is_out = False
    for pt in e['coords']:
        if pt[0] < b['west'] or pt[0] > b['east'] or pt[1] < b['south'] or pt[1] > b['north']:
            is_out = True
            break
    if is_out:
        out_edges.append(e)

print(f"Total edges with points outside pilot bbox: {len(out_edges)}")
for oe in out_edges[:5]:
    print(f"Edge {oe['edge_id']} ({oe['name']}): Road class {oe['road_class']}, Length {oe['length_m']}m")

print("\n--- M5 DEPTH INTEGRATION INSPECTION ---")
with open(M5_SIM_PATH, 'r', encoding='utf-8') as f:
    m5_sim = json.load(f)
with open(M5_META_PATH, 'r', encoding='utf-8') as f:
    m5_meta = json.load(f)

# Inspect sparse depths structure
presets = m5_sim.get('presets', {})
print(f"M5 Presets available: {list(presets.keys())}")
p50 = presets.get('preset_50mm', {})
timesteps = p50.get('timesteps', [])
print(f"Number of timesteps in preset_50mm: {len(timesteps)}")
t12 = timesteps[12] if len(timesteps) > 12 else {}
sparse_depths = t12.get('sparse_depths', [])
print(f"Timestep 12 (minute {t12.get('minute')}): {len(sparse_depths)} wet cells")
if sparse_depths:
    max_d = max(d[1] for d in sparse_depths)
    min_d = min(d[1] for d in sparse_depths)
    print(f"Depth range: min={min_d:.3f}m, max={max_d:.3f}m")

# Check road edge depths across preset_50mm @ t12
edge_depths = []
for e in edges:
    max_d = 0.0
    s_depths = dict(sparse_depths)
    for pt in e['coords']:
        lon, lat = pt[0], pt[1]
        if b['west'] <= lon <= b['east'] and b['south'] <= lat <= b['north']:
            col = min(max(int((lon - b['west']) / (b['east'] - b['west']) * 100), 0), 99)
            row = min(max(int((b['north'] - lat) / (b['north'] - b['south']) * 100), 0), 99)
            flat_idx = row * 100 + col
            d = s_depths.get(flat_idx, 0.0)
            if d > max_d:
                max_d = d
    edge_depths.append(max_d)

wet_edges = [d for d in edge_depths if d > 0]
submerged_edges = [d for d in edge_depths if d > 0.05]
deep_edges = [d for d in edge_depths if d > 0.20]
print(f"Edges with any water (d > 0): {len(wet_edges)} / {len(edges)}")
print(f"Edges submerged (d > 0.05m): {len(submerged_edges)} / {len(edges)}")
print(f"Edges deep (d > 0.20m): {len(deep_edges)} / {len(edges)}")
if wet_edges:
    print(f"Max road edge depth: {max(wet_edges):.3f}m")

print("\n--- M6 DRAINAGE INTEGRATION INSPECTION ---")
with open(M6_NET_PATH, 'r', encoding='utf-8') as f:
    m6_net = json.load(f)

conduits = m6_net.get('conduits', {})
print(f"Total conduits in M6: {len(conduits)}")
edges_with_conduits = [e for e in edges if e.get('nearby_conduit_ids')]
print(f"Edges with nearby conduits (<25m): {len(edges_with_conduits)} / {len(edges)}")
conduit_counts_per_edge = [len(e['nearby_conduit_ids']) for e in edges_with_conduits]
if conduit_counts_per_edge:
    print(f"Max nearby conduits per edge: {max(conduit_counts_per_edge)}, Mean: {sum(conduit_counts_per_edge)/len(conduit_counts_per_edge):.1f}")

# Check dynamic simulation loading in M6
m6_loading = m6_net.get('dynamic_simulation_loading', {})
print(f"M6 dynamic simulation loading presets: {list(m6_loading.keys())}")
loading_50 = m6_loading.get('preset_50mm', {}).get('timesteps', [])
print(f"M6 loading timesteps in preset_50mm: {len(loading_50)}")
if loading_50:
    print(f"Sample timestep 12 loading: {loading_50[12] if len(loading_50) > 12 else 'N/A'}")
