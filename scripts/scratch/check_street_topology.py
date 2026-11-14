import json
import math
import os

with open('scripts/scratch/raw_street_centerlines.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

features = raw.get('features', [])
print(f"Total features: {len(features)}")

# Check coordinate bounding box and endpoints
endpoints = []
segments = []

for idx, f in enumerate(features):
    attrs = f.get('attributes', {})
    geom = f.get('geometry', {})
    paths = geom.get('paths', [])
    if not paths:
        continue
    for p in paths:
        if len(p) >= 2:
            start_pt = (round(p[0][0], 6), round(p[0][1], 6))
            end_pt = (round(p[-1][0], 6), round(p[-1][1], 6))
            endpoints.append(start_pt)
            endpoints.append(end_pt)
            segments.append({
                'id': attrs.get('OBJECTID', idx),
                'name': attrs.get('FULL_NAME', 'Unnamed'),
                'road_class': attrs.get('ROAD_CLASS', 'LOCAL'),
                'one_way': attrs.get('ONE_WAY', ' '),
                'speed': attrs.get('SPEED', 30),
                'length_ft': attrs.get('Shape.STLength()', 0.0),
                'length_m': attrs.get('Shape.STLength()', 0.0) * 0.3048,
                'path': p,
                'start': start_pt,
                'end': end_pt
            })

print(f"Processed segments: {len(segments)}")

# Cluster endpoints within 5 meters tolerance (or snap exact endpoints)
# In standard GIS, endpoints within 0.00005 deg (~5 meters) are intersections
def dist_m(p1, p2):
    # Equirectangular approximation for small area
    lat_mid = math.radians((p1[1] + p2[1]) / 2.0)
    dx = (p2[0] - p1[0]) * 111320.0 * math.cos(lat_mid)
    dy = (p2[1] - p1[1]) * 110540.0
    return math.sqrt(dx*dx + dy*dy)

# Node clustering
nodes = [] # list of (lon, lat)
node_map = {} # pt -> node_id

for pt in endpoints:
    matched = None
    for nid, npt in enumerate(nodes):
        if dist_m(pt, npt) < 3.0: # 3 meters snap tolerance
            matched = nid
            break
    if matched is None:
        matched = len(nodes)
        nodes.append(pt)
    node_map[pt] = matched

print(f"Total unique intersection nodes discovered (3m snap): {len(nodes)}")

# Build adjacency
adj = {i: [] for i in range(len(nodes))}
for s in segments:
    u = node_map[s['start']]
    v = node_map[s['end']]
    ow = s['one_way']
    # For vehicular: respect one_way. For pedestrian / walking: bidirectional.
    # We will record both!
    adj[u].append((v, s))
    if ow not in ['FT']:
        adj[v].append((u, s))
    if ow not in ['TF']:
        adj[u].append((v, s))

# Connected components analysis (undirected)
undirected_adj = {i: set() for i in range(len(nodes))}
for s in segments:
    u = node_map[s['start']]
    v = node_map[s['end']]
    undirected_adj[u].add(v)
    undirected_adj[v].add(u)

visited = set()
components = []
for i in range(len(nodes)):
    if i not in visited:
        comp = []
        q = [i]
        visited.add(i)
        while q:
            curr = q.pop()
            comp.append(curr)
            for nbr in undirected_adj[curr]:
                if nbr not in visited:
                    visited.add(nbr)
                    q.append(nbr)
        components.append(comp)

components.sort(key=len, reverse=True)
print(f"Total connected components: {len(components)}")
for idx, c in enumerate(components[:5]):
    print(f"  Component {idx+1}: {len(c)} nodes ({len(c)/len(nodes)*100:.1f}%)")

