import os
import json
import math
from collections import defaultdict, Counter

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEOJSON_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'street_network.geojson')
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
META_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_route_planner_meta.json')
M5_SIM_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json')
M5_META_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm5_simulation_meta.json')
M6_NET_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm6_drainage_network.json')
SUSC_GRID_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'susceptibility_grid.json')

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def run_audit():
    print("=" * 70)
    print("M7 ROUTE PLANNER INDEPENDENT AUDIT")
    print("=" * 70)

    # 1. Load Files
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    with open(META_PATH, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    # --- 1. Street Network Feature & Edge Counts ---
    features = geojson.get('features', [])
    num_features = len(features)
    geom_types = Counter(f['geometry']['type'] for f in features)
    total_paths = 0
    multi_path_features = 0
    for f in features:
        geom = f['geometry']
        if geom['type'] == 'LineString':
            total_paths += 1
        elif geom['type'] == 'MultiLineString':
            num_subpaths = len(geom['coordinates'])
            total_paths += num_subpaths
            if num_subpaths > 1:
                multi_path_features += 1

    print(f"1. Source Features: {num_features}")
    print(f"   Geometry types: {dict(geom_types)}")
    print(f"   Features with >1 path: {multi_path_features}")
    print(f"   Total polyline paths across all features: {total_paths}")

    graph_nodes = graph.get('nodes', [])
    graph_edges = graph.get('edges', [])
    print(f"   Graph compiled nodes: {len(graph_nodes)}")
    print(f"   Graph compiled edges: {len(graph_edges)}")

    # Check why feature count (200) != graph edge count (210)
    print(f"   Difference: {len(graph_edges) - num_features} extra edges.")
    print(f"   Does total_paths == graph_edges? {total_paths == len(graph_edges)}")

    # Directionality in GeoJSON vs Meta
    geojson_ow = Counter(str(f['properties'].get('one_way', 'BI')).strip().upper() for f in features)
    print(f"   Feature one_way values: {dict(geojson_ow)}")
    meta_ow = meta.get('network_data_audit', {}).get('directionality', {})
    print(f"   Meta one_way values: {meta_ow}")

    # Road classes in GeoJSON vs Meta
    geojson_rc = Counter(str(f['properties'].get('road_class', 'LOCAL')).strip().upper() for f in features)
    print(f"   Feature road_class values: {dict(geojson_rc)}")
    meta_rc = meta.get('network_data_audit', {}).get('road_classes', {})
    print(f"   Meta road_class values: {meta_rc}")

    # Geometry checks
    zero_len_edges = 0
    nan_coords = 0
    out_of_bbox_pts = 0
    pilot_bbox = meta.get('study_area', {}).get('bounding_box', {})
    for e in graph_edges:
        if e['length_m'] <= 0:
            zero_len_edges += 1
        for pt in e['coords']:
            if math.isnan(pt[0]) or math.isnan(pt[1]):
                nan_coords += 1
            if not (pilot_bbox['west'] - 0.005 <= pt[0] <= pilot_bbox['east'] + 0.005 and
                    pilot_bbox['south'] - 0.005 <= pt[1] <= pilot_bbox['north'] + 0.005):
                out_of_bbox_pts += 1

    print(f"   Zero length edges: {zero_len_edges}")
    print(f"   NaN coordinates: {nan_coords}")
    print(f"   Out-of-bbox points (>500m outside): {out_of_bbox_pts}")

    # Connected Components (undirected)
    adj_undirected = defaultdict(list)
    for e in graph_edges:
        u, v = e['from_node'], e['to_node']
        adj_undirected[u].append(v)
        adj_undirected[v].append(u)

    visited = set()
    components = []
    for nid in range(len(graph_nodes)):
        if nid not in visited:
            comp = []
            q = [nid]
            visited.add(nid)
            while q:
                curr = q.pop(0)
                comp.append(curr)
                for nbr in adj_undirected[curr]:
                    if nbr not in visited:
                        visited.add(nbr)
                        q.append(nbr)
            components.append(comp)

    print(f"   Undirected Connected Components: {len(components)}")
    print(f"   Component sizes: {[len(c) for c in components]}")

    # Directed Connected Components (for vehicle mode)
    adj_directed = defaultdict(list)
    for e in graph_edges:
        u, v = e['from_node'], e['to_node']
        ow = e['one_way']
        if ow != 'TF':
            adj_directed[u].append(v)
        if ow != 'FT':
            adj_directed[v].append(u)

    # Check reachability in directed graph from node 0
    visited_dir = set()
    q = [0]
    visited_dir.add(0)
    while q:
        curr = q.pop(0)
        for nbr in adj_directed[curr]:
            if nbr not in visited_dir:
                visited_dir.add(nbr)
                q.append(nbr)
    print(f"   Directed reachable nodes from node 0 (vehicle): {len(visited_dir)} / {len(graph_nodes)}")

    # Check duplicate edges (same u and v)
    edge_pairs = Counter((min(e['from_node'], e['to_node']), max(e['from_node'], e['to_node'])) for e in graph_edges)
    duplicate_pairs = {k: v for k, v in edge_pairs.items() if v > 1}
    print(f"   Multi-edges between same node pairs (parallel edges): {len(duplicate_pairs)} pairs with {sum(duplicate_pairs.values())} edges total")

    # Check self-loops (u == v)
    self_loops = [e for e in graph_edges if e['from_node'] == e['to_node']]
    print(f"   Self-loops (from_node == to_node): {len(self_loops)}")

    # Check intersection snapping
    # Min distance between distinct nodes
    min_node_dist = float('inf')
    close_node_pairs = []
    for i in range(len(graph_nodes)):
        for j in range(i + 1, len(graph_nodes)):
            d = haversine(graph_nodes[i]['coords'][0], graph_nodes[i]['coords'][1],
                          graph_nodes[j]['coords'][0], graph_nodes[j]['coords'][1])
            if d < min_node_dist:
                min_node_dist = d
            if d < 3.0:
                close_node_pairs.append((i, j, d))

    print(f"   Min distance between distinct nodes: {min_node_dist:.2f} m")
    print(f"   Node pairs closer than 3.0m: {len(close_node_pairs)}")

if __name__ == '__main__':
    run_audit()
