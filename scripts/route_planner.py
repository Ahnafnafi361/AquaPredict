"""
AquaPredict Milestone 7 (M7) — Drainage-Informed Route Planner Engine

Provides:
- Graph topology builder from municipal street centerlines GeoJSON
- Coordinate validation and snapping to nearest intersection node
- Spatial association with M1 EWSI susceptibility grid
- Dynamic association with M5 simulation modelled ponding depth
- Spatial screening against M6 drainage network conduit loading
- Non-negative, deterministic edge-cost scoring suitable for Dijkstra / A*
- Alternative route comparison (Shortest Baseline vs. Drainage-Informed vs. Low-Susceptibility)
- Rigorous missing-data handling and scientific disclaimers
"""

import os
import json
import math
import heapq

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT_BBOX = {
    "west": -95.3750,
    "south": 29.7560,
    "east": -95.3650,
    "north": 29.7650
}

# Standard Walking & Vehicular Speed Assumptions
WALKING_SPEED_MPS = 1.34    # AASHTO / MUTCD default pedestrian walking speed (4.8 km/h, 3.0 mph)
DEFAULT_VEHICLE_SPEED_MPH = 30.0 # Default local street speed limit (mph)

# Documented Default Cost Function Weights
DEFAULT_WEIGHTS = {
    "w_susc": 1.0,      # Terrain susceptibility weight (EWSI [0.0 - 1.0])
    "w_depth": 1.0,     # Modelled ponding depth penalty weight
    "w_drain": 1.0,     # M6 conduit capacity screening penalty weight
    "w_uncert": 1.0     # Data uncertainty penalty weight
}

def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate great-circle distance between two points in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def validate_coordinates(lon, lat, allow_boundary_buffer_m=50.0):
    """
    Validate that coordinates are valid numbers and fall within the pilot study bounding box.
    Allows small buffer (e.g. 50m) for street boundary intersection nodes.
    """
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        raise ValueError(f"Invalid coordinate types: lon={lon}, lat={lat}")
    if math.isnan(lon) or math.isnan(lat) or math.isinf(lon) or math.isinf(lat):
        raise ValueError(f"Coordinates contain NaN or Inf: lon={lon}, lat={lat}")

    # Convert 50m buffer to degrees approximately
    buf_deg = allow_boundary_buffer_m / 111320.0
    if not (PILOT_BBOX["west"] - buf_deg <= lon <= PILOT_BBOX["east"] + buf_deg and
            PILOT_BBOX["south"] - buf_deg <= lat <= PILOT_BBOX["north"] + buf_deg):
        raise ValueError(
            f"Coordinates ({lon:.5f}, {lat:.5f}) fall outside authoritative pilot bounding box "
            f"[-95.3750, 29.7560, -95.3650, 29.7650]."
        )
    return True


def round_half_up(val, places=6):
    """Symmetric round-half-up to guarantee numerical parity with client Math.round."""
    mult = 10 ** places
    return math.floor(val * mult + 0.5) / mult


def densify_polyline(coords, step_m=10.0):
    """
    Sample polyline coordinates at approximately step_m intervals.
    
    Guarantees:
    - Input polyline vertices are preserved as sample points.
    - Zero duplicate consecutive points (no duplicate samples at shared vertices).
    - Intermediate points are linearly interpolated in EPSG:4326.
    - Preserves exact endpoints and guarantees client/server coordinate parity.
    - Returns original list if len(coords) < 2.
    """
    if not coords or len(coords) < 2:
        return [list(c) for c in (coords or [])]

    samples = []
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]
        seg_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if seg_dist <= 0.001:
            continue
        n_steps = max(1, int(round(seg_dist / step_m)))
        for s in range(n_steps):
            frac = s / n_steps
            interp_lon = round_half_up(p1[0] + frac * (p2[0] - p1[0]), 6)
            interp_lat = round_half_up(p1[1] + frac * (p2[1] - p1[1]), 6)
            samples.append([interp_lon, interp_lat])

    # Append final endpoint
    p_last = coords[-1]
    samples.append([round_half_up(p_last[0], 6), round_half_up(p_last[1], 6)])
    return samples



class DrainageInformedRoutingGraph:
    """
    Routable network graph with multi-criteria physical and hydraulic edge costs.
    """
    def __init__(self, geojson_path=None, susc_grid_path=None, sim_scenarios_path=None, drainage_net_path=None):
        self.geojson_path = geojson_path or os.path.join(WORKSPACE_DIR, "public", "data", "street_network.geojson")
        self.susc_grid_path = susc_grid_path or os.path.join(WORKSPACE_DIR, "public", "data", "susceptibility_grid.json")
        self.sim_scenarios_path = sim_scenarios_path or os.path.join(WORKSPACE_DIR, "public", "data", "simulation_scenarios.json")
        self.drainage_net_path = drainage_net_path or os.path.join(WORKSPACE_DIR, "public", "data", "m6_drainage_network.json")

        self.nodes = []       # list of {"id": int, "coords": [lon, lat]}
        self.node_lookup = {} # (round_lon, round_lat) -> node_id
        self.edges = []       # list of edge dicts
        self.adj = {}         # node_id -> list of edge_indices
        self.susc_grid = None
        self.sim_scenarios = None
        self.drainage_net = None
        self.loaded = False

    def load_data(self):
        """Load auxiliary raster grids and drainage network if available."""
        if os.path.exists(self.susc_grid_path):
            with open(self.susc_grid_path, 'r', encoding='utf-8') as f:
                self.susc_grid = json.load(f)

        if os.path.exists(self.sim_scenarios_path):
            with open(self.sim_scenarios_path, 'r', encoding='utf-8') as f:
                self.sim_scenarios = json.load(f)

        if os.path.exists(self.drainage_net_path):
            with open(self.drainage_net_path, 'r', encoding='utf-8') as f:
                self.drainage_net = json.load(f)

    def build_graph(self, snap_tolerance_m=3.0):
        """
        Build topology nodes and edges from street_network.geojson.
        """
        if not os.path.exists(self.geojson_path):
            raise FileNotFoundError(f"Street network file not found: {self.geojson_path}")

        self.load_data()

        with open(self.geojson_path, 'r', encoding='utf-8') as f:
            fc = json.load(f)

        features = fc.get("features", [])
        if not features:
            raise ValueError(f"No features found in {self.geojson_path}")

        self.nodes = []
        self.node_lookup = {}
        self.edges = []
        self.adj = {}

        def get_or_create_node(coord):
            lon, lat = round(coord[0], 6), round(coord[1], 6)
            # Find existing node within snap tolerance
            for nid, nd in enumerate(self.nodes):
                if haversine_distance(lon, lat, nd["coords"][0], nd["coords"][1]) <= snap_tolerance_m:
                    return nid
            # Create new node
            new_id = len(self.nodes)
            self.nodes.append({"id": new_id, "coords": [lon, lat]})
            self.adj[new_id] = []
            return new_id

        edge_counter = 0
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            gtype = geom.get("type")
            coords = geom.get("coordinates", [])

            paths = []
            if gtype == "LineString":
                paths = [coords]
            elif gtype == "MultiLineString":
                paths = coords

            for path in paths:
                if len(path) < 2:
                    continue

                u = get_or_create_node(path[0])
                v = get_or_create_node(path[-1])

                # Calculate path length
                length_m = 0.0
                for i in range(len(path) - 1):
                    length_m += haversine_distance(path[i][0], path[i][1], path[i+1][0], path[i+1][1])

                one_way = str(props.get("one_way", "BI")).strip().upper()
                name = props.get("name", "Unnamed Street")
                road_class = props.get("road_class", "LOCAL")
                speed_mph = float(props.get("speed_limit_mph", DEFAULT_VEHICLE_SPEED_MPH))

                # Compute spatial M1 EWSI profile
                susc_mean, susc_max = self._sample_susc_profile(path)

                # Find nearest M6 storm conduits
                nearby_conduit_ids = self._find_nearby_conduits(path, buffer_m=25.0)

                edge_info = {
                    "edge_id": edge_counter,
                    "from_node": u,
                    "to_node": v,
                    "name": name,
                    "road_class": road_class,
                    "length_m": round(length_m, 2),
                    "speed_mph": speed_mph,
                    "one_way": one_way,
                    "coords": path,
                    "susc_mean": round(susc_mean, 3),
                    "susc_max": round(susc_max, 3),
                    "nearby_conduit_ids": nearby_conduit_ids
                }
                edge_counter += 1
                self.edges.append(edge_info)

                # Add to adjacency list
                # For walking / pedestrian mode, streets are bidirectional
                # For vehicle mode, FT or TF is respected
                self.adj[u].append((v, edge_info["edge_id"], "forward"))
                self.adj[v].append((u, edge_info["edge_id"], "backward"))

        self.loaded = True
        return len(self.nodes), len(self.edges)

    def _sample_susc_profile(self, path):
        """Sample M1 EWSI susceptibility grid along path coordinates at ~10m intervals."""
        if not self.susc_grid:
            return 0.25, 0.25  # default moderate baseline

        b = self.susc_grid.get("bbox", PILOT_BBOX)
        west, east = b["west"], b["east"]
        south, north = b["south"], b["north"]
        rows = self.susc_grid.get("rows", 100)
        cols = self.susc_grid.get("cols", 100)
        grid = self.susc_grid.get("grid", [])

        sample_pts = densify_polyline(path, 10.0)
        scores = []
        tier_weights = {"Low": 0.15, "Moderate": 0.45, "Elevated": 0.70, "High": 0.90}
        for pt in sample_pts:
            lon, lat = pt[0], pt[1]
            if west <= lon <= east and south <= lat <= north:
                col = min(max(int((lon - west) / (east - west) * cols), 0), cols - 1)
                row = min(max(int((north - lat) / (north - south) * rows), 0), rows - 1)
                cell = grid[row][col]
                scores.append(tier_weights.get(cell.get("tier"), 0.35))
            else:
                scores.append(0.35) # outside grid baseline

        if not scores:
            return 0.25, 0.25
        return sum(scores) / len(scores), max(scores)

    def _find_nearby_conduits(self, path, buffer_m=25.0):
        """Identify IDs of M6 conduits within buffer distance of edge polyline."""
        if not self.drainage_net:
            return []

        conduits = self.drainage_net.get("conduits", {})
        nearby = []
        # Sample edge mid-point
        mid_pt = path[len(path) // 2]
        for cid, c in conduits.items():
            ccoords = c.get("coordinates", [])
            if not ccoords:
                continue
            c_mid = ccoords[len(ccoords) // 2]
            dist = haversine_distance(mid_pt[0], mid_pt[1], c_mid[0], c_mid[1])
            if dist <= buffer_m:
                nearby.append(cid)
                if len(nearby) >= 4:
                    break
        return nearby

    def calculate_edge_cost(self, edge_id, preset_mm=50, timestep_idx=12, mode="pedestrian", weights=None):
        """
        Calculate deterministic, non-negative edge cost:
        Cost(e) = C_base * (1 + w_susc * EWSI) + P_depth + P_drain + P_uncert

        Guaranteed: Cost(e) >= C_base > 0
        """
        w = dict(DEFAULT_WEIGHTS)
        if weights:
            w.update(weights)

        edge = self.edges[edge_id]
        length_m = edge["length_m"]

        # 1. Base Cost (C_base)
        c_base = length_m

        # 2. Terrain Susceptibility Multiplier (M_susc)
        ewsi = edge["susc_mean"]
        m_susc = 1.0 + (w["w_susc"] * ewsi)

        # 3. Modelled Ponding Depth Penalty (P_depth)
        max_depth_m, depth_diag = self._get_modelled_depth(edge["coords"], preset_mm, timestep_idx, return_diag=True)
        p_depth = 0.0
        if max_depth_m > 0.0:
            if max_depth_m <= 0.05:
                # Shallow (< 5cm): small nuisance penalty
                p_depth = w["w_depth"] * (max_depth_m / 0.05) * 50.0
            elif max_depth_m <= 0.20:
                # Moderate (5-20cm): curb-level water
                p_depth = w["w_depth"] * (150.0 + ((max_depth_m - 0.05) / 0.15) * 350.0)
            elif max_depth_m <= 0.50:
                # Deep (20-50cm): knee-deep / vehicle risk
                p_depth = w["w_depth"] * (500.0 + ((max_depth_m - 0.20) / 0.30) * 1500.0)
            else:
                # Very Deep (> 50cm): severe inundation
                p_depth = w["w_depth"] * (2000.0 + (max_depth_m - 0.50) * 5000.0)

        # 4. Drainage Screening Penalty (P_drain)
        p_drain = 0.0
        drain_warnings = self._screen_drainage_loading(edge["nearby_conduit_ids"], preset_mm, timestep_idx)
        p_drain = (w["w_drain"] * 100.0 * drain_warnings["exceeded_count"]) + (w["w_drain"] * 30.0 * drain_warnings["high_count"])

        # 5. Data Uncertainty Penalty (P_uncert)
        # Never convert missing or unmeasured data into zero flood risk
        p_uncert = 0.0
        mid_pt = edge["coords"][len(edge["coords"]) // 2]
        is_outside = not (PILOT_BBOX["west"] <= mid_pt[0] <= PILOT_BBOX["east"] and
                         PILOT_BBOX["south"] <= mid_pt[1] <= PILOT_BBOX["north"]) or (depth_diag.get("outside_count", 0) > 0)
        if is_outside:
            p_uncert += w["w_uncert"] * 80.0

        if depth_diag.get("status") == "UNAVAILABLE":
            p_uncert += w["w_uncert"] * 80.0

        if drain_warnings["insufficient_data_count"] > 0:
            p_uncert += w["w_uncert"] * 25.0

        total_cost = (c_base * m_susc) + p_depth + p_drain + p_uncert

        return {
            "total_cost": round(total_cost, 2),
            "c_base": round(c_base, 2),
            "m_susc": round(m_susc, 3),
            "p_depth": round(p_depth, 2),
            "p_drain": round(p_drain, 2),
            "p_uncert": round(p_uncert, 2),
            "max_depth_m": round(max_depth_m, 3),
            "ewsi": round(ewsi, 3),
            "drain_warnings": drain_warnings,
            "depth_diag": depth_diag
        }

    def _get_modelled_depth(self, coords, preset_mm, timestep_idx, return_diag=False):
        """
        Query M5 simulation depth along edge coords sampled at ~10m intervals.
        Explicitly tracks whether data is unavailable or crosses boundary.
        Never silently converts unavailable or unmeasured data into zero flood depth.
        """
        diag = {
            "status": "VALID_PILOT",
            "outside_count": 0,
            "sampled_count": 0,
            "max_depth_m": 0.0
        }
        if not self.sim_scenarios:
            diag["status"] = "UNAVAILABLE"
            diag["reason"] = "Simulation scenarios data missing"
            return (0.0, diag) if return_diag else 0.0

        preset_key = f"preset_{int(preset_mm)}mm"
        preset = self.sim_scenarios.get("presets", {}).get(preset_key)
        if not preset:
            diag["status"] = "UNAVAILABLE"
            diag["reason"] = f"Preset {preset_key} not found"
            return (0.0, diag) if return_diag else 0.0

        timesteps = preset.get("timesteps", [])
        if timestep_idx < 0 or timestep_idx >= len(timesteps):
            diag["status"] = "UNAVAILABLE"
            diag["reason"] = f"Timestep {timestep_idx} out of range"
            return (0.0, diag) if return_diag else 0.0

        ts = timesteps[timestep_idx]
        if "sparse_depths" not in ts or ts["sparse_depths"] is None:
            diag["status"] = "UNAVAILABLE"
            diag["reason"] = f"sparse_depths key missing or null in timestep {timestep_idx}"
            return (0.0, diag) if return_diag else 0.0

        raw_sparse = ts["sparse_depths"]
        if isinstance(raw_sparse, list):
            try:
                sparse_depths = dict(raw_sparse)
            except (ValueError, TypeError):
                diag["status"] = "UNAVAILABLE"
                diag["reason"] = f"sparse_depths malformed in timestep {timestep_idx}"
                return (0.0, diag) if return_diag else 0.0
        elif isinstance(raw_sparse, dict):
            sparse_depths = raw_sparse
        else:
            diag["status"] = "UNAVAILABLE"
            diag["reason"] = f"sparse_depths invalid type in timestep {timestep_idx}"
            return (0.0, diag) if return_diag else 0.0

        b = PILOT_BBOX
        sample_pts = densify_polyline(coords, 10.0)
        diag["sampled_count"] = len(sample_pts)
        max_d = 0.0
        outside_count = 0

        for pt in sample_pts:
            lon, lat = pt[0], pt[1]
            if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
                col = min(max(int((lon - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
                row = min(max(int((b["north"] - lat) / (b["north"] - b["south"]) * 100), 0), 99)
                flat_idx = row * 100 + col
                d = sparse_depths.get(flat_idx, 0.0)
                if d > max_d:
                    max_d = d
            else:
                outside_count += 1

        diag["outside_count"] = outside_count
        diag["max_depth_m"] = round(max_d, 3)
        if outside_count > 0:
            diag["status"] = "BOUNDARY_CROSSING"

        return (max_d, diag) if return_diag else max_d

    def _screen_drainage_loading(self, conduit_ids, preset_mm, timestep_idx):
        """Screen loading states for nearby M6 conduits."""
        res = {"exceeded_count": 0, "high_count": 0, "insufficient_data_count": 0, "disconnected_count": 0}
        if not self.drainage_net or not conduit_ids:
            return res

        conduits = self.drainage_net.get("conduits", {})
        preset_key = f"preset_{int(preset_mm)}mm"
        loading_ts = self.drainage_net.get("dynamic_simulation_loading", {}).get(preset_key, {}).get("timesteps", [])
        base_inflow = loading_ts[timestep_idx].get("inflow_rate_per_inlet_m3s", 0.0) if (0 <= timestep_idx < len(loading_ts)) else 0.0

        for cid in conduit_ids:
            c = conduits.get(cid)
            if not c:
                continue
            is_calculable = c.get("capacity_status", "").startswith("CALCULAT") and c.get("capacity_m3s", 0) > 0
            if c.get("connectivity_type") == "dangling_boundary" and not c.get("reaches_bayou_outfall"):
                res["disconnected_count"] += 1

            # Unmeasured hydraulics precedence: incalculable conduits trigger insufficient_data penalty
            if not is_calculable:
                res["insufficient_data_count"] += 1
            else:
                q_inflow = c.get("contributing_inlet_fraction", 0.0) * base_inflow
                cap = c.get("capacity_m3s", 1.0)
                ratio = q_inflow / cap if cap > 0 else 0.0
                if ratio > 1.0:
                    res["exceeded_count"] += 1
                elif ratio >= 0.70:
                    res["high_count"] += 1
        return res

    def snap_to_nearest_node(self, lon, lat, max_search_m=250.0):
        """Find the nearest intersection node in the graph within max_search_m."""
        validate_coordinates(lon, lat)
        if not self.nodes:
            raise ValueError("Routing graph is empty. Cannot snap coordinates.")

        best_node = None
        min_dist = float("inf")
        for nd in self.nodes:
            d = haversine_distance(lon, lat, nd["coords"][0], nd["coords"][1])
            if d < min_dist:
                min_dist = d
                best_node = nd["id"]

        if min_dist > max_search_m:
            raise ValueError(
                f"No road intersection found within {max_search_m:.0f}m of coordinates "
                f"({lon:.5f}, {lat:.5f}). Nearest node is {min_dist:.1f}m away."
            )
        return best_node, round(min_dist, 1)

    def find_route(self, start_coords, dest_coords, preset_mm=50, timestep_idx=12,
                   cost_profile="drainage_informed", mode="pedestrian"):
        """
        Compute optimal route using Dijkstra's algorithm.

        cost_profile options:
        - 'baseline': pure distance C_base (shortest geometric path)
        - 'drainage_informed': full cost function with M1, M5, M6, and uncertainty
        - 'low_susceptibility': distance weighted by terrain EWSI only
        """
        if not self.loaded:
            self.build_graph()

        start_node, snap_start_m = self.snap_to_nearest_node(start_coords[0], start_coords[1])
        dest_node, snap_dest_m = self.snap_to_nearest_node(dest_coords[0], dest_coords[1])

        if start_node == dest_node:
            return {
                "status": "COINCIDENT_POINTS",
                "message": "Start and destination snapped to the exact same intersection node.",
                "distance_m": 0.0,
                "travel_time_min": 0.0,
                "coordinates": [self.nodes[start_node]["coords"]],
                "edge_count": 0,
                "snap_start_m": snap_start_m,
                "snap_dest_m": snap_dest_m
            }

        # Priority queue: (cost, current_node, path_edge_ids, path_node_ids)
        pq = [(0.0, start_node, [], [start_node])]
        min_costs = {start_node: 0.0}
        visited = set()

        while pq:
            curr_cost, u, edge_path, node_path = heapq.heappop(pq)

            if u in visited:
                continue
            visited.add(u)

            if u == dest_node:
                # Reconstruct route details
                return self._assemble_route_summary(
                    start_coords, dest_coords, start_node, dest_node,
                    snap_start_m, snap_dest_m, edge_path, node_path,
                    preset_mm, timestep_idx, cost_profile
                )

            for v, edge_id, direction in self.adj.get(u, []):
                edge = self.edges[edge_id]

                # Vehicle one-way constraint
                if mode == "vehicle":
                    ow = edge["one_way"]
                    if direction == "forward" and ow == "TF":
                        continue
                    if direction == "backward" and ow == "FT":
                        continue

                # Determine edge cost
                if cost_profile == "baseline":
                    e_cost = edge["length_m"]
                elif cost_profile == "low_susceptibility":
                    e_cost = edge["length_m"] * (1.0 + edge["susc_mean"])
                else: # 'drainage_informed'
                    cost_data = self.calculate_edge_cost(edge_id, preset_mm, timestep_idx, mode)
                    e_cost = cost_data["total_cost"]

                new_cost = curr_cost + e_cost
                if new_cost < min_costs.get(v, float("inf")):
                    min_costs[v] = new_cost
                    heapq.heappush(pq, (new_cost, v, edge_path + [edge_id], node_path + [v]))

        # No route found
        return {
            "status": "NO_ROUTE_FOUND",
            "message": f"No connected street path exists between intersection #{start_node} and #{dest_node}.",
            "start_node": start_node,
            "dest_node": dest_node,
            "snap_start_m": snap_start_m,
            "snap_dest_m": snap_dest_m
        }

    def _assemble_route_summary(self, start_coords, dest_coords, start_node, dest_node,
                                snap_start_m, snap_dest_m, edge_ids, node_ids,
                                preset_mm, timestep_idx, cost_profile):
        """Assemble comprehensive, auditable route comparison breakdown."""
        total_dist_m = 0.0
        total_cost = 0.0
        route_coords = []
        street_names = []
        max_depth_m = 0.0
        depth_weighted_sum = 0.0
        susc_weighted_sum = 0.0
        submerged_length_m = 0.0
        total_exceeded_drains = 0
        total_high_drains = 0
        total_uncertainty_cost = 0.0
        detailed_edges = []

        for e_idx in edge_ids:
            edge = self.edges[e_idx]
            l_m = edge["length_m"]
            total_dist_m += l_m

            cost_data = self.calculate_edge_cost(e_idx, preset_mm, timestep_idx)
            total_cost += cost_data["total_cost"]
            total_uncertainty_cost += cost_data["p_uncert"]

            d = cost_data["max_depth_m"]
            if d > max_depth_m:
                max_depth_m = d
            depth_weighted_sum += d * l_m
            if d > 0.05:
                submerged_length_m += l_m

            susc_weighted_sum += edge["susc_mean"] * l_m
            total_exceeded_drains += cost_data["drain_warnings"]["exceeded_count"]
            total_high_drains += cost_data["drain_warnings"]["high_count"]

            if edge["name"] not in street_names:
                street_names.append(edge["name"])

            detailed_edges.append({
                "edge_id": e_idx,
                "name": edge["name"],
                "length_m": l_m,
                "cost_data": cost_data
            })

        # Merge coordinates smoothly with strict traversal orientation anchored on start_node
        curr_node = start_node
        for e_idx in edge_ids:
            edge = self.edges[e_idx]
            if edge["from_node"] == curr_node:
                pts = edge["coords"]
                curr_node = edge["to_node"]
            elif edge["to_node"] == curr_node:
                pts = list(reversed(edge["coords"]))
                curr_node = edge["from_node"]
            else:
                d0 = haversine_distance(edge["coords"][0][0], edge["coords"][0][1], self.nodes[curr_node]["coords"][0], self.nodes[curr_node]["coords"][1])
                d1 = haversine_distance(edge["coords"][-1][0], edge["coords"][-1][1], self.nodes[curr_node]["coords"][0], self.nodes[curr_node]["coords"][1])
                pts = edge["coords"] if d0 <= d1 else list(reversed(edge["coords"]))
                curr_node = edge["to_node"] if d0 <= d1 else edge["from_node"]

            if not route_coords:
                route_coords.extend(pts)
            else:
                route_coords.extend(pts[1:])


        mean_depth_m = round(depth_weighted_sum / total_dist_m, 3) if total_dist_m > 0 else 0.0
        mean_ewsi = round(susc_weighted_sum / total_dist_m, 3) if total_dist_m > 0 else 0.25

        # Classify susceptibility tier
        if mean_ewsi < 0.35:
            susc_tier = "Low"
        elif mean_ewsi < 0.60:
            susc_tier = "Moderate"
        elif mean_ewsi < 0.80:
            susc_tier = "Elevated"
        else:
            susc_tier = "High"

        # Estimated travel times
        walk_time_min = round(total_dist_m / (WALKING_SPEED_MPS * 60.0), 1)
        vehicle_speed_mps = (DEFAULT_VEHICLE_SPEED_MPH * 1609.34) / 3600.0
        vehicle_time_min = round(total_dist_m / (vehicle_speed_mps * 60.0), 1)

        return {
            "status": "SUCCESS",
            "cost_profile": cost_profile,
            "total_distance_m": round(total_dist_m, 1),
            "total_distance_ft": round(total_dist_m * 3.28084, 1),
            "walk_time_min": walk_time_min,
            "vehicle_time_min": vehicle_time_min,
            "prototype_hazard_score": round(total_cost, 1),
            "mean_ewsi": mean_ewsi,
            "susc_tier": susc_tier,
            "max_modelled_depth_m": round(max_depth_m, 3),
            "mean_modelled_depth_m": mean_depth_m,
            "submerged_length_m": round(submerged_length_m, 1),
            "submerged_pct": round(submerged_length_m / total_dist_m * 100.0, 1) if total_dist_m > 0 else 0.0,
            "drainage_exceeded_conduits": total_exceeded_drains,
            "drainage_high_conduits": total_high_drains,
            "uncertainty_cost_penalty": round(total_uncertainty_cost, 1),
            "street_names": street_names,
            "edge_count": len(edge_ids),
            "node_count": len(node_ids),
            "snap_start_m": snap_start_m,
            "snap_dest_m": snap_dest_m,
            "start_coords": start_coords,
            "dest_coords": dest_coords,
            "preset_mm": preset_mm,
            "timestep_idx": timestep_idx,
            "coordinates": route_coords,
            "detailed_edges": detailed_edges,
            "scientific_disclaimer": (
                "EXPERIMENTAL PROTOTYPE METRIC ONLY — NOT A CERTIFIED NAVIGATION ROUTE OR FLOOD ADVISORY. "
                "Calculated scores compare relative physical screening indicators and uncalibrated model outputs. "
                "A lower modelled score does NOT guarantee safety or open road conditions in the real world."
            )
        }

    def compare_alternatives(self, start_coords, dest_coords, preset_mm=50, timestep_idx=12, mode="pedestrian"):
        """
        Compute and compare three distinct alternative routing profiles:
        1. Baseline / Shortest Distance
        2. Drainage & Hazard-Informed
        3. Low-Susceptibility
        """
        res_baseline = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "baseline", mode)
        res_drainage = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "drainage_informed", mode)
        res_susc = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "low_susceptibility", mode)

        return {
            "start_coords": start_coords,
            "dest_coords": dest_coords,
            "preset_mm": preset_mm,
            "timestep_idx": timestep_idx,
            "alternatives": {
                "baseline_shortest": res_baseline,
                "drainage_informed": res_drainage,
                "low_susceptibility": res_susc
            },
            "disclaimer": (
                "Relative prototype metrics for research demonstration. "
                "Missing or uncalibrated hydraulic information is penalized and never assumed safe."
            )
        }

    def export_graph_json(self, out_path=None):
        """Export compiled graph structure with edge costs for browser Leaflet visualization."""
        if not self.loaded:
            self.build_graph()

        out_path = out_path or os.path.join(WORKSPACE_DIR, "public", "data", "m7_routing_graph.json")
        data = {
            "title": "AquaPredict M7 Compiled Street Routing Graph",
            "milestone": "M7",
            "source": "City of Houston Enterprise GIS (DIR/LandbaseandRoads_gx/MapServer/9)",
            "bounding_box": PILOT_BBOX,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes": self.nodes,
            "edges": self.edges,
            "default_weights": DEFAULT_WEIGHTS,
            "assumptions": {
                "walking_speed_mps": WALKING_SPEED_MPS,
                "vehicle_speed_mph": DEFAULT_VEHICLE_SPEED_MPH,
                "corridor_buffer_m": 25.0,
                "polyline_sampling_interval_m": 10.0,
                "non_negative_guarantee": "Cost(e) >= C_base > 0 for all edges under all scenarios."
            }
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Exported M7 routing graph: {len(self.nodes)} nodes, {len(self.edges)} edges to {out_path}")


if __name__ == "__main__":
    print("Testing M7 DrainageInformedRoutingGraph...")
    g = DrainageInformedRoutingGraph()
    n_cnt, e_cnt = g.build_graph()
    print(f"Built graph: {n_cnt} nodes, {e_cnt} edges")
    g.export_graph_json()

    # Test route across downtown: From Bagby & McKinney (SW) to Milam & Franklin (NE near Bayou)
    start = [-95.3705, 29.7580]
    dest = [-95.3670, 29.7635]
    print(f"\nRouting from {start} to {dest} (50mm storm @ minute 60):")
    comp = g.compare_alternatives(start, dest, preset_mm=50, timestep_idx=12)
    for k, r in comp["alternatives"].items():
        print(f"\n--- {k.upper()} ---")
        print(f"  Status: {r['status']}")
        if r['status'] == 'SUCCESS':
            print(f"  Distance: {r['total_distance_m']} m ({r['total_distance_ft']} ft)")
            print(f"  Walking Time: {r['walk_time_min']} min")
            print(f"  Hazard Score: {r['prototype_hazard_score']}")
            print(f"  Max Modelled Depth: {r['max_modelled_depth_m']} m")
            print(f"  Submerged Length: {r['submerged_length_m']} m ({r['submerged_pct']}%)")
            print(f"  Susceptibility Tier: {r['susc_tier']} (EWSI: {r['mean_ewsi']})")
            print(f"  Nearby Exceeded Drains: {r['drainage_exceeded_conduits']}")
            print(f"  Streets: {', '.join(r['street_names'])}")
