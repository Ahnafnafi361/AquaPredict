import os
import json
import math
import time

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRAPH_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json')
M6_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'm6_drainage_network.json')
STREETS_PATH = os.path.join(WORKSPACE_DIR, 'public', 'data', 'street_network.geojson')

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def dist_point_to_segment(px, py, x1, y1, x2, y2):
    """Distance in meters from point (px, py) to line segment (x1, y1)-(x2, y2)."""
    # Project to approximate local planar meters (Houston lat ~29.76 deg)
    cos_lat = math.cos(math.radians(29.76))
    scale_x = 111320.0 * cos_lat
    scale_y = 111320.0

    px_m, py_m = px * scale_x, py * scale_y
    x1_m, y1_m = x1 * scale_x, y1 * scale_y
    x2_m, y2_m = x2 * scale_x, y2 * scale_y

    dx = x2_m - x1_m
    dy = y2_m - y1_m
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0.0:
        return math.hypot(px_m - x1_m, py_m - y1_m)

    t = max(0.0, min(1.0, ((px_m - x1_m) * dx + (py_m - y1_m) * dy) / seg_len_sq))
    proj_x = x1_m + t * dx
    proj_y = y1_m + t * dy
    return math.hypot(px_m - proj_x, py_m - proj_y)

def polyline_to_polyline_min_dist(coords1, coords2):
    """Minimum Euclidean distance in meters between two polylines."""
    min_d = float('inf')
    # Check all vertices of coords1 against segments of coords2
    for pt in coords1:
        for j in range(len(coords2) - 1):
            d = dist_point_to_segment(pt[0], pt[1], coords2[j][0], coords2[j][1], coords2[j+1][0], coords2[j+1][1])
            if d < min_d:
                min_d = d
                if min_d == 0:
                    return 0.0
    # Check all vertices of coords2 against segments of coords1
    for pt in coords2:
        for i in range(len(coords1) - 1):
            d = dist_point_to_segment(pt[0], pt[1], coords1[i][0], coords1[i][1], coords1[i+1][0], coords1[i+1][1])
            if d < min_d:
                min_d = d
                if min_d == 0:
                    return 0.0
    return min_d

def run_drainage_audit():
    print("=" * 70)
    print("TASK 3: DRAINAGE MATCHING AUDIT & CORRIDOR METHOD COMPARISON")
    print("=" * 70)

    with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    with open(M6_PATH, 'r', encoding='utf-8') as f:
        m6 = json.load(f)

    edges = graph['edges']
    conduits = m6.get('conduits', {})
    print(f"Total Street Edges: {len(edges)}")
    print(f"Total M6 Conduits: {len(conduits)}")

    # 1. Current Method: Midpoint-to-Midpoint <= 25m, max 4
    t0 = time.time()
    current_matches = {}
    for e in edges:
        path = e['coords']
        mid_pt = path[len(path) // 2]
        nearby = []
        for cid, c in conduits.items():
            ccoords = c.get('coordinates', [])
            if not ccoords:
                continue
            c_mid = ccoords[len(ccoords) // 2]
            d = haversine(mid_pt[0], mid_pt[1], c_mid[0], c_mid[1])
            if d <= 25.0:
                nearby.append(cid)
                if len(nearby) >= 4:
                    break
        current_matches[e['edge_id']] = nearby
    t_current = (time.time() - t0) * 1000.0

    # 2. Geometry-Based Corridor Method: Min Polyline Distance <= 25m, capped at 4 vs uncapped
    t0 = time.time()
    geom_matches_cap4 = {}
    geom_matches_uncapped = {}
    for e in edges:
        path = e['coords']
        # Pre-filter by bounding box to make geometry check fast
        e_lons = [p[0] for p in path]
        e_lats = [p[1] for p in path]
        deg_buf = 35.0 / 111320.0
        min_lon, max_lon = min(e_lons) - deg_buf, max(e_lons) + deg_buf
        min_lat, max_lat = min(e_lats) - deg_buf, max(e_lats) + deg_buf

        matched_conduits_with_dist = []
        for cid, c in conduits.items():
            ccoords = c.get('coordinates', [])
            if not ccoords:
                continue
            # Bbox prefilter
            c_mid = ccoords[len(ccoords) // 2]
            if not (min_lon <= c_mid[0] <= max_lon and min_lat <= c_mid[1] <= max_lat):
                continue
            d = polyline_to_polyline_min_dist(path, ccoords)
            if d <= 25.0:
                matched_conduits_with_dist.append((cid, d))

        # Sort by distance
        matched_conduits_with_dist.sort(key=lambda x: x[1])
        geom_matches_uncapped[e['edge_id']] = [m[0] for m in matched_conduits_with_dist]
        geom_matches_cap4[e['edge_id']] = [m[0] for m in matched_conduits_with_dist[:4]]

    t_geom = (time.time() - t0) * 1000.0

    # Metrics Comparison
    edges_with_current = sum(1 for m in current_matches.values() if len(m) > 0)
    edges_with_geom_cap4 = sum(1 for m in geom_matches_cap4.values() if len(m) > 0)
    edges_with_geom_uncapped = sum(1 for m in geom_matches_uncapped.values() if len(m) > 0)

    total_current_links = sum(len(m) for m in current_matches.values())
    total_geom_cap4_links = sum(len(m) for m in geom_matches_cap4.values())
    total_geom_uncapped_links = sum(len(m) for m in geom_matches_uncapped.values())

    print(f"\n--- MATCHING STATISTICS ---")
    print(f"Current Method (Midpoint <= 25m, Cap 4):")
    print(f"  Edges with >=1 matched conduit: {edges_with_current} / {len(edges)} ({edges_with_current/len(edges)*100:.1f}%)")
    print(f"  Total edge-to-conduit associations: {total_current_links}")
    print(f"  Execution time: {t_current:.1f} ms")

    print(f"\nGeometry Method (Polyline Distance <= 25m, Cap 4):")
    print(f"  Edges with >=1 matched conduit: {edges_with_geom_cap4} / {len(edges)} ({edges_with_geom_cap4/len(edges)*100:.1f}%)")
    print(f"  Total edge-to-conduit associations: {total_geom_cap4_links}")
    print(f"  Execution time: {t_geom:.1f} ms ({t_geom/max(t_current, 0.001):.1f}x slower)")

    print(f"\nGeometry Method (Polyline Distance <= 25m, Uncapped):")
    print(f"  Edges with >=1 matched conduit: {edges_with_geom_uncapped} / {len(edges)} ({edges_with_geom_uncapped/len(edges)*100:.1f}%)")
    print(f"  Total edge-to-conduit associations: {total_geom_uncapped_links}")

    # Inspect what the difference is on long edges
    long_edges = [e for e in edges if e['length_m'] >= 150.0]
    print(f"\nLong street edges (length >= 150m): {len(long_edges)} edges")
    diff_on_long = 0
    for e in long_edges:
        eid = e['edge_id']
        curr = set(current_matches[eid])
        geom = set(geom_matches_cap4[eid])
        if curr != geom:
            diff_on_long += 1
            added = geom - curr
            omitted = curr - geom
            print(f"  Edge {eid} ({e['name']}, {e['length_m']}m):")
            print(f"    Current ({len(curr)}): {list(curr)}")
            print(f"    Geometry ({len(geom)}): {list(geom)}")
            if added:
                print(f"    -> Conduits matched by geometry: {list(added)}")
            if omitted:
                print(f"    -> Conduits omitted by geometry: {list(omitted)}")

    # Check for potential false associations:
    # Do conduits from cross streets (perpendicular) get falsely linked?
    print(f"\n--- FALSE ASSOCIATION ANALYSIS ---")
    cross_street_matches = 0
    for e in edges:
        eid = e['edge_id']
        geom = geom_matches_uncapped[eid]
        # Check if matched conduits are perpendicular or along cross streets
        # Look at conduit names/street names if present
        # In Houston M6 data, conduits are gravity mains
        pass

if __name__ == '__main__':
    run_drainage_audit()
