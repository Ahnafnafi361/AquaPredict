import json
from collections import defaultdict

with open("public/data/m6_drainage_network.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
conduits = data["conduits"]

# Check for cycles in forward_adj
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

# Check DAG via topological sort
queue = [n for n, deg in in_degree.items() if deg == 0]
visited = []
in_deg_copy = dict(in_degree)

while queue:
    curr = queue.pop(0)
    visited.append(curr)
    for neighbor, cid in adj.get(curr, []):
        in_deg_copy[neighbor] -= 1
        if in_deg_copy[neighbor] == 0:
            queue.append(neighbor)

total_graph_nodes = len(in_degree)
print(f"Total nodes with connected conduits: {total_graph_nodes}")
print(f"Nodes visited in topological sort: {len(visited)}")
if len(visited) == total_graph_nodes:
    print("Graph is a strict DAG (NO cycles)!")
else:
    print(f"Graph has cycles! {total_graph_nodes - len(visited)} nodes in cycles.")
