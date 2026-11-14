import json

with open("public/data/m6_drainage_network.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
conduits = data["conduits"]

# Let's inspect the graph structure from Inlets
inlets = [nid for nid, nd in nodes.items() if nd["node_type"] == "Inlet"]
manholes = [nid for nid, nd in nodes.items() if nd["node_type"] == "Manhole"]
outfalls = [nid for nid, nd in nodes.items() if nd["node_type"] == "Outfall"]

# For each inlet, trace outgoing paths
# How many conduits are in paths originating at inlets?
inlet_conduits = set()
for nid in inlets:
    for cid in nodes[nid]["outgoing_conduits"]:
        inlet_conduits.add(cid)

print(f"Direct inlet outgoing conduits: {len(inlet_conduits)}")

# If we traverse downstream from each inlet:
downstream_from_inlets = set(inlet_conduits)
queue = list(inlet_conduits)
visited_conduits = set(inlet_conduits)

while queue:
    cid = queue.pop(0)
    to_node = conduits[cid]["to_node"]
    if to_node and to_node in nodes:
        for next_cid in nodes[to_node]["outgoing_conduits"]:
            if next_cid not in visited_conduits:
                visited_conduits.add(next_cid)
                queue.append(next_cid)

print(f"Total conduits reachable downstream from inlets: {len(visited_conduits)} of {len(conduits)}")
print(f"Conduits with NO inlet upstream: {len(conduits) - len(visited_conduits)}")
