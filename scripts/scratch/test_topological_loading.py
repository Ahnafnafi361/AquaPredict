import json
import os
from collections import defaultdict, Counter

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"
network_path = os.path.join(workspace, "public", "data", "m6_drainage_network.json")
scenarios_path = os.path.join(workspace, "public", "data", "simulation_scenarios.json")

with open(network_path, "r", encoding="utf-8") as f:
    net_data = json.load(f)
with open(scenarios_path, "r", encoding="utf-8") as f:
    sc_data = json.load(f)["presets"]

nodes = net_data["nodes"]
conduits = net_data["conduits"]
inlets = [nid for nid, nd in nodes.items() if nd["node_type"] == "Inlet"]

# Build topological flow propagation multiplier for each conduit
# Multiplier m_c: number of inlet equivalents reaching conduit c
adj = defaultdict(list)
in_degree = defaultdict(int)
for cid, c in conduits.items():
    u = c["from_node"]
    v = c["to_node"]
    if u and v:
        adj[u].append((v, cid))
        in_degree[v] += 1
        if u not in in_degree:
            in_degree[u] = 0

queue = [n for n, deg in in_degree.items() if deg == 0]
in_deg_copy = dict(in_degree)
topo_order = []
while queue:
    curr = queue.pop(0)
    topo_order.append(curr)
    for neighbor, cid in adj.get(curr, []):
        in_deg_copy[neighbor] -= 1
        if in_deg_copy[neighbor] == 0:
            queue.append(neighbor)

node_multiplier = defaultdict(float)
conduit_multiplier = defaultdict(float)

# Surface inflow enters ONLY at Inlets
for nid in inlets:
    node_multiplier[nid] += 1.0

for u in topo_order:
    inflow_u = node_multiplier[u]
    outs = nodes[u]["outgoing_conduits"]
    if outs and inflow_u > 0:
        frac = inflow_u / len(outs)
        for cid in outs:
            conduit_multiplier[cid] += frac
            v = conduits[cid]["to_node"]
            if v:
                node_multiplier[v] += frac

print(f"Conduits with contributing inlets (>0): {len([c for c, m in conduit_multiplier.items() if m > 0])}")
print(f"Conduits with NO contributing inlets (0): {len([c for c, m in conduit_multiplier.items() if m == 0])}")

# Let's test dynamic simulation loading under this reconciled flow routing:
total_inlets = len(inlets) # 265
catchment_area_per_inlet_m2 = 970000.0 / total_inlets

for pid in ["preset_10mm", "preset_50mm", "preset_100mm"]:
    sc = sc_data[pid]
    peak_ts = sc["timesteps"][12] # minute 60
    delta_rain_mm = sc["hyetograph"][11]["rain_mm"]
    inflow_per_inlet = (delta_rain_mm * 1e-3 * catchment_area_per_inlet_m2) / 300.0
    
    state_counts = Counter()
    for cid, c in conduits.items():
        cap = c["capacity_m3s"]
        reaches_outfall = c["reaches_bayou_outfall"]
        conn_type = c["connectivity_type"]
        q_cond = conduit_multiplier[cid] * inflow_per_inlet
        
        if conn_type == "dangling_boundary" and not reaches_outfall:
            st = "DISCONNECTED"
        elif cap is None or cap <= 0.0:
            st = "INSUFFICIENT_DATA"
        else:
            if q_cond <= 0.0:
                st = "NORMAL"
            else:
                ratio = q_cond / cap
                if ratio > 1.0:
                    st = "CAPACITY_EXCEEDED"
                elif ratio >= 0.70:
                    st = "HIGH_LOADING"
                else:
                    st = "NORMAL"
        state_counts[st] += 1
    
    print(f"\n{pid} at storm peak (minute 60, rain={delta_rain_mm:.2f}mm, Q_inlet={inflow_per_inlet:.4f} m3/s):")
    for st, cnt in sorted(state_counts.items()):
        print(f"  {st:<20}: {cnt}")
    print(f"  Total conduits: {sum(state_counts.values())}")
