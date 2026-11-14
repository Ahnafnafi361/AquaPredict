import json
from collections import defaultdict

with open("public/data/m6_drainage_network.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
conduits = data["conduits"]
inlets = [nid for nid, nd in nodes.items() if nd["node_type"] == "Inlet"]

# 1. Direct inlet allocation
# For each inlet, divide Q_inlet among outgoing conduits
# Any conduit not connected to an inlet gets 0 local intake
direct_allocation = defaultdict(float) # conduit_id -> multiplier of Q_inlet
for nid in inlets:
    outs = nodes[nid]["outgoing_conduits"]
    if outs:
        frac = 1.0 / len(outs)
        for cid in outs:
            direct_allocation[cid] += frac

print(f"Approach A (Direct Inlet Intake):")
print(f"  Conduits receiving direct inlet flow: {len(direct_allocation)}")
print(f"  Sum of multipliers: {sum(direct_allocation.values()):.2f} (out of 265 inlets; {265 - sum(direct_allocation.values()):.0f} inlets have no outgoing conduit mapped)")

# 2. Directed network conveyance (routing along DAG)
# Inlets inject 1.0 unit of flow each
# Propagate in topological order
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

# Topological sort
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

node_inflow = defaultdict(float) # node -> flow units
conduit_flow = defaultdict(float) # conduit -> flow units

for nid in inlets:
    node_inflow[nid] += 1.0

for u in topo_order:
    inflow_at_u = node_inflow[u]
    outs = nodes[u]["outgoing_conduits"]
    if outs and inflow_at_u > 0:
        frac_per_conduit = inflow_at_u / len(outs)
        for cid in outs:
            conduit_flow[cid] += frac_per_conduit
            v = conduits[cid]["to_node"]
            if v:
                node_inflow[v] += frac_per_conduit

print(f"\nApproach B (Topological DAG Conveyance):")
print(f"  Conduits carrying flow: {len([cid for cid, fl in conduit_flow.items() if fl > 0])}")
print(f"  Max conduit multiplier: {max(conduit_flow.values()):.2f}")
print(f"  Min conduit multiplier (>0): {min(fl for fl in conduit_flow.values() if fl > 0):.2f}")
print(f"  Mean conduit multiplier (>0): {sum(conduit_flow.values()) / max(len([fl for fl in conduit_flow.values() if fl > 0]), 1):.2f}")
