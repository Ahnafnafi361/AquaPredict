import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')

with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
    graph = json.load(f)

edges = graph['edges']
nodes = graph['nodes']

print(f"Node 143 coords: {nodes[143]['coords']}")
connected_143 = [e for e in edges if e['from_node'] == 143 or e['to_node'] == 143]
print(f"Edges connected to Node 143: {len(connected_143)}")
for e in connected_143:
    print(f"  Edge {e['edge_id']} ({e['name']}): from {e['from_node']} to {e['to_node']}, one_way={e['one_way']}")
