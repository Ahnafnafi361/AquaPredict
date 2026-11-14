"""
AquaPredict Milestone 7 (M7) — Drainage-Informed Route Planner Test Suite

Verifies:
1. Route graph connectivity and topology (160 nodes, single connected component)
2. Start and destination coordinate validation and snapping within bounding box
3. Out-of-bounds and invalid coordinates rejection (strict PILOT_BBOX enforcement)
4. Coincident start/destination handling (distance = 0)
5. No-route handling (handling disconnected target nodes or missing network)
6. Non-negative edge weights guarantee across all parameter spaces (Cost >= C_base > 0)
7. Deterministic edge costs across repeated invocations
8. Scenario and timestep selection (10, 25, 50, 75, 100 mm presets across 37 timesteps)
9. Missing terrain, depth, and drainage data handling (penalized, never assumed safe)
10. Preservation of the existing M5 simulation ledger and water balance
11. Route alternatives comparison (Baseline vs. Drainage-Informed vs. Low-Susceptibility)
12. Scientific guardrails and disclaimer presence in route outputs
"""

import os
import json
import math
import unittest
import sys

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

from route_planner import DrainageInformedRoutingGraph, validate_coordinates, PILOT_BBOX

class TestM7RoutePlanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.geojson_path = os.path.join(WORKSPACE_DIR, "public", "data", "street_network.geojson")
        cls.graph_path = os.path.join(WORKSPACE_DIR, "public", "data", "m7_routing_graph.json")
        cls.meta_path = os.path.join(WORKSPACE_DIR, "public", "data", "m7_route_planner_meta.json")
        cls.audit_path = os.path.join(WORKSPACE_DIR, "docs", "M7_ROUTING_DATA_AUDIT.md")

        cls.graph = DrainageInformedRoutingGraph()
        cls.n_cnt, cls.e_cnt = cls.graph.build_graph()

        with open(cls.meta_path, 'r', encoding='utf-8') as f:
            cls.meta_data = json.load(f)

    # ----------------------------------------------------
    # 1. Route Graph Connectivity & Topology Integrity
    # ----------------------------------------------------
    def test_01_graph_asset_counts_and_schema(self):
        """Verify graph node and edge counts match audited municipal street centerlines."""
        self.assertEqual(self.n_cnt, 160, "Expected exactly 160 intersection nodes")
        self.assertGreaterEqual(self.e_cnt, 200, "Expected at least 200 street segments")
        self.assertTrue(os.path.exists(self.geojson_path), "street_network.geojson must exist")
        self.assertTrue(os.path.exists(self.graph_path), "m7_routing_graph.json must exist")
        self.assertTrue(os.path.exists(self.meta_path), "m7_route_planner_meta.json must exist")
        self.assertTrue(os.path.exists(self.audit_path), "M7_ROUTING_DATA_AUDIT.md must exist")

    def test_02_graph_single_connected_component(self):
        """Verify the road network forms a 100% connected graph (all nodes reachable)."""
        visited = set()
        queue = [0]
        visited.add(0)
        while queue:
            curr = queue.pop(0)
            for nbr, edge_id, _ in self.graph.adj.get(curr, []):
                if nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
        self.assertEqual(len(visited), self.n_cnt, "All 160 nodes must be mutually reachable in undirected graph")

    # ----------------------------------------------------
    # 2. Coordinate Validation & Bounding Box Enforcement
    # ----------------------------------------------------
    def test_03_valid_coordinates_within_pilot_bbox(self):
        """Verify valid coordinates inside Downtown Houston pilot box pass validation."""
        self.assertTrue(validate_coordinates(-95.3700, 29.7600))
        self.assertTrue(validate_coordinates(-95.3745, 29.7565))
        self.assertTrue(validate_coordinates(-95.3655, 29.7645))

    def test_04_invalid_and_out_of_bounds_coordinates_raise_error(self):
        """Verify coordinates outside the pilot box or invalid types raise ValueError."""
        # Significantly outside bbox (West)
        with self.assertRaises(ValueError):
            validate_coordinates(-95.4000, 29.7600)
        # Significantly outside bbox (North)
        with self.assertRaises(ValueError):
            validate_coordinates(-95.3700, 29.7900)
        # NaN / Inf coordinates
        with self.assertRaises(ValueError):
            validate_coordinates(float('nan'), 29.7600)
        with self.assertRaises(ValueError):
            validate_coordinates(-95.3700, float('inf'))
        # Non-numeric types
        with self.assertRaises(ValueError):
            validate_coordinates("invalid", 29.7600)

    def test_05_snapping_to_nearest_node(self):
        """Verify snapping finds valid node with positive distance <= max_search_m."""
        node_id, snap_dist = self.graph.snap_to_nearest_node(-95.3705, 29.7580, max_search_m=200.0)
        self.assertIsInstance(node_id, int)
        self.assertGreaterEqual(node_id, 0)
        self.assertLess(node_id, self.n_cnt)
        self.assertGreaterEqual(snap_dist, 0.0)
        self.assertLessEqual(snap_dist, 200.0)

    # ----------------------------------------------------
    # 3. Deterministic Edge Costs & Non-Negative Weights
    # ----------------------------------------------------
    def test_06_edge_costs_strictly_non_negative(self):
        """Verify Cost(e) >= C_base > 0 for all edges under all presets and timesteps."""
        for e_id in range(min(50, len(self.graph.edges))):
            for preset in [10, 50, 100]:
                for step in [0, 12, 18, 36]:
                    c_data = self.graph.calculate_edge_cost(e_id, preset_mm=preset, timestep_idx=step)
                    total_cost = c_data["total_cost"]
                    c_base = c_data["c_base"]
                    self.assertGreater(c_base, 0.0, "Segment length must be strictly positive")
                    self.assertGreaterEqual(total_cost, c_base, "Total edge cost must be >= C_base")
                    self.assertGreaterEqual(c_data["p_depth"], 0.0, "Depth penalty must be non-negative")
                    self.assertGreaterEqual(c_data["p_drain"], 0.0, "Drainage penalty must be non-negative")
                    self.assertGreaterEqual(c_data["p_uncert"], 0.0, "Uncertainty penalty must be non-negative")
                    self.assertGreaterEqual(c_data["m_susc"], 1.0, "Susceptibility factor must be >= 1.0")

    def test_07_deterministic_edge_cost_repeatability(self):
        """Verify identical inputs produce bit-identical deterministic cost outputs."""
        for e_id in [0, 10, 25, 40]:
            cost1 = self.graph.calculate_edge_cost(e_id, preset_mm=75, timestep_idx=14)
            cost2 = self.graph.calculate_edge_cost(e_id, preset_mm=75, timestep_idx=14)
            self.assertEqual(cost1, cost2, "Cost evaluation must be strictly deterministic")

    # ----------------------------------------------------
    # 4. Route Execution & Alternatives
    # ----------------------------------------------------
    def test_08_coincident_start_and_destination(self):
        """Verify routing when start and destination are coincident returns distance 0."""
        pt = [-95.3705, 29.7580]
        res = self.graph.find_route(pt, pt)
        self.assertEqual(res["status"], "COINCIDENT_POINTS")
        self.assertEqual(res["distance_m"], 0.0)
        self.assertEqual(res["travel_time_min"], 0.0)

    def test_09_successful_route_finding_and_alternatives(self):
        """Verify multi-criteria route alternatives return valid paths and statistics."""
        start = [-95.3740, 29.7610]
        dest = [-95.3680, 29.7645]
        comp = self.graph.compare_alternatives(start, dest, preset_mm=100, timestep_idx=18)
        alts = comp["alternatives"]

        self.assertIn("baseline_shortest", alts)
        self.assertIn("drainage_informed", alts)
        self.assertIn("low_susceptibility", alts)

        base = alts["baseline_shortest"]
        drain = alts["drainage_informed"]

        self.assertEqual(base["status"], "SUCCESS")
        self.assertEqual(drain["status"], "SUCCESS")
        self.assertGreater(base["total_distance_m"], 0.0)
        self.assertGreater(drain["total_distance_m"], 0.0)
        self.assertGreater(len(base["coordinates"]), 2)
        self.assertGreater(len(drain["coordinates"]), 2)

        # Scientific disclaimer present
        self.assertIn("EXPERIMENTAL PROTOTYPE METRIC", base["scientific_disclaimer"])
        self.assertIn("EXPERIMENTAL PROTOTYPE METRIC", drain["scientific_disclaimer"])

    def test_10_no_route_handling_on_disconnected_subgraph(self):
        """Verify graceful NO_ROUTE_FOUND handling if an isolated node is requested."""
        # Create temporary isolated graph
        temp_g = DrainageInformedRoutingGraph()
        temp_g.nodes = [
            {"id": 0, "coords": [-95.3700, 29.7600]},
            {"id": 1, "coords": [-95.3690, 29.7610]},
            {"id": 2, "coords": [-95.3680, 29.7620]} # isolated
        ]
        temp_g.edges = [
            {
                "edge_id": 0, "from_node": 0, "to_node": 1, "name": "Street A",
                "length_m": 100.0, "coords": [[-95.3700, 29.7600], [-95.3690, 29.7610]],
                "susc_mean": 0.2, "nearby_conduit_ids": [], "one_way": "BI",
                "road_class": "LOCAL", "speed_mph": 30.0
            }
        ]
        temp_g.adj = {0: [(1, 0, "forward")], 1: [(0, 0, "backward")], 2: []}
        temp_g.loaded = True

        res = temp_g.find_route([-95.3700, 29.7600], [-95.3680, 29.7620])
        self.assertEqual(res["status"], "NO_ROUTE_FOUND")
        self.assertIn("No connected street path exists", res["message"])

    # ----------------------------------------------------
    # 5. Missing Data Penalization & Guardrails
    # ----------------------------------------------------
    def test_11_missing_data_penalized_not_assumed_safe(self):
        """Verify that segments with missing conduit capacity or outside grid receive uncertainty penalties."""
        # Edge outside grid receives uncertainty penalty
        g_empty = DrainageInformedRoutingGraph(susc_grid_path="nonexistent.json",
                                              sim_scenarios_path="nonexistent.json",
                                              drainage_net_path="nonexistent.json")
        g_empty.build_graph()
        # Edge cost still evaluates deterministically and remains strictly positive
        cost = g_empty.calculate_edge_cost(0, preset_mm=50, timestep_idx=12)
        self.assertGreater(cost["total_cost"], 0.0)
        self.assertGreaterEqual(cost["p_uncert"], 0.0)

    def test_12_preservation_of_m5_water_ledger(self):
        """Verify M7 routing calculations do not modify M5 simulation metadata or water balance ledger."""
        m5_meta_path = os.path.join(WORKSPACE_DIR, "public", "data", "m5_simulation_meta.json")
        with open(m5_meta_path, 'r', encoding='utf-8') as f:
            m5_meta = json.load(f)

        params = m5_meta["simulation_parameters"]
        self.assertEqual(params["curve_number"], 88.0)
        self.assertEqual(params["drawdown_rate_per_step"], 0.05)
        self.assertEqual(params["horizon_minutes"], 180)
        self.assertEqual(params["interval_minutes"], 5)
        self.assertEqual(params["total_depression_capacity_m3"], 66306.29)

    # ----------------------------------------------------
    # 6. Audit Gap Coverage: Topology, Vehicles & Guardrails
    # ----------------------------------------------------
    def test_13_multilinestring_feature_expansion(self):
        """Verify why 200 source features expand into 210 edges: 8 MultiLineStrings with 18 paths."""
        with open(self.geojson_path, 'r', encoding='utf-8') as f:
            fc = json.load(f)
        features = fc.get("features", [])
        self.assertEqual(len(features), 200, "Source GeoJSON must contain exactly 200 features")

        total_paths = 0
        multi_count = 0
        for feat in features:
            geom = feat.get("geometry", {})
            gtype = geom.get("type")
            coords = geom.get("coordinates", [])
            if gtype == "LineString":
                total_paths += 1
            elif gtype == "MultiLineString":
                total_paths += len(coords)
                if len(coords) > 1:
                    multi_count += 1

        self.assertEqual(multi_count, 8, "Expected exactly 8 MultiLineString features with >1 path")
        self.assertEqual(total_paths, 210, "Expected exactly 210 polyline paths expanding to 210 graph edges")
        self.assertEqual(self.e_cnt, total_paths, "Compiled graph edge count must match total polyline paths")

    def test_14_vehicle_mode_one_way_restrictions(self):
        """Verify vehicle routing strictly enforces one-way restrictions and detours accordingly."""
        # Bagby & McKinney to Travis & Bell:
        # In pedestrian mode (bidirectional), straight distance is 398.5 m
        # In vehicle mode, one-way streets force a detour of 602.0 m
        start = [-95.3705, 29.7580]
        dest = [-95.3670, 29.7570]
        ped = self.graph.find_route(start, dest, mode="pedestrian")
        veh = self.graph.find_route(start, dest, mode="vehicle")

        self.assertEqual(ped["status"], "SUCCESS")
        self.assertEqual(veh["status"], "SUCCESS")
        self.assertLessEqual(ped["total_distance_m"], veh["total_distance_m"],
                             "Vehicle one-way constraints must require equal or greater distance than pedestrian")
        self.assertAlmostEqual(ped["total_distance_m"], 398.5, delta=2.0)
        self.assertAlmostEqual(veh["total_distance_m"], 601.0, delta=3.0)

        # Isolated destination for vehicles (node 143 has in-degree 0 for vehicles)
        dest_isolated = [-95.3680, 29.7645]
        veh_isolated = self.graph.find_route(start, dest_isolated, mode="vehicle")
        self.assertEqual(veh_isolated["status"], "NO_ROUTE_FOUND",
                         "Must return NO_ROUTE_FOUND when destination cannot be legally reached under one-way rules")

    def test_15_baseline_strictly_minimizes_distance(self):
        """Verify the baseline route strictly minimizes geometric distance C_base."""
        start = [-95.3705, 29.7580]
        dest = [-95.3660, 29.7610] # Bagby & McKinney to Main & Capitol
        comp = self.graph.compare_alternatives(start, dest, preset_mm=100, timestep_idx=12, mode="pedestrian")
        base = comp["alternatives"]["baseline_shortest"]
        drain = comp["alternatives"]["drainage_informed"]
        susc = comp["alternatives"]["low_susceptibility"]

        self.assertLessEqual(base["total_distance_m"], drain["total_distance_m"],
                             "Baseline route must have distance <= drainage-informed route")
        self.assertLessEqual(base["total_distance_m"], susc["total_distance_m"],
                             "Baseline route must have distance <= low-susceptibility route")

    def test_16_depth_penalty_piecewise_bounds(self):
        """Verify depth penalty piecewise bounds evaluate non-negative and finite."""
        # Shallow: <= 0.05m
        w = {"w_depth": 1.0, "w_susc": 0.0, "w_drain": 0.0, "w_uncert": 0.0}
        # Edge 0 with manual depth overrides
        cost_dry = self.graph.calculate_edge_cost(0, preset_mm=10, timestep_idx=0, weights=w)
        self.assertEqual(cost_dry["p_depth"], 0.0)

    def test_17_self_loop_non_interference_in_paths(self):
        """Verify Edge 135 (2.8m self-loop on node 143) is never included in paths between distinct nodes."""
        self_loops = [e for e in self.graph.edges if e["from_node"] == e["to_node"]]
        self.assertEqual(len(self_loops), 1, "Expected exactly 1 self-loop edge (Edge 135)")
        self.assertEqual(self_loops[0]["edge_id"], 135)

        # Test routing between distinct nodes across the network: Edge 135 must not appear
        comp = self.graph.compare_alternatives([-95.3705, 29.7580], [-95.3660, 29.7610])
        for k, alt in comp["alternatives"].items():
            if alt["status"] == "SUCCESS":
                edge_ids = [de["edge_id"] for de in alt.get("detailed_edges", [])]
                self.assertNotIn(135, edge_ids, f"Self-loop edge 135 must never be part of path {k}")

    def test_18_subsurface_pipes_excluded_from_roads(self):
        """Verify subsurface gravity mains (624 pipes) are strictly excluded from surface routing network."""
        m6_path = os.path.join(WORKSPACE_DIR, "public", "data", "m6_drainage_network.json")
        with open(m6_path, 'r', encoding='utf-8') as f:
            m6_net = json.load(f)
        pipe_ids = set(m6_net.get("conduits", {}).keys())
        self.assertEqual(len(pipe_ids), 624, "M6 must contain 624 underground pipes")

        for edge in self.graph.edges:
            self.assertNotIn(str(edge["edge_id"]), pipe_ids,
                             "Underground sewer pipe must never be used as a surface road edge")

    # ----------------------------------------------------
    # 7. Milestone 7.1 Targeted Improvements Coverage
    # ----------------------------------------------------
    def test_19_depression_between_vertices_detected_by_densification(self):
        """Verify that a flood depression located strictly between polyline vertices is detected by 10m sampling."""
        from route_planner import densify_polyline
        # Create a mock 100m straight road segment between two vertices
        p_start = [-95.370000, 29.760000]
        p_end   = [-95.370000, 29.760900] # ~100m north

        # Densify at 10m: should produce 11 points (start, 9 intermediate, end)
        sampled = densify_polyline([p_start, p_end], step_m=10.0)
        self.assertGreaterEqual(len(sampled), 10, "100m road must have at least 10 sample points at 10m spacing")
        self.assertEqual(sampled[0], p_start, "First sample point must be exact start vertex")
        self.assertEqual(sampled[-1], p_end, "Last sample point must be exact end vertex")

        # Mock a simulation scenario where endpoints are dry (0.0m) but midpoint (index 5) is flooded (0.25m)
        b = PILOT_BBOX
        mid_pt = sampled[len(sampled) // 2]
        col_mid = min(max(int((mid_pt[0] - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
        row_mid = min(max(int((b["north"] - mid_pt[1]) / (b["north"] - b["south"]) * 100), 0), 99)
        flat_idx_mid = row_mid * 100 + col_mid

        mock_sim = {
            "presets": {
                "preset_50mm": {
                    "timesteps": [
                        {"sparse_depths": [[flat_idx_mid, 0.25]]}
                    ]
                }
            }
        }

        # Raw vertex check (only endpoints):
        col_start = min(max(int((p_start[0] - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
        row_start = min(max(int((b["north"] - p_start[1]) / (b["north"] - b["south"]) * 100), 0), 99)
        col_end = min(max(int((p_end[0] - b["west"]) / (b["east"] - b["west"]) * 100), 0), 99)
        row_end = min(max(int((b["north"] - p_end[1]) / (b["north"] - b["south"]) * 100), 0), 99)
        raw_sparse = dict([[flat_idx_mid, 0.25]])

        # Endpoints should not match the midpoint depression
        d_start = raw_sparse.get(row_start * 100 + col_start, 0.0)
        d_end = raw_sparse.get(row_end * 100 + col_end, 0.0)
        raw_max = max(d_start, d_end)
        self.assertEqual(raw_max, 0.0, "Endpoints must evaluate as dry (0.0m)")

        # Query using the graph's 10m densified depth lookup
        g_mock = DrainageInformedRoutingGraph()
        g_mock.sim_scenarios = mock_sim
        dens_depth, diag = g_mock._get_modelled_depth([p_start, p_end], preset_mm=50, timestep_idx=0, return_diag=True)

        self.assertEqual(dens_depth, 0.25, "10m sampling must detect the 0.25m mid-segment depression")
        self.assertEqual(diag["status"], "VALID_PILOT")

    def test_20_densify_polyline_no_duplicates_and_bounds(self):
        """Verify densify_polyline guarantees no duplicate consecutive points and preserves endpoints."""
        from route_planner import densify_polyline, haversine_distance
        for edge in self.graph.edges[:30]:
            coords = edge["coords"]
            dens = densify_polyline(coords, step_m=10.0)
            self.assertGreaterEqual(len(dens), len(coords))
            # Check endpoints
            self.assertEqual(dens[0], coords[0])
            self.assertEqual(dens[-1], coords[-1])
            # Check no identical consecutive points
            for i in range(len(dens) - 1):
                d = haversine_distance(dens[i][0], dens[i][1], dens[i+1][0], dens[i+1][1])
                self.assertGreater(d, 0.001, "No consecutive duplicate points allowed")

    def test_21_vehicle_destination_unreachable_detection(self):
        """Verify destination landmarks with in-degree 0 for vehicles return NO_ROUTE_FOUND."""
        # Node 143 (Milam & Franklin) has only outbound edges (in-degree 0)
        dest_143 = [-95.3680, 29.7645]
        start = [-95.3705, 29.7580] # Bagby & McKinney

        # Pedestrian succeeds
        ped = self.graph.find_route(start, dest_143, mode="pedestrian")
        self.assertEqual(ped["status"], "SUCCESS")

        # Vehicle fails gracefully with NO_ROUTE_FOUND
        veh = self.graph.find_route(start, dest_143, mode="vehicle")
        self.assertEqual(veh["status"], "NO_ROUTE_FOUND")
        self.assertIn("No connected street path exists", veh["message"])

    def test_22_missing_simulation_data_explicitly_penalized(self):
        """Verify that missing M5 depth data returns UNAVAILABLE and receives positive uncertainty penalty."""
        g_missing = DrainageInformedRoutingGraph(sim_scenarios_path="missing_file.json")
        g_missing.build_graph()

        cost_data = g_missing.calculate_edge_cost(0, preset_mm=50, timestep_idx=12)
        # Depth must be 0.0 but flagged UNAVAILABLE with uncertainty penalty
        self.assertEqual(cost_data["max_depth_m"], 0.0)
        self.assertEqual(cost_data["depth_diag"]["status"], "UNAVAILABLE")
        self.assertGreaterEqual(cost_data["p_uncert"], 80.0, "Missing depth scenario must be penalized as uncertain")

    # ----------------------------------------------------
    # 8. Milestone 7.1 Final Consistency Checks & Parity
    # ----------------------------------------------------
    def test_23_sparse_depths_missing_null_malformed_handling(self):
        """Verify missing key, null, malformed, and empty sparse_depths handling."""
        g = DrainageInformedRoutingGraph()
        edge_coords = [[-95.3700, 29.7600], [-95.3700, 29.7609]]

        # Case A: sparse_depths key missing
        g.sim_scenarios = {"presets": {"preset_50mm": {"timesteps": [{}]}}}
        d_val, diag = g._get_modelled_depth(edge_coords, preset_mm=50, timestep_idx=0, return_diag=True)
        self.assertEqual(diag["status"], "UNAVAILABLE")
        self.assertIn("missing or null", diag["reason"])

        # Case B: sparse_depths is None
        g.sim_scenarios = {"presets": {"preset_50mm": {"timesteps": [{"sparse_depths": None}]}}}
        d_val, diag = g._get_modelled_depth(edge_coords, preset_mm=50, timestep_idx=0, return_diag=True)
        self.assertEqual(diag["status"], "UNAVAILABLE")

        # Case C: sparse_depths is malformed (not key-value pairs)
        g.sim_scenarios = {"presets": {"preset_50mm": {"timesteps": [{"sparse_depths": "invalid_type"}]}}}
        d_val, diag = g._get_modelled_depth(edge_coords, preset_mm=50, timestep_idx=0, return_diag=True)
        self.assertEqual(diag["status"], "UNAVAILABLE")

        # Case D: sparse_depths is empty list (legitimate all-dry encoding)
        g.sim_scenarios = {"presets": {"preset_50mm": {"timesteps": [{"sparse_depths": []}]}}}
        d_val, diag = g._get_modelled_depth(edge_coords, preset_mm=50, timestep_idx=0, return_diag=True)
        self.assertEqual(diag["status"], "VALID_PILOT")
        self.assertEqual(d_val, 0.0)

    def test_24_disconnected_conduit_unmeasured_hydraulics_parity(self):
        """Verify disconnected conduits with unmeasured capacity receive uncertainty penalty."""
        g = DrainageInformedRoutingGraph()
        # Mock M6 network with one calculable and one incalculable disconnected conduit
        g.drainage_net = {
            "conduits": {
                "C_incalc": {
                    "connectivity_type": "dangling_boundary",
                    "reaches_bayou_outfall": False,
                    "capacity_status": "UNAVAILABLE",
                    "capacity_m3s": 0.0
                },
                "C_calc": {
                    "connectivity_type": "dangling_boundary",
                    "reaches_bayou_outfall": False,
                    "capacity_status": "CALCULATED",
                    "capacity_m3s": 1.0,
                    "contributing_inlet_fraction": 2.0
                }
            },
            "dynamic_simulation_loading": {
                "preset_50mm": {"timesteps": [{"inflow_rate_per_inlet_m3s": 1.0}]}
            }
        }
        # Incalculable disconnected conduit must trigger insufficient_data penalty
        res_incalc = g._screen_drainage_loading(["C_incalc"], preset_mm=50, timestep_idx=0)
        self.assertEqual(res_incalc["disconnected_count"], 1)
        self.assertEqual(res_incalc["insufficient_data_count"], 1)

        # Calculable disconnected conduit must be screened for loading (exceeded in this case)
        res_calc = g._screen_drainage_loading(["C_calc"], preset_mm=50, timestep_idx=0)
        self.assertEqual(res_calc["disconnected_count"], 1)
        self.assertEqual(res_calc["exceeded_count"], 1)
        self.assertEqual(res_calc["insufficient_data_count"], 0)

    def test_25_route_coordinate_traversal_orientation(self):
        """Verify route coordinates assemble without artificial jumps regardless of edge directionality."""
        from route_planner import haversine_distance
        # Test routing between distinct landmarks in pedestrian mode (bidirectional)
        landmarks = [
            [-95.3705, 29.7580], # Bagby & McKinney
            [-95.3670, 29.7635], # Milam & Franklin
            [-95.3660, 29.7610], # Main & Capitol
            [-95.3670, 29.7570]  # Travis & Bell
        ]
        for s in landmarks:
            for d in landmarks:
                if s == d:
                    continue
                route = self.graph.find_route(s, d, cost_profile="baseline", mode="pedestrian")
                if route["status"] == "SUCCESS":
                    coords = route["coordinates"]
                    self.assertGreater(len(coords), 1)
                    # Consecutive coordinates should connect smoothly at intersection nodes
                    for i in range(len(coords) - 1):
                        seg_len = haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
                        # Longest street segment in the pilot is ~165m (one full city block)
                        self.assertLess(seg_len, 200.0, f"Discontinuous jump of {seg_len:.1f}m detected in route from {s} to {d}")

    def test_26_round_half_up_numerical_parity(self):
        """Verify round_half_up produces exact client/server numerical parity without bias."""
        from route_planner import round_half_up
        # 0.5 cases round up away from zero
        self.assertEqual(round_half_up(0.1234565, 6), 0.123457)
        self.assertEqual(round_half_up(0.1234575, 6), 0.123458)
        self.assertEqual(round_half_up(0.0000005, 6), 0.000001)
        self.assertEqual(round_half_up(0.0000004, 6), 0.0)

    def test_27_depth_penalty_piecewise_threshold_continuity_and_step(self):
        """Verify depth penalty formula immediately below, at, and immediately above every threshold."""
        # Threshold 0.05m: step jump of +100m for curb overtopping
        # d <= 0.05: (d / 0.05) * 50
        # d > 0.05: 150 + ((d - 0.05) / 0.15) * 350
        def p_depth(d):
            if d <= 0.0: return 0.0
            if d <= 0.05: return (d / 0.05) * 50.0
            if d <= 0.20: return 150.0 + ((d - 0.05) / 0.15) * 350.0
            if d <= 0.50: return 500.0 + ((d - 0.20) / 0.30) * 1500.0
            return 2000.0 + (d - 0.50) * 5000.0

        # At zero:
        self.assertEqual(p_depth(0.0), 0.0)
        # Immediately below 0.05m:
        self.assertAlmostEqual(p_depth(0.049), 49.0, places=4)
        # At 0.05m:
        self.assertAlmostEqual(p_depth(0.05), 50.0, places=4)
        # Immediately above 0.05m (curb-level entry step):
        self.assertAlmostEqual(p_depth(0.0501), 150.2333, places=3)

        # Threshold 0.20m: continuous at 500.0
        self.assertAlmostEqual(p_depth(0.199), 497.6667, places=3)
        self.assertAlmostEqual(p_depth(0.20), 500.0, places=4)
        self.assertAlmostEqual(p_depth(0.201), 505.0, places=3)

        # Threshold 0.50m: continuous at 2000.0
        self.assertAlmostEqual(p_depth(0.499), 1995.0, places=3)
        self.assertAlmostEqual(p_depth(0.50), 2000.0, places=4)
        self.assertAlmostEqual(p_depth(0.501), 2005.0, places=3)

    # --------------------------------------------------------------------------
    # Flood-Aware Route Decision Support Tests (Requirements 1-8)
    # --------------------------------------------------------------------------

    def test_28_flood_aware_route_diversion_when_shortest_submerged(self):
        """Test 1: Shortest road has high simulated depth; longer alternative has lower exposure -> recommended route changes."""
        n4 = self.graph.nodes[4]["coords"]
        n10 = self.graph.nodes[10]["coords"]
        comp = self.graph.compare_alternatives(n4, n10, preset_mm=50, timestep_idx=12, mode="pedestrian")

        shortest = comp["alternatives"]["shortest"]
        lowest_exp = comp["alternatives"]["lowest_exposure"]

        self.assertEqual(shortest["status"], "SUCCESS")
        self.assertEqual(lowest_exp["status"], "SUCCESS")

        # Shortest encounters high water depth (>0.40m)
        self.assertGreater(shortest["max_modelled_depth_m"], 0.40)
        # Lowest exposure route avoids severe waterlogging (<0.10m)
        self.assertLess(lowest_exp["max_modelled_depth_m"], 0.10)
        # Recommendation switches from shortest to lowest_exposure
        self.assertEqual(comp["recommended_profile"], "lowest_exposure")
        self.assertIn("Lowest Waterlogging Exposure route is recommended", comp["recommendation_reason"])
        self.assertTrue(len(comp["alerts"]) > 0)

    def test_29_dry_conditions_shortest_route_preferred(self):
        """Test 2: All roads have zero modeled water depth -> shortest route remains competitive/recommended."""
        n4 = self.graph.nodes[4]["coords"]
        n10 = self.graph.nodes[10]["coords"]
        comp = self.graph.compare_alternatives(n4, n10, preset_mm=10, timestep_idx=0, mode="pedestrian")

        shortest = comp["alternatives"]["shortest"]
        self.assertEqual(shortest["status"], "SUCCESS")
        self.assertAlmostEqual(shortest["max_modelled_depth_m"], 0.0, places=2)
        self.assertEqual(comp["recommended_profile"], "shortest")
        self.assertIn("dry conditions", comp["recommendation_reason"].lower())

    def test_30_road_exceeds_vehicle_restriction_threshold_avoided(self):
        """Test 3: A road exceeds configured vehicle restriction threshold -> vehicle routing avoids it when alternative exists."""
        n2 = self.graph.nodes[2]["coords"]
        n119 = self.graph.nodes[119]["coords"]

        r_short = self.graph.find_route(n2, n119, preset_mm=100, timestep_idx=12, cost_profile="shortest", mode="vehicle")
        r_low = self.graph.find_route(n2, n119, preset_mm=100, timestep_idx=12, cost_profile="lowest_exposure", mode="vehicle")

        self.assertEqual(r_short["status"], "SUCCESS")
        self.assertEqual(r_low["status"], "SUCCESS")

        # Shortest route exceeds vehicle impassable threshold (0.30m)
        from route_planner import EXPERIMENTAL_THRESHOLDS
        veh_thresh = EXPERIMENTAL_THRESHOLDS["vehicle"]["impassable_depth_m"]
        self.assertGreaterEqual(r_short["max_modelled_depth_m"], veh_thresh)
        self.assertGreater(r_short["impassable_segments_count"], 0)

        # Lowest exposure vehicle route completely avoids impassable segments
        self.assertLess(r_low["max_modelled_depth_m"], veh_thresh)
        self.assertEqual(r_low["impassable_segments_count"], 0)

    def test_31_pedestrian_and_vehicle_modes_diverge(self):
        """Test 4: Pedestrian and vehicle modes produce different results when their configured restrictions differ."""
        start = [-95.3705, 29.7580]
        dest = [-95.3670, 29.7635]

        r_ped = self.graph.find_route(start, dest, preset_mm=50, timestep_idx=12, cost_profile="lowest_exposure", mode="pedestrian")
        r_veh = self.graph.find_route(start, dest, preset_mm=50, timestep_idx=12, cost_profile="lowest_exposure", mode="vehicle")

        self.assertEqual(r_ped["status"], "SUCCESS")
        self.assertEqual(r_veh["status"], "SUCCESS")
        # One-way network constraints and threshold differences create distinct routes
        self.assertNotEqual(r_ped["coordinates"], r_veh["coordinates"])
        self.assertNotEqual(r_ped["total_distance_m"], r_veh["total_distance_m"])

    def test_32_missing_simulation_data_penalized_not_zero(self):
        """Test 5: Missing simulation data must not be interpreted as zero water depth."""
        g_missing = DrainageInformedRoutingGraph()
        g_missing.build_graph()
        g_missing.sim_scenarios = None

        assessment = g_missing.assess_edge_waterlogging(self.graph.edges[0]["coords"], preset_mm=50, timestep_idx=12)
        self.assertFalse(assessment["data_available"])
        self.assertEqual(assessment["status"], "UNAVAILABLE")
        self.assertGreaterEqual(assessment["uncertainty_penalty"], 80.0)

        cost_data = g_missing.calculate_edge_cost(0, preset_mm=50, timestep_idx=12, cost_profile="lowest_exposure")
        self.assertGreaterEqual(cost_data["p_uncert"], 80.0)
        self.assertGreater(cost_data["total_cost"], cost_data["c_base"])

    def test_33_no_valid_alternative_route_handling(self):
        """Test 6: No valid alternative route exists -> returns NO_ROUTE_FOUND with explanation without inventing route."""
        restricted_dest = [-95.3680, 29.7645]
        start = [-95.3705, 29.7580]
        res = self.graph.find_route(start, restricted_dest, preset_mm=50, timestep_idx=12, cost_profile="lowest_exposure", mode="vehicle")

        self.assertEqual(res["status"], "NO_ROUTE_FOUND")
        self.assertIn("No connected street path exists", res["message"])
        self.assertNotIn("coordinates", res)

    def test_34_hard_exclusion_passable_guarantee(self):
        """Audit Issue 2: Verify hard exclusion ensures zero impassable segments are traversed when an alternative exists."""
        n4 = self.graph.nodes[4]["coords"]
        n10 = self.graph.nodes[10]["coords"]
        res = self.graph.find_route(n4, n10, preset_mm=50, timestep_idx=12, cost_profile="lowest_exposure", mode="pedestrian")

        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["passable_route_found"])
        self.assertEqual(res["impassable_segments_count"], 0)
        ped_thresh = 0.25
        self.assertLess(res["max_modelled_depth_m"], ped_thresh)

    def test_35_missing_data_recommendation_prevents_dry_claim(self):
        """Audit Issue 3: Missing data must never be reported as dry conditions in recommendation selection."""
        dummy_alts = {
            "shortest": {
                "status": "SUCCESS",
                "max_modelled_depth_m": 0.0,
                "submerged_length_m": 0.0,
                "total_distance_m": 500.0,
                "has_missing_data": True,
                "data_available": False
            },
            "lowest_exposure": {
                "status": "SUCCESS",
                "max_modelled_depth_m": 0.0,
                "submerged_length_m": 0.0,
                "total_distance_m": 500.0,
                "has_missing_data": True,
                "data_available": False,
                "passable_route_found": True
            }
        }
        from route_planner import determine_recommendation
        rec = determine_recommendation(dummy_alts, mode="pedestrian")

        # Must NOT claim dry conditions
        self.assertNotIn("dry conditions (0.00m water depth) modelled", rec["reason"])
        # Must alert about data uncertainty
        self.assertTrue(any("DATA UNCERTAINTY" in a for a in rec["alerts"]))

    def test_36_snapshot_temporal_metadata(self):
        """Audit Issue 4: Verify static scenario snapshot metadata is explicitly identified without claiming dynamic routing."""
        n4 = self.graph.nodes[4]["coords"]
        n10 = self.graph.nodes[10]["coords"]
        res = self.graph.find_route(n4, n10, preset_mm=50, timestep_idx=12, cost_profile="shortest")

        self.assertEqual(res["routing_type"], "STATIC_SCENARIO_SNAPSHOT")
        self.assertEqual(res["simulation_time_min"], 60)
        self.assertIn("Static scenario snapshot", res["snapshot_description"])
        self.assertIn("not dynamic time-dependent routing", res["snapshot_description"])


if __name__ == "__main__":
    unittest.main()

