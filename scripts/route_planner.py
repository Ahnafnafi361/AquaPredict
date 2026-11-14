"""
AquaPredict Milestone 7 (M7) — Safest Route Planner Engine

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

# Documented Experimental Screening Thresholds (Prototypes, NOT empirical certifications)
EXPERIMENTAL_THRESHOLDS = {
    "pedestrian": {
        "caution_depth_m": 0.10,      # 10 cm (~ankle depth; difficult/unpleasant to wade)
        "impassable_depth_m": 0.25,   # 25 cm (~shin/knee depth; hazardous footing/sweeping risk)
        "speed_mps": WALKING_SPEED_MPS,
        "description": "Experimental screening thresholds for pedestrian footing stability and curb-height splash."
    },
    "vehicle": {
        "caution_depth_m": 0.15,      # 15 cm (~6 inches; curb level / exhaust splash)
        "impassable_depth_m": 0.30,   # 30 cm (~12 inches; typical passenger sedan air intake stall / float limit)
        "speed_mph": DEFAULT_VEHICLE_SPEED_MPH,
        "description": "Experimental screening thresholds for standard passenger vehicles. High-clearance vehicles differ."
    }
}

# Documented Default Cost Function Weights
DEFAULT_WEIGHTS = {
    "w_susc": 1.0,      # Terrain susceptibility weight (EWSI [0.0 - 1.0])
    "w_depth": 1.0,     # Modelled ponding depth penalty weight
    "w_drain": 1.0,     # M6 conduit capacity screening penalty weight
    "w_uncert": 1.0     # Data uncertainty penalty weight
}


def determine_recommendation(alternatives, mode="pedestrian"):
    """
    Evaluate candidate routes and determine recommended route with clear scientific rationale.
    
    Returns:
    - recommended_key: 'lowest_exposure', 'shortest', or 'drainage_informed'
    - reason: plain English explanation of WHY this route is recommended
    - alerts: list of specific waterlogging warnings along candidate routes
    """
    thresh = EXPERIMENTAL_THRESHOLDS.get(mode, EXPERIMENTAL_THRESHOLDS["pedestrian"])
    caution_d = thresh["caution_depth_m"]
    impassable_d = thresh["impassable_depth_m"]

    shortest = alternatives.get("shortest") or alternatives.get("baseline_shortest")
    lowest_exp = alternatives.get("lowest_exposure")
    drainage = alternatives.get("drainage_informed")

    if not shortest or shortest.get("status") != "SUCCESS":
        if lowest_exp and lowest_exp.get("status") == "SUCCESS":
            return {
                "recommended_key": "lowest_exposure",
                "reason": "Lowest Waterlogging Exposure route is the only viable path found.",
                "alerts": ["Shortest path unavailable or blocked by network restrictions."]
            }
        return {
            "recommended_key": None,
            "reason": "No continuous street route found between origin and destination.",
            "alerts": ["No route available."]
        }

    s_depth = shortest.get("max_modelled_depth_m", 0.0)
    s_sub_m = shortest.get("submerged_length_m", 0.0)
    s_dist = shortest.get("total_distance_m", 0.0)

    l_depth = lowest_exp.get("max_modelled_depth_m", 0.0) if lowest_exp and lowest_exp.get("status") == "SUCCESS" else s_depth
    l_sub_m = lowest_exp.get("submerged_length_m", 0.0) if lowest_exp and lowest_exp.get("status") == "SUCCESS" else s_sub_m
    l_dist = lowest_exp.get("total_distance_m", 0.0) if lowest_exp and lowest_exp.get("status") == "SUCCESS" else s_dist

    alerts = []
    has_missing_data = shortest.get("has_missing_data", False) or (lowest_exp and lowest_exp.get("has_missing_data", False))
    passable_found = lowest_exp.get("passable_route_found", True) if lowest_exp else True

    # Missing data / uncertainty guardrail
    if has_missing_data:
        alerts.append("DATA UNCERTAINTY: Simulation depth data is unavailable or out-of-domain for parts of candidate routes. Missing data is penalized and NEVER assumed dry or safe.")

    # Network impassability guardrail
    if not passable_found:
        alerts.append(f"CRITICAL WARNING: No fully passable route exists across the network. All available paths traverse water exceeding the {mode} threshold ({impassable_d:.2f}m).")

    # Check if shortest encounters deep or impassable water
    if s_depth >= impassable_d:
        alerts.append(f"Shortest route encounters potentially impassable water ({s_depth:.2f}m >= {impassable_d:.2f}m {mode} threshold).")
    elif s_depth >= caution_d:
        alerts.append(f"Shortest route encounters cautionary waterlogging ({s_depth:.2f}m >= {caution_d:.2f}m {mode} threshold).")

    # Case 1: Dry conditions everywhere (zero or negligible water) AND all data available
    if not has_missing_data and s_depth <= 0.01 and s_sub_m <= 1.0:
        return {
            "recommended_key": "shortest",
            "reason": "Shortest Route is recommended: dry conditions (0.00m water depth) modelled across all candidate paths.",
            "alerts": alerts
        }

    # Case 1b: Zero depth recorded but missing/unmeasured data exists
    if has_missing_data and s_depth <= 0.01:
        return {
            "recommended_key": "shortest",
            "reason": "Shortest Route selected under unmeasured/missing data penalties. Note: Missing simulation data is penalized as uncertain and must NOT be treated as zero depth or proof of safety.",
            "alerts": alerts
        }

    # Case 2: Lowest exposure significantly avoids or reduces flood depth
    if lowest_exp and lowest_exp.get("status") == "SUCCESS":
        extra_dist = l_dist - s_dist

        if s_depth >= caution_d and l_depth < s_depth:
            if l_depth < impassable_d and s_depth >= impassable_d:
                reason = (
                    f"Lowest Waterlogging Exposure route is recommended: diverts around impassable inundation "
                    f"({s_depth:.2f}m on shortest path), reducing maximum depth to {l_depth:.2f}m "
                    f"({round(extra_dist):+d}m detour)."
                )
            else:
                reason = (
                    f"Lowest Waterlogging Exposure route is recommended: reduces maximum water depth from "
                    f"{s_depth:.2f}m to {l_depth:.2f}m ({round(extra_dist):+d}m detour, {l_sub_m:.0f}m submerged vs {s_sub_m:.0f}m)."
                )
            return {
                "recommended_key": "lowest_exposure",
                "reason": reason,
                "alerts": alerts
            }

        if s_sub_m > 50.0 and l_sub_m < s_sub_m * 0.5:
            reason = (
                f"Lowest Waterlogging Exposure route is recommended: cuts submerged road length from "
                f"{s_sub_m:.0f}m to {l_sub_m:.0f}m ({round(extra_dist):+d}m detour)."
            )
            return {
                "recommended_key": "lowest_exposure",
                "reason": reason,
                "alerts": alerts
            }

    # Case 3: Water is present but below caution threshold
    if s_depth < caution_d:
        return {
            "recommended_key": "shortest",
            "reason": f"Shortest Route is recommended: modelled water depth ({s_depth:.2f}m) remains below {mode} caution threshold ({caution_d:.2f}m).",
            "alerts": alerts
        }

    # Case 4: Impassable water across evaluated candidate profiles
    if l_depth >= impassable_d:
        alerts.append(f"WARNING: All evaluated candidate route profiles encounter water exceeding the {mode} impassable threshold ({impassable_d:.2f}m).")
        return {
            "recommended_key": "lowest_exposure",
            "reason": f"Lowest Exposure route has lowest relative water exposure ({l_depth:.2f}m vs {s_depth:.2f}m), but exceeds {mode} threshold ({impassable_d:.2f}m). Exercise extreme caution.",
            "alerts": alerts
        }

    return {
        "recommended_key": "lowest_exposure" if (l_depth < s_depth) else "shortest",
        "reason": f"Lowest Waterlogging Exposure route provides lower modelled water exposure ({l_depth:.2f}m vs {s_depth:.2f}m).",
        "alerts": alerts
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

    def assess_edge_waterlogging(self, coords, preset_mm=50, timestep_idx=12, mode="pedestrian"):
        """
        Conduct detailed road segment waterlogging assessment.
        
        Samples M5 simulation depths along edge polyline at ~10m intervals.
        Computes max depth, mean depth, flooded/affected length, flooded percentage,
        exposure risk tier, and mode-specific caution/impassability flags.
        
        Guarantees:
        - Explicitly tracks data availability status (VALID_PILOT vs UNAVAILABLE vs BOUNDARY_CROSSING).
        - Never silently converts missing or out-of-domain simulation data into dry (0.0m) conditions.
        """
        thresh = EXPERIMENTAL_THRESHOLDS.get(mode, EXPERIMENTAL_THRESHOLDS["pedestrian"])
        caution_th = thresh["caution_depth_m"]
        impassable_th = thresh["impassable_depth_m"]

        diag = {
            "status": "VALID_PILOT",
            "data_available": True,
            "outside_count": 0,
            "sampled_count": 0,
            "max_depth_m": 0.0,
            "mean_depth_m": 0.0,
            "affected_length_m": 0.0,
            "affected_pct": 0.0,
            "risk_tier": "Dry",
            "is_caution": False,
            "is_impassable": False,
            "uncertainty_penalty": 0.0
        }

        if not self.sim_scenarios:
            diag["status"] = "UNAVAILABLE"
            diag["data_available"] = False
            diag["reason"] = "Simulation scenarios data missing"
            diag["uncertainty_penalty"] = 80.0
            return diag

        preset_key = f"preset_{int(preset_mm)}mm"
        preset = self.sim_scenarios.get("presets", {}).get(preset_key)
        if not preset:
            diag["status"] = "UNAVAILABLE"
            diag["data_available"] = False
            diag["reason"] = f"Preset {preset_key} not found"
            diag["uncertainty_penalty"] = 80.0
            return diag

        timesteps = preset.get("timesteps", [])
        if timestep_idx < 0 or timestep_idx >= len(timesteps):
            diag["status"] = "UNAVAILABLE"
            diag["data_available"] = False
            diag["reason"] = f"Timestep {timestep_idx} out of range"
            diag["uncertainty_penalty"] = 80.0
            return diag

        ts = timesteps[timestep_idx]
        if "sparse_depths" not in ts or ts["sparse_depths"] is None:
            diag["status"] = "UNAVAILABLE"
            diag["data_available"] = False
            diag["reason"] = f"sparse_depths key missing or null in timestep {timestep_idx}"
            diag["uncertainty_penalty"] = 80.0
            return diag

        raw_sparse = ts["sparse_depths"]
        if isinstance(raw_sparse, list):
            try:
                sparse_depths = dict(raw_sparse)
            except (ValueError, TypeError):
                diag["status"] = "UNAVAILABLE"
                diag["data_available"] = False
                diag["reason"] = f"sparse_depths malformed in timestep {timestep_idx}"
                diag["uncertainty_penalty"] = 80.0
                return diag
        elif isinstance(raw_sparse, dict):
            sparse_depths = raw_sparse
        else:
            diag["status"] = "UNAVAILABLE"
            diag["data_available"] = False
            diag["reason"] = f"sparse_depths invalid type in timestep {timestep_idx}"
            diag["uncertainty_penalty"] = 80.0
            return diag

        b = PILOT_BBOX
        sample_pts = densify_polyline(coords, 10.0)
        n_samples = len(sample_pts)
        diag["sampled_count"] = n_samples

        if n_samples == 0:
            return diag

        depths = []
        outside_count = 0

        for pt in sample_pts:
            lon, lat = pt[0], pt[1]
            if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
                col = min(max(int((lon - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
                row = min(max(int((b["north"] - lat) / (b["north"] - b["south"]) * 100), 0), 99)
                flat_idx = row * 100 + col
                d = sparse_depths.get(flat_idx, 0.0)
                depths.append(d)
            else:
                outside_count += 1
                depths.append(0.0)

        diag["outside_count"] = outside_count
        if outside_count > 0:
            diag["status"] = "BOUNDARY_CROSSING"
            diag["data_available"] = False
            diag["uncertainty_penalty"] = 80.0

        max_d = max(depths) if depths else 0.0
        mean_d = sum(depths) / len(depths) if depths else 0.0
        diag["max_depth_m"] = round(max_d, 3)
        diag["mean_depth_m"] = round(mean_d, 3)

        # Count samples exceeding ponding detection threshold (> 2cm)
        flooded_samples = sum(1 for d in depths if d > 0.02)
        flooded_ratio = flooded_samples / n_samples if n_samples > 0 else 0.0

        # Calculate approximate segment length
        seg_len_m = 0.0
        for i in range(len(coords) - 1):
            seg_len_m += haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

        diag["affected_length_m"] = round(seg_len_m * flooded_ratio, 1)
        diag["affected_pct"] = round(flooded_ratio * 100.0, 1)

        # Risk tier classification
        if max_d < 0.01:
            diag["risk_tier"] = "Dry"
        elif max_d < 0.05:
            diag["risk_tier"] = "Low"
        elif max_d < 0.15:
            diag["risk_tier"] = "Moderate"
        elif max_d < 0.30:
            diag["risk_tier"] = "Elevated"
        else:
            diag["risk_tier"] = "High"

        # Caution & Impassability based on mode thresholds
        diag["is_caution"] = (max_d >= caution_th)
        diag["is_impassable"] = (max_d >= impassable_th)

        return diag

    def calculate_edge_cost(self, edge_id, preset_mm=50, timestep_idx=12, mode="pedestrian", weights=None, cost_profile="drainage_informed"):
        """
        Calculate deterministic, non-negative edge cost across routing profiles:
        - 'baseline' / 'shortest': pure distance C_base (shortest geometric path)
        - 'lowest_exposure': base distance penalized by flood depth, affected length, and mode impassability
        - 'drainage_informed': full cost function combining surface depth, EWSI, and M6 conduit loading
        - 'low_susceptibility': distance weighted by terrain EWSI only

        Guaranteed: Cost(e) >= C_base > 0
        """
        w = dict(DEFAULT_WEIGHTS)
        if weights:
            w.update(weights)

        edge = self.edges[edge_id]
        c_base = edge["length_m"]

        # 1. Baseline / Shortest profile
        if cost_profile in ("baseline", "shortest"):
            return {
                "total_cost": round(c_base, 2),
                "c_base": round(c_base, 2),
                "m_susc": 1.0,
                "p_depth": 0.0,
                "p_drain": 0.0,
                "p_uncert": 0.0,
                "max_depth_m": 0.0,
                "ewsi": round(edge["susc_mean"], 3),
                "drain_warnings": {"exceeded_count": 0, "high_count": 0, "insufficient_data_count": 0, "disconnected_count": 0},
                "depth_diag": {"status": "VALID_PILOT", "max_depth_m": 0.0}
            }

        # 2. Low-Susceptibility profile
        if cost_profile == "low_susceptibility":
            total_cost = c_base * (1.0 + edge["susc_mean"])
            return {
                "total_cost": round(total_cost, 2),
                "c_base": round(c_base, 2),
                "m_susc": round(1.0 + edge["susc_mean"], 3),
                "p_depth": 0.0,
                "p_drain": 0.0,
                "p_uncert": 0.0,
                "max_depth_m": 0.0,
                "ewsi": round(edge["susc_mean"], 3),
                "drain_warnings": {"exceeded_count": 0, "high_count": 0, "insufficient_data_count": 0, "disconnected_count": 0},
                "depth_diag": {"status": "VALID_PILOT", "max_depth_m": 0.0}
            }

        # Run road segment water assessment for Lowest Exposure and Drainage-Informed profiles
        assessment = self.assess_edge_waterlogging(edge["coords"], preset_mm, timestep_idx, mode)
        max_depth_m = assessment["max_depth_m"]
        depth_diag = assessment

        # 3. Lowest Waterlogging Exposure profile
        if cost_profile in ("lowest_exposure", "low_exposure"):
            p_depth = 0.0
            if max_depth_m > 0.0:
                if max_depth_m <= 0.01:
                    p_depth = 0.0
                elif max_depth_m <= 0.05:
                    p_depth = (max_depth_m / 0.05) * 50.0
                elif max_depth_m <= 0.15:
                    p_depth = 150.0 + ((max_depth_m - 0.05) / 0.10) * 800.0
                elif max_depth_m <= 0.25:
                    p_depth = 1000.0 + ((max_depth_m - 0.15) / 0.10) * 3000.0
                else:
                    p_depth = 4000.0 + (max_depth_m - 0.25) * 10000.0

            # Penalize segments exceeding mode thresholds
            p_threshold = 0.0
            if assessment["is_impassable"]:
                p_threshold += 20000.0
            elif assessment["is_caution"]:
                p_threshold += 500.0

            # Segment affected length penalty
            p_length = assessment["affected_length_m"] * 2.0

            # Data uncertainty penalty (never assume missing data is dry)
            p_uncert = assessment["uncertainty_penalty"]

            total_cost = c_base + p_depth + p_threshold + p_length + p_uncert
            return {
                "total_cost": round(total_cost, 2),
                "c_base": round(c_base, 2),
                "m_susc": 1.0,
                "p_depth": round(p_depth + p_threshold + p_length, 2),
                "p_drain": 0.0,
                "p_uncert": round(p_uncert, 2),
                "max_depth_m": round(max_depth_m, 3),
                "ewsi": round(edge["susc_mean"], 3),
                "drain_warnings": {"exceeded_count": 0, "high_count": 0, "insufficient_data_count": 0, "disconnected_count": 0},
                "depth_diag": depth_diag,
                "assessment": assessment
            }

        # 4. Drainage-Informed profile
        ewsi = edge["susc_mean"]
        m_susc = 1.0 + (w["w_susc"] * ewsi)

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

        # Drainage Screening Penalty (P_drain)
        p_drain = 0.0
        drain_warnings = self._screen_drainage_loading(edge["nearby_conduit_ids"], preset_mm, timestep_idx)
        p_drain = (w["w_drain"] * 100.0 * drain_warnings["exceeded_count"]) + (w["w_drain"] * 30.0 * drain_warnings["high_count"])

        # Data Uncertainty Penalty (P_uncert)
        p_uncert = assessment["uncertainty_penalty"]
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
            "depth_diag": depth_diag,
            "assessment": assessment
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
        - 'baseline' / 'shortest': pure distance C_base (shortest geometric path)
        - 'lowest_exposure': path minimizing flood water depth and exposed length, avoiding impassable roads
        - 'drainage_informed': multi-criteria cost with M1 terrain EWSI, M5 flood depth, and M6 conduit capacity
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

        # Dijkstra search with configurable impassable exclusion
        def _dijkstra_search(strict_impassable_exclusion=False):
            pq = [(0.0, start_node, [], [start_node])]
            min_costs = {start_node: 0.0}
            visited = set()

            while pq:
                curr_cost, u, edge_path, node_path = heapq.heappop(pq)

                if u in visited:
                    continue
                visited.add(u)

                if u == dest_node:
                    return edge_path, node_path

                for v, edge_id, direction in self.adj.get(u, []):
                    edge = self.edges[edge_id]

                    # Vehicle one-way constraint
                    if mode == "vehicle":
                        ow = edge["one_way"]
                        if direction == "forward" and ow == "TF":
                            continue
                        if direction == "backward" and ow == "FT":
                            continue

                    assessment = self.assess_edge_waterlogging(edge["coords"], preset_mm, timestep_idx, mode)
                    if strict_impassable_exclusion and assessment["is_impassable"]:
                        continue  # Hard exclusion: strictly avoid impassable segments

                    cost_data = self.calculate_edge_cost(edge_id, preset_mm, timestep_idx, mode, cost_profile=cost_profile)
                    e_cost = cost_data["total_cost"]

                    # If not strict (fallback pass for lowest_exposure), apply overwhelming lexicographic penalty
                    if not strict_impassable_exclusion and cost_profile in ("lowest_exposure", "low_exposure"):
                        if assessment["is_impassable"]:
                            e_cost += 10000000.0

                    new_cost = curr_cost + e_cost
                    if new_cost < min_costs.get(v, float("inf")):
                        min_costs[v] = new_cost
                        heapq.heappush(pq, (new_cost, v, edge_path + [edge_id], node_path + [v]))

            return None, None

        passable_route_found = True
        if cost_profile in ("lowest_exposure", "low_exposure"):
            # Pass 1: Strict hard exclusion of impassable segments
            edge_path, node_path = _dijkstra_search(strict_impassable_exclusion=True)
            if edge_path is None:
                # Pass 2: No 100% passable path exists in network. Run lexicographic minimal-impassable fallback.
                passable_route_found = False
                edge_path, node_path = _dijkstra_search(strict_impassable_exclusion=False)
        else:
            edge_path, node_path = _dijkstra_search(strict_impassable_exclusion=False)

        if edge_path is None:
            return {
                "status": "NO_ROUTE_FOUND",
                "message": f"No connected street path exists between intersection #{start_node} and #{dest_node}.",
                "start_node": start_node,
                "dest_node": dest_node,
                "snap_start_m": snap_start_m,
                "snap_dest_m": snap_dest_m
            }

        res = self._assemble_route_summary(
            start_coords, dest_coords, start_node, dest_node,
            snap_start_m, snap_dest_m, edge_path, node_path,
            preset_mm, timestep_idx, cost_profile, mode
        )
        res["passable_route_found"] = passable_route_found
        return res

    def _assemble_route_summary(self, start_coords, dest_coords, start_node, dest_node,
                                snap_start_m, snap_dest_m, edge_ids, node_ids,
                                preset_mm, timestep_idx, cost_profile, mode="pedestrian"):
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
        flood_exposed_segments = []
        impassable_segments_count = 0
        caution_segments_count = 0
        has_missing_data = False
        all_data_available = True

        for e_idx in edge_ids:
            edge = self.edges[e_idx]
            l_m = edge["length_m"]
            total_dist_m += l_m

            cost_data = self.calculate_edge_cost(e_idx, preset_mm, timestep_idx, mode, cost_profile=cost_profile)
            assessment = cost_data.get("assessment") or self.assess_edge_waterlogging(edge["coords"], preset_mm, timestep_idx, mode)

            total_cost += cost_data["total_cost"]
            total_uncertainty_cost += cost_data["p_uncert"]

            if not assessment.get("data_available", True) or assessment.get("status") != "VALID_PILOT":
                has_missing_data = True
                all_data_available = False

            d = assessment["max_depth_m"]
            if d > max_depth_m:
                max_depth_m = d
            depth_weighted_sum += assessment["mean_depth_m"] * l_m

            if assessment["affected_length_m"] > 0:
                submerged_length_m += assessment["affected_length_m"]
            elif d > 0.02:
                submerged_length_m += l_m

            if assessment["is_impassable"]:
                impassable_segments_count += 1
            elif assessment["is_caution"]:
                caution_segments_count += 1

            if d > 0.02:
                flood_exposed_segments.append({
                    "edge_id": e_idx,
                    "name": edge["name"],
                    "length_m": l_m,
                    "max_depth_m": d,
                    "mean_depth_m": assessment["mean_depth_m"],
                    "affected_length_m": assessment["affected_length_m"],
                    "affected_pct": assessment["affected_pct"],
                    "risk_tier": assessment["risk_tier"],
                    "is_caution": assessment["is_caution"],
                    "is_impassable": assessment["is_impassable"],
                    "coords": edge["coords"]
                })

            susc_weighted_sum += edge["susc_mean"] * l_m
            total_exceeded_drains += cost_data["drain_warnings"]["exceeded_count"]
            total_high_drains += cost_data["drain_warnings"]["high_count"]

            if edge["name"] not in street_names:
                street_names.append(edge["name"])

            detailed_edges.append({
                "edge_id": e_idx,
                "name": edge["name"],
                "length_m": l_m,
                "cost_data": cost_data,
                "assessment": assessment
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

        # Overall waterlogging exposure category
        if max_depth_m < 0.01:
            exposure_category = "Minimal (Dry)"
        elif max_depth_m < 0.05:
            exposure_category = "Low"
        elif max_depth_m < 0.15:
            exposure_category = "Moderate"
        elif max_depth_m < 0.30:
            exposure_category = "Elevated"
        else:
            exposure_category = "High / Severe"

        # Estimated travel times
        walk_time_min = round(total_dist_m / (WALKING_SPEED_MPS * 60.0), 1)
        vehicle_speed_mps = (DEFAULT_VEHICLE_SPEED_MPH * 1609.34) / 3600.0
        vehicle_time_min = round(total_dist_m / (vehicle_speed_mps * 60.0), 1)

        return {
            "status": "SUCCESS",
            "cost_profile": cost_profile,
            "mode": mode,
            "routing_type": "STATIC_SCENARIO_SNAPSHOT",
            "simulation_time_min": timestep_idx * 5,
            "snapshot_description": f"Static scenario snapshot at Minute {timestep_idx * 5} of {int(preset_mm)}mm rainfall event (uncalibrated M5 aggregate depression drawdown model; not dynamic time-dependent routing)",
            "data_available": all_data_available,
            "has_missing_data": has_missing_data,
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
            "exposure_category": exposure_category,
            "flood_exposed_segments": flood_exposed_segments,
            "flood_exposed_count": len(flood_exposed_segments),
            "impassable_segments_count": impassable_segments_count,
            "caution_segments_count": caution_segments_count,
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
        1. Shortest Route: Shortest available geometric path
        2. Lowest Waterlogging Exposure: Penalizes depth & flooded length, avoids impassable roads
        3. Drainage-Informed Route: Screened against M6 storm conduit capacity & terrain EWSI
        """
        res_shortest = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "shortest", mode)
        res_lowest_exp = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "lowest_exposure", mode)
        res_drainage = self.find_route(start_coords, dest_coords, preset_mm, timestep_idx, "drainage_informed", mode)

        alternatives = {
            "shortest": res_shortest,
            "lowest_exposure": res_lowest_exp,
            "drainage_informed": res_drainage,
            # Backwards compatibility aliases for existing test suite
            "baseline_shortest": res_shortest,
            "low_susceptibility": res_lowest_exp
        }

        rec = determine_recommendation(alternatives, mode)

        return {
            "start_coords": start_coords,
            "dest_coords": dest_coords,
            "preset_mm": preset_mm,
            "timestep_idx": timestep_idx,
            "simulation_time_min": timestep_idx * 5,
            "routing_type": "STATIC_SCENARIO_SNAPSHOT",
            "snapshot_description": f"Static scenario snapshot at Minute {timestep_idx * 5} of {int(preset_mm)}mm rainfall event (uncalibrated M5 aggregate depression drawdown model; not dynamic time-dependent routing)",
            "mode": mode,
            "recommended_profile": rec["recommended_key"],
            "recommendation_reason": rec["reason"],
            "alerts": rec["alerts"],
            "experimental_thresholds": EXPERIMENTAL_THRESHOLDS,
            "alternatives": alternatives,
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
            "experimental_thresholds": EXPERIMENTAL_THRESHOLDS,
            "assumptions": {
                "walking_speed_mps": WALKING_SPEED_MPS,
                "vehicle_speed_mph": DEFAULT_VEHICLE_SPEED_MPH,
                "pedestrian_caution_depth_m": EXPERIMENTAL_THRESHOLDS["pedestrian"]["caution_depth_m"],
                "pedestrian_impassable_depth_m": EXPERIMENTAL_THRESHOLDS["pedestrian"]["impassable_depth_m"],
                "vehicle_caution_depth_m": EXPERIMENTAL_THRESHOLDS["vehicle"]["caution_depth_m"],
                "vehicle_impassable_depth_m": EXPERIMENTAL_THRESHOLDS["vehicle"]["impassable_depth_m"],
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
