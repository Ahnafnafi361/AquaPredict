import json
import os
from collections import defaultdict

workspace = r"c:\Users\ASUS\Desktop\AquaPredict"
network_path = os.path.join(workspace, "public", "data", "m6_drainage_network.json")

with open(network_path, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
conduits = data["conduits"]

inlets = [nid for nid, nd in nodes.items() if nd["node_type"] == "Inlet"]
manholes = [nid for nid, nd in nodes.items() if nd["node_type"] == "Manhole"]
outfalls = [nid for nid, nd in nodes.items() if nd["node_type"] == "Outfall"]

print(f"Total Inlets: {len(inlets)}")
print(f"Total Manholes: {len(manholes)}")
print(f"Total Outfalls: {len(outfalls)}")

# Check how many outgoing conduits each inlet has
inlet_out_counts = defaultdict(int)
for nid in inlets:
    outs = nodes[nid]["outgoing_conduits"]
    inlet_out_counts[len(outs)] += 1

print("\nInlet outgoing conduits count distribution:")
for k, v in sorted(inlet_out_counts.items()):
    print(f"  {k} outgoing conduits: {v} inlets")

# Check incoming conduits for each conduit
# Which conduits have an Inlet as from_node?
direct_inlet_conduits = [cid for cid, c in conduits.items() if c["from_node"] in inlets]
print(f"\nConduits directly originating from an Inlet: {len(direct_inlet_conduits)} of {len(conduits)}")

# Conduits originating from a Manhole
manhole_conduits = [cid for cid, c in conduits.items() if c["from_node"] in manholes]
print(f"Conduits originating from a Manhole: {len(manhole_conduits)} of {len(conduits)}")

# Conduits with from_node None (dangling)
dangling_conduits = [cid for cid, c in conduits.items() if c["from_node"] is None]
print(f"Conduits originating from Dangling / None: {len(dangling_conduits)} of {len(conduits)}")

# Now examine what build_drainage_network.py currently does:
# Currently in simulate_dynamic_drainage_loading:
# Every single conduit in conduits.items() is evaluated with:
# ratio = inflow_rate_m3s / cap
# where inflow_rate_m3s is the single nominal inlet inflow rate!
print("\nCurrent method evaluates:")
print("EVERY conduit against a single inlet's nominal inflow rate inflow_rate_m3s.")
