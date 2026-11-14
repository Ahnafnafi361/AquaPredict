"""Audit all 210 edges for endpoints, no consecutive duplicates, parity, and graph sync."""
import os, sys, json, subprocess, tempfile

ROOT = r"c:\Users\ASUS\Desktop\AquaPredict"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from route_planner import DrainageInformedRoutingGraph, densify_polyline, haversine_distance

BRIDGE = os.path.join(ROOT, "scripts", "m7_js_parity_bridge.js")
GRAPH_PATH = os.path.join(ROOT, "public", "data", "m7_routing_graph.json")

pub = json.load(open(GRAPH_PATH, encoding="utf-8"))
edges = pub["edges"]

# 1. Check endpoints & no duplicate consecutive points across all 210 edges
endpoint_failures = []
duplicate_consecutive_failures = []
min_consecutive_distances = []

for e in edges:
    eid = e["edge_id"]
    coords = e["coords"]
    dens = densify_polyline(coords, step_m=10.0)

    # Start and end coordinates must remain unchanged (within 6 decimal places)
    expected_start = [round(coords[0][0], 6), round(coords[0][1], 6)]
    expected_end = [round(coords[-1][0], 6), round(coords[-1][1], 6)]

    if dens[0] != expected_start:
        endpoint_failures.append((eid, "start", dens[0], expected_start))
    if dens[-1] != expected_end:
        endpoint_failures.append((eid, "end", dens[-1], expected_end))

    # Check for duplicate consecutive points
    for i in range(len(dens) - 1):
        p1, p2 = dens[i], dens[i + 1]
        dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        min_consecutive_distances.append(dist)
        if dist <= 0.001 or p1 == p2:
            duplicate_consecutive_failures.append((eid, i, p1, p2, dist))

print(f"Total edges audited: {len(edges)}")
print(f"Endpoint preservation failures: {len(endpoint_failures)}")
print(f"Duplicate consecutive point failures: {len(duplicate_consecutive_failures)}")
print(f"Minimum distance between any two consecutive sampled points: {min(min_consecutive_distances):.3f} m")
print(f"Maximum distance between any two consecutive sampled points: {max(min_consecutive_distances):.3f} m")

# 2. Densification parity across all 210 edges against actual JS bridge
dcases = [{"id": f"e{e['edge_id']}", "coords": e["coords"]} for e in edges]
with tempfile.TemporaryDirectory() as td:
    cp, op = os.path.join(td, "c.json"), os.path.join(td, "o.json")
    json.dump({"contexts": {}, "densify": dcases, "costs": []}, open(cp, "w"))
    subprocess.run(["node", BRIDGE, cp, op], check=True)
    js = json.load(open(op))["densify"]

parity_mismatches = []
total_sample_points = 0
for dc, jr in zip(dcases, js):
    py_samples = densify_polyline(dc["coords"], step_m=10.0)
    js_samples = jr["samples"]
    total_sample_points += len(py_samples)
    if py_samples != js_samples:
        parity_mismatches.append((dc["id"], len(py_samples), len(js_samples)))

print(f"Total polyline sample points compared: {total_sample_points}")
print(f"Python vs JS polyline sample mismatches across all 210 edges: {len(parity_mismatches)}")

# 3. Graph synchronization check: freshly built graph vs m7_routing_graph.json
g = DrainageInformedRoutingGraph()
g.build_graph()

fields = ["from_node", "to_node", "length_m", "coords", "susc_mean", "susc_max", "nearby_conduit_ids", "one_way"]
sync_diffs = {f: 0 for f in fields}
for a, b in zip(g.edges, edges):
    for f in fields:
        if a[f] != b[f]:
            sync_diffs[f] += 1

print(f"Graph synchronization diffs: {sync_diffs}")
print(f"Graph nodes count: {len(g.nodes)} (JSON: {len(pub['nodes'])}), identical coords: {[n['coords'] for n in g.nodes] == [n['coords'] for n in pub['nodes']]}")
