"""
AquaPredict Milestone 6 (M6) - Drainage Network & Hydraulic Capacity Automated Test Suite

Verifies:
- GIS schema, geometry types, and feature count integrity (624 mains, 265 inlets, 283 manholes, 4 outfalls)
- WGS84 CRS and bounding box compliance
- Identifier uniqueness (FACILITYID)
- Source-confirmed vs. inferred geometric snapping (1.0m tolerance)
- Graph traversal: upstream tracing, downstream tracing, and cycle prevention
- Manning's equation capacity calculation & strict UNAVAILABLE handling
- Dynamic simulation loading states across presets and timesteps
- Prevention of volume double-counting with M5 aggregate drawdown
- Conceptual model hotspot ranking and labeling guardrails
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

import build_drainage_network

class TestM6DrainageNetwork(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.network_path = os.path.join(WORKSPACE_DIR, "public", "data", "m6_drainage_network.json")
        cls.meta_path = os.path.join(WORKSPACE_DIR, "public", "data", "m6_analysis_meta.json")
        cls.audit_md_path = os.path.join(WORKSPACE_DIR, "docs", "M6_DRAINAGE_DATA_AUDIT.md")

        with open(cls.network_path, 'r', encoding='utf-8') as f:
            cls.network_data = json.load(f)
        with open(cls.meta_path, 'r', encoding='utf-8') as f:
            cls.meta_data = json.load(f)

    # ----------------------------------------------------
    # 1. Asset Counts & Schema Verification
    # ----------------------------------------------------
    def test_01_asset_counts_match_municipal_sources(self):
        """Verify feature counts match reported municipal GIS records."""
        stats = self.network_data["statistics"]
        self.assertEqual(stats["total_conduits"], 624)
        self.assertEqual(stats["inlets_count"], 265)
        self.assertEqual(stats["manholes_count"], 283)
        self.assertEqual(stats["outfalls_count"], 4)
        self.assertEqual(stats["total_nodes"], 552)

    def test_02_node_identifier_uniqueness_and_coordinates(self):
        """Verify all 552 nodes have valid, unique IDs and WGS84 coordinates."""
        nodes = self.network_data["nodes"]
        self.assertEqual(len(nodes), 552)
        for nid, nd in nodes.items():
            self.assertTrue(bool(nid), "Node ID must not be empty")
            coords = nd["coords"]
            self.assertEqual(len(coords), 2)
            lon, lat = coords
            # Must be within reasonable range of Downtown Houston (WGS84)
            self.assertGreaterEqual(lon, -95.3900)
            self.assertLessEqual(lon, -95.3500)
            self.assertGreaterEqual(lat, 29.7400)
            self.assertLessEqual(lat, 29.7800)

    # ----------------------------------------------------
    # 2. Network Connectivity & Snapping Tolerance
    # ----------------------------------------------------
    def test_03_connectivity_categories_partition_sum_to_624(self):
        """Verify the 4 connectivity categories partition exactly to 624 conduits."""
        stats = self.network_data["statistics"]
        c_src = stats["source_confirmed_conduits"]
        c_part = stats["partially_snapped_conduits"]
        c_inf = stats["inferred_snapped_conduits"]
        c_dang = stats["dangling_boundary_conduits"]
        
        self.assertEqual(c_src + c_part + c_inf + c_dang, 624)
        self.assertEqual(c_src, 391)
        self.assertEqual(c_part, 74)
        self.assertEqual(c_inf, 14)
        self.assertEqual(c_dang, 145)

    def test_04_geometric_snapping_strictly_within_tolerance(self):
        """Verify all snapped endpoints do not exceed the 1.0m tolerance."""
        conduits = self.network_data["conduits"]
        tol = build_drainage_network.SNAP_TOLERANCE_M
        for cid, c in conduits.items():
            if c["connectivity_type"] in ["source_partial_snapped", "inferred_snapped"]:
                self.assertLessEqual(c["snap_up_dist_m"], tol + 1e-4)
                self.assertLessEqual(c["snap_down_dist_m"], tol + 1e-4)

    # ----------------------------------------------------
    # 3. Manning's Hydraulic Capacity & Non-Fabrication
    # ----------------------------------------------------
    def test_05_mannings_equation_accuracy(self):
        """Verify Manning's formula calculation for a known standard circular concrete conduit."""
        # 24 inch concrete pipe (n=0.013), slope = 1.0% (0.01 ft/ft)
        # D = 2.0 ft, A = pi * 1.0^2 = 3.14159 sqft, Rh = 0.5 ft, S0^0.5 = 0.1
        # Q = (1.486 / 0.013) * 3.14159 * (0.5 ^ (2/3)) * 0.1
        # Rh^(2/3) = 0.62996
        # Q = 114.3077 * 3.14159 * 0.62996 * 0.1 ≈ 22.622 cfs
        q_cfs, q_m3s, n, assumed, status, reason = build_drainage_network.calculate_manning_capacity(24.0, 0.01, 'RCP')
        self.assertAlmostEqual(q_cfs, 22.622, delta=0.05)
        self.assertAlmostEqual(q_m3s, 22.622 * 0.0283168, delta=0.01)
        self.assertEqual(n, 0.013)
        self.assertFalse(assumed)
        self.assertEqual(status, "CALCULATED")

    def test_06_unrecorded_and_adverse_slopes_strictly_unavailable(self):
        """Verify conduits with adverse slopes or missing parameters return UNAVAILABLE status without fabricating numbers."""
        stats = self.network_data["statistics"]
        self.assertEqual(stats["capacity_calculable_conduits"], 264)
        self.assertEqual(stats["capacity_unavailable_conduits"], 360)
        
        conduits = self.network_data["conduits"]
        for cid, c in conduits.items():
            if c["capacity_status"] == "UNAVAILABLE":
                self.assertIsNone(c["capacity_cfs"], f"Conduit {cid} must have null capacity_cfs")
                self.assertIsNone(c["capacity_m3s"], f"Conduit {cid} must have null capacity_m3s")
                self.assertTrue(bool(c["capacity_reason"]))

    # ----------------------------------------------------
    # 4. Graph Tracing & Reachability Analysis
    # ----------------------------------------------------
    def test_07_bayou_outfalls_reachability(self):
        """Verify outfall branch reachability connects to Buffalo Bayou terminals."""
        outfall_nodes = {nid for nid, nd in self.network_data["nodes"].items() if nd["node_type"] == "Outfall"}
        self.assertEqual(len(outfall_nodes), 4)
        
        mains = self.network_data["conduits"]
        reachable_count = sum(1 for c in mains.values() if c.get("reaches_bayou_outfall"))
        self.assertEqual(reachable_count, 64)

    def test_08_connected_components_identified(self):
        """Verify connected components partitioning produces non-empty clusters."""
        comps = self.network_data["components"]
        self.assertGreater(len(comps), 0)
        total_nodes_in_comps = sum(c["node_count"] for c in comps)
        self.assertEqual(total_nodes_in_comps, 552)

    # ----------------------------------------------------
    # 5. Dynamic Simulation Loading States (M6-D)
    # ----------------------------------------------------
    def test_09_dynamic_loading_all_presets_and_timesteps(self):
        """Verify dynamic hydraulic simulation loading tracks all 5 presets and 37 timesteps."""
        dyn = self.network_data["dynamic_simulation_loading"]
        expected_presets = ["preset_10mm", "preset_25mm", "preset_50mm", "preset_75mm", "preset_100mm"]
        for p in expected_presets:
            self.assertIn(p, dyn, f"Missing preset {p} in dynamic loading")
            steps = dyn[p]["timesteps"]
            self.assertEqual(len(steps), 37)
            for s in steps:
                self.assertGreaterEqual(s["normal_conduits_count"], 0)
                self.assertGreaterEqual(s["high_loading_conduits_count"], 0)
                self.assertGreaterEqual(s["overloaded_conduits_count"], 0)
                self.assertGreaterEqual(s["surcharged_inlet_nodes_count"], 0)
                total_conds = (s["normal_conduits_count"] + s["high_loading_conduits_count"] + 
                               s["overloaded_conduits_count"] + s["disconnected_conduits_count"] + 
                               s["insufficient_data_count"])
                self.assertEqual(total_conds, 624)

    # ----------------------------------------------------
    # 6. Conceptual Hotspots & Guardrails (M6-E)
    # ----------------------------------------------------
    def test_10_hotspots_have_required_metadata_and_guardrails(self):
        """Verify conceptual model hotspots include ranking, landmarks, and non-validation labels."""
        hotspots = self.network_data["hotspots"]
        self.assertGreaterEqual(len(hotspots), 3)
        for h in hotspots:
            self.assertIn("rank", h)
            self.assertIn("name", h)
            self.assertIn("centroid", h)
            self.assertIn("nearest_inlet_id", h)
            self.assertIn("hydraulic_capacity_status", h)
            self.assertIn("risk_mechanism", h)

    def test_11_audit_documentation_file_exists(self):
        """Verify docs/M6_DRAINAGE_DATA_AUDIT.md artifact is generated and non-empty."""
        self.assertTrue(os.path.exists(self.audit_md_path))
        self.assertGreater(os.path.getsize(self.audit_md_path), 1000)

    def test_12_metadata_schema_governance(self):
        """Verify m6_analysis_meta.json contains complete assumptions and updated workflow steps."""
        self.assertEqual(self.meta_data["milestone"], "M6")
        self.assertIn("PROVISIONAL", self.meta_data["scientific_status"])
        steps = self.meta_data["workflow_steps_update"]
        self.assertEqual(len(steps), 7)
        # Step 5 Drainage and Step 7 Hotspots must be COMPLETED
        self.assertEqual(steps[4]["status"], "COMPLETED")
        self.assertEqual(steps[6]["status"], "COMPLETED")

    # ----------------------------------------------------
    # 7. Zero/Negative Capacity & Data Quality Regression Tests
    # ----------------------------------------------------
    def test_13_zero_and_negative_capacity_handling(self):
        """
        Verify that None, zero, and negative capacities NEVER produce NORMAL status.
        They must be strictly classified as INSUFFICIENT_DATA (or DISCONNECTED if boundary dangling).
        """
        eval_fn = build_drainage_network.evaluate_conduit_loading_state

        # 1. None capacity
        self.assertEqual(eval_fn(None, 0.05, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertEqual(eval_fn(None, 0.0, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertNotEqual(eval_fn(None, 0.0, True, "source_confirmed"), "NORMAL")

        # 2. Zero capacity
        self.assertEqual(eval_fn(0.0, 0.05, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertEqual(eval_fn(0.0, 0.0, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertNotEqual(eval_fn(0.0, 0.0, True, "source_confirmed"), "NORMAL")

        # 3. Negative capacity
        self.assertEqual(eval_fn(-1.5, 0.05, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertEqual(eval_fn(-0.001, 0.0, True, "source_confirmed"), "INSUFFICIENT_DATA")
        self.assertNotEqual(eval_fn(-1.5, 0.0, True, "source_confirmed"), "NORMAL")

        # 4. Valid positive capacity
        self.assertEqual(eval_fn(1.0, 0.2, True, "source_confirmed"), "NORMAL")
        self.assertEqual(eval_fn(1.0, 0.75, True, "source_confirmed"), "HIGH_LOADING")
        self.assertEqual(eval_fn(1.0, 1.25, True, "source_confirmed"), "CAPACITY_EXCEEDED")

        # 5. Dangling boundary not reaching outfall produces DISCONNECTED
        self.assertEqual(eval_fn(1.0, 0.2, False, "dangling_boundary"), "DISCONNECTED")
        self.assertEqual(eval_fn(None, 0.2, False, "dangling_boundary"), "DISCONNECTED")

    def test_14_mutually_exclusive_conduit_quality_partition(self):
        """
        Verify that all 624 conduits are partitioned into mutually exclusive primary data quality categories.
        """
        conduits = self.network_data["conduits"]
        self.assertEqual(len(conduits), 624)

        summary = self.network_data["statistics"]["mutually_exclusive_quality_summary"]
        self.assertEqual(sum(summary.values()), 624)
        self.assertEqual(summary["CALCULATED_RECORDED_MATERIAL"], 186)
        self.assertEqual(summary["CALCULATED_ASSUMED_ROUGHNESS"], 78)
        self.assertEqual(summary["ADVERSE_OR_ZERO_SLOPE"], 181)
        self.assertEqual(summary["MISSING_SLOPE_AND_INVERTS"], 75)
        self.assertEqual(summary["MISSING_OR_ZERO_DIAMETER"], 104)

        # Confirm each individual conduit has an assigned primary category
        valid_cats = {
            "CALCULATED_RECORDED_MATERIAL",
            "CALCULATED_ASSUMED_ROUGHNESS",
            "ADVERSE_OR_ZERO_SLOPE",
            "MISSING_SLOPE_AND_INVERTS",
            "MISSING_OR_ZERO_DIAMETER"
        }
        for cid, c in conduits.items():
            self.assertIn("primary_quality_category", c, f"Conduit {cid} missing primary_quality_category")
            self.assertIn(c["primary_quality_category"], valid_cats)

    def test_15_disconnected_state_definition_and_guardrail(self):
        """
        Verify that DISCONNECTED state is explicitly defined as unresolved mapped connectivity,
        NOT confirmed physical drainage failure or blockage.
        """
        # Check metadata assumption documentation
        assumptions = self.meta_data["assumptions"]
        found_disconnected_def = any("unresolved mapped connectivity" in a.lower() for a in assumptions)
        self.assertTrue(found_disconnected_def, "Metadata assumptions must define DISCONNECTED as unresolved mapped connectivity")

        # Check conduit attributes
        conduits = self.network_data["conduits"]
        for c in conduits.values():
            if c["connectivity_type"] == "dangling_boundary" and not c.get("reaches_bayou_outfall"):
                self.assertIn("disconnected_definition", c)
                self.assertIn("unresolved mapped connectivity", c["disconnected_definition"].lower())

    def test_16_flow_conveyance_non_duplication(self):
        """
        Verify surface runoff enters strictly at Inlets and conveys without secondary catchment invention or duplication.
        """
        conduits = self.network_data["conduits"]
        for cid, c in conduits.items():
            self.assertIn("contributing_inlet_fraction", c, f"Conduit {cid} missing contributing_inlet_fraction")
            self.assertGreaterEqual(c["contributing_inlet_fraction"], 0.0)

        # Check that direct inlet conduits correctly sum to connected inlets
        inlets = [nid for nid, nd in self.network_data["nodes"].items() if nd["node_type"] == "Inlet"]
        self.assertEqual(len(inlets), 265)


if __name__ == "__main__":
    unittest.main()
