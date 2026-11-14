import os
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
M6_NET_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm6_drainage_network.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)
with open(M6_NET_PATH, 'r', encoding='utf-8') as f:
    m6_net = json.load(f)

conduits = m6_net.get('conduits', {})
loading = m6_net.get('dynamic_simulation_loading', {})

edges = graph['edges']
edges_with_both = []

for preset in [10, 25, 50, 75, 100]:
    p_key = f"preset_{preset}mm"
    timesteps = loading.get(p_key, {}).get('timesteps', [])
    for t_idx, ts in enumerate(timesteps):
        base_inflow = ts.get('inflow_rate_per_inlet_m3s', 0.0)
        for e in edges:
            cids = e.get('nearby_conduit_ids', [])
            exceeded = 0
            high = 0
            insufficient = 0
            for cid in cids:
                c = conduits.get(cid)
                if not c: continue
                is_calc = c.get('capacity_status', '').startswith('CALCULAT') and c.get('capacity_m3s', 0) > 0
                if not is_calc:
                    insufficient += 1
                else:
                    q = c.get('contributing_inlet_fraction', 0.0) * base_inflow
                    cap = c.get('capacity_m3s', 1.0)
                    r = q / cap if cap > 0 else 0
                    if r > 1.0:
                        exceeded += 1
                    elif r >= 0.70:
                        high += 1
            if exceeded > 0 and high > 0:
                edges_with_both.append((preset, t_idx, e['edge_id'], exceeded, high))

print(f"Total instances where edge has BOTH exceeded and high conduits: {len(edges_with_both)}")
if edges_with_both:
    print(f"Sample instances: {edges_with_both[:5]}")
