import json
import math
import os

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
SIM_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)

with open(SIM_PATH, 'r', encoding='utf-8') as f:
    sim = json.load(f)

nodes = graph['nodes']
edges = graph['edges']
pilot_bbox = [-95.3750, 29.7560, -95.3650, 29.7650]

# Build adjacency
adj = {}
for e in edges:
    u = e['from_node']
    v = e['to_node']
    if u not in adj: adj[u] = []
    if v not in adj: adj[v] = []
    adj[u].append((v, e))
    if e.get('one_way') == 'BI':
        adj[v].append((u, e))

def snap_node(lon, lat):
    best_id = None
    best_dist = float('inf')
    for n in nodes:
        c = n['coords']
        dx = (c[0] - lon) * 111320.0 * math.cos(math.radians(29.76))
        dy = (c[1] - lat) * 110540.0
        d = math.sqrt(dx*dx + dy*dy)
        if d < best_dist:
            best_dist = d
            best_id = n['id']
    return best_id, best_dist

def get_sparse_depth_map(preset_key, step_idx):
    preset = sim.get('presets', {}).get(preset_key, {})
    timesteps = preset.get('timesteps', [])
    if step_idx < len(timesteps):
        sparse = timesteps[step_idx].get('sparse_depths', [])
        return dict(sparse)
    return {}

def assess_edge(e, depth_map, impassable_thresh=0.30):
    # Sample points along edge
    pts = e.get('coords', [])
    if not pts:
        return 0.0, False
    max_d = 0.0
    for lon, lat in pts:
        if not (pilot_bbox[0] <= lon <= pilot_bbox[2] and pilot_bbox[1] <= lat <= pilot_bbox[3]):
            continue
        gx = int(round((lon - pilot_bbox[0]) / (pilot_bbox[2] - pilot_bbox[0]) * 99))
        gy = int(round((lat - pilot_bbox[1]) / (pilot_bbox[3] - pilot_bbox[1]) * 99))
        cell_id = gy * 100 + gx
        d = depth_map.get(cell_id, 0.0)
        if d > max_d:
            max_d = d
    return max_d, max_d >= impassable_thresh

LOCATIONS = [
    # Hospitals
    {"id": "hosp_1", "name": "CHRISTUS St. Joseph Hospital (Downtown)", "category": "Hospitals", "coords": [-95.3668, 29.7492], "is_critical": True, "note": "Regional Receiving Facility"},
    {"id": "hosp_2", "name": "Good Neighbor Healthcare Center", "category": "Hospitals", "coords": [-95.3782, 29.7525], "is_critical": True, "note": "Community Health Clinic"},
    # Residential Areas
    {"id": "res_1", "name": "Sabine Island Residential District", "category": "Residential Areas", "coords": [-95.3738, 29.7628], "is_critical": False},
    {"id": "res_2", "name": "Old Sixth Ward Historic Residential", "category": "Residential Areas", "coords": [-95.3745, 29.7645], "is_critical": False},
    {"id": "res_3", "name": "Reisner Subdivision", "category": "Residential Areas", "coords": [-95.3725, 29.7638], "is_critical": False},
    {"id": "res_4", "name": "Johnson Subdivision", "category": "Residential Areas", "coords": [-95.3735, 29.7642], "is_critical": False},
    # Societies
    {"id": "soc_1", "name": "Old Sixth Ward Neighborhood Association", "category": "Societies", "coords": [-95.3745, 29.7645], "is_critical": False},
    {"id": "soc_2", "name": "Freedmen's Town Association, Inc.", "category": "Societies", "coords": [-95.3715, 29.7568], "is_critical": False},
    {"id": "soc_3", "name": "CDC of Freedmen's Town", "category": "Societies", "coords": [-95.3722, 29.7572], "is_critical": False},
    # Villages
    {"id": "vil_1", "name": "Allen Parkway Village", "category": "Villages", "coords": [-95.3740, 29.7610], "is_critical": False},
    # Communities
    {"id": "com_1", "name": "Fonde Community Center", "category": "Communities", "coords": [-95.3735, 29.7635], "is_critical": False},
    {"id": "com_2", "name": "Wesley Anchor Community House", "category": "Communities", "coords": [-95.3720, 29.7565], "is_critical": False},
    {"id": "com_3", "name": "Freedmen's Town Historic Community", "category": "Communities", "coords": [-95.3710, 29.7575], "is_critical": False}
]

print("=== RISK ASSESSMENT ACROSS PRESETS (PEAK STEP 12 = 60 MIN) ===")
for p_mm in [10, 25, 50, 75, 100]:
    p_key = f"preset_{p_mm}mm"
    depth_map = get_sparse_depth_map(p_key, 12)
    print(f"\n--- Scenario: {p_mm} mm/hr (Sparse depth cells: {len(depth_map)}) ---")
    
    # Assess all edges
    impassable_edges = set()
    for e in edges:
        md, is_imp = assess_edge(e, depth_map, 0.30)
        if is_imp:
            impassable_edges.add(e['edge_id'])
            
    print(f"Total impassable edges (>0.30m): {len(impassable_edges)} / {len(edges)}")
    
    for loc in LOCATIONS:
        nid, dist = snap_node(loc['coords'][0], loc['coords'][1])
        # Incident edges
        inc_edges = [e for e in edges if e['from_node'] == nid or e['to_node'] == nid]
        imp_inc = [e for e in inc_edges if e['edge_id'] in impassable_edges]
        
        # Determine risk
        if len(inc_edges) > 0 and len(imp_inc) == len(inc_edges):
            risk = "Community Isolation Risk"
            max_d = max(assess_edge(e, depth_map)[0] for e in inc_edges)
        elif len(imp_inc) > 0:
            risk = "Road Failure Risk"
            max_d = max(assess_edge(e, depth_map)[0] for e in imp_inc)
        else:
            risk = "No Critical Risk Detected"
            max_d = 0.0
            
        if risk != "No Critical Risk Detected":
            print(f"  * [{loc['category']}] {loc['name']}: 🔴 {risk} (Max depth {max_d:.2f}m, {len(imp_inc)}/{len(inc_edges)} access edges impassable)")
