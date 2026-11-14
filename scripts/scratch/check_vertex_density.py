import os
import json
import math

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEOJSON_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'street_network.geojson')
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)

edges = graph['edges']
vertex_counts = [len(e['coords']) for e in edges]
print(f"Vertex counts per edge: min={min(vertex_counts)}, max={max(vertex_counts)}, mean={sum(vertex_counts)/len(vertex_counts):.1f}")

# Check distances between consecutive vertices
vertex_distances = []
long_segments = []
for e in edges:
    coords = e['coords']
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i+1]
        d = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) * 111320.0
        vertex_distances.append(d)
        if d > 30.0:
            long_segments.append((e['edge_id'], e['name'], e['length_m'], len(coords), d))

print(f"Distances between consecutive vertices (m): min={min(vertex_distances):.1f}, max={max(vertex_distances):.1f}, mean={sum(vertex_distances)/len(vertex_distances):.1f}")
print(f"Segments with distance > 30m between consecutive vertices: {len(long_segments)}")
for ls in long_segments[:10]:
    print(f"  Edge {ls[0]} ({ls[1]}): total len={ls[2]}m, num coords={ls[3]}, max gap={ls[4]:.1f}m")
