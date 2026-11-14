"""
AquaPredict - Unit and Verification Tests for M3 Validation Readiness
Tests data integrity, candidate source evaluation, scientific guardrails,
and absence of fabricated validation metrics.
"""

import os
import json
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_ROOT, "public", "data")
M3_JSON_PATH = os.path.join(DATA_DIR, "m3_validation_readiness.json")
M1_META_PATH = os.path.join(DATA_DIR, "m1_analysis_meta.json")

class TestM3ValidationReadiness(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(M3_JSON_PATH), f"Missing {M3_JSON_PATH}")
        with open(M3_JSON_PATH, "r", encoding="utf-8") as f:
            self.m3 = json.load(f)

    def test_explicit_validation_decision(self):
        """M3 must reach an explicit, uncompromised VALIDATION DATA UNAVAILABLE decision."""
        self.assertEqual(self.m3.get("validation_status"), "UNAVAILABLE")
        self.assertEqual(self.m3.get("decision"), "VALIDATION DATA UNAVAILABLE")

    def test_pilot_boundary_preservation(self):
        """Downtown Houston pilot boundary must remain unchanged."""
        bbox = self.m3.get("pilot_area", {}).get("bounding_box", {})
        self.assertEqual(bbox.get("west"), -95.375)
        self.assertEqual(bbox.get("south"), 29.756)
        self.assertEqual(bbox.get("east"), -95.365)
        self.assertEqual(bbox.get("north"), 29.765)
        self.assertEqual(self.m3.get("pilot_area", {}).get("area_km2"), 0.97)

    def test_m1_weight_and_score_integrity(self):
        """M1 susceptibility weights must not be modified during baseline validation."""
        m1_integrity = self.m3.get("m1_model_integrity", {})
        self.assertTrue(m1_integrity.get("verified"))
        self.assertTrue(m1_integrity.get("unaltered"))
        
        weights = m1_integrity.get("weights", {})
        self.assertEqual(weights.get("terrain_depressions"), 0.35)
        self.assertEqual(weights.get("relative_elevation_tpi"), 0.25)
        self.assertEqual(weights.get("slope_flatness"), 0.20)
        self.assertEqual(weights.get("drainage_proximity"), 0.20)
        
        # Cross-check directly against m1_analysis_meta.json
        with open(M1_META_PATH, "r", encoding="utf-8") as f:
            m1_meta = json.load(f)
        ind = m1_meta.get("indicators", {})
        self.assertEqual(ind["terrain_depressions"]["weight"], 0.35)
        self.assertEqual(ind["relative_elevation"]["weight"], 0.25)
        self.assertEqual(ind["slope_flatness"]["weight"], 0.20)
        self.assertEqual(ind["drainage_proximity"]["weight"], 0.20)

    def test_no_synthetic_validation_fabrication(self):
        """Synthetic flood events or synthetic performance scores must NOT be fabricated."""
        baseline = self.m3.get("baseline_comparison", {})
        self.assertFalse(baseline.get("executed"))
        self.assertIn("strictly prohibited", baseline.get("reason", "").lower())
        
        # Verify no fabricated metric keys exist
        for key in ["roc_auc", "f1_score", "precision", "recall", "accuracy"]:
            self.assertNotIn(key, baseline)
            
        inv = self.m3.get("local_data_inventory", {})
        self.assertFalse(inv.get("synthetic_ground_truth_present"))

    def test_candidate_sources_inventory(self):
        """All 5 candidate sources must be evaluated with complete provenance and rationale."""
        sources = self.m3.get("candidate_sources", [])
        self.assertEqual(len(sources), 5)
        
        source_ids = [s["id"] for s in sources]
        expected_ids = ["usgs_stn_hwm", "houston_311", "houston_transtar", "hcfws_gauges", "fema_nfhl"]
        self.assertEqual(sorted(source_ids), sorted(expected_ids))
        
        for s in sources:
            self.assertTrue(len(s.get("provenance", "")) > 5)
            self.assertTrue(len(s.get("access_method", "")) > 5)
            self.assertTrue(len(s.get("geographic_coverage", "")) > 5)
            self.assertTrue(len(s.get("event_definition", "")) > 5)
            self.assertTrue(len(s.get("limitations", [])) >= 2)
            self.assertFalse(s.get("suitability_for_m1_validation"), f"Source {s['id']} should not be suitable")

    def test_scientific_distinctions(self):
        """Must distinguish fluvial vs pluvial, modeled vs observed, complaints vs physical data."""
        dist = self.m3.get("scientific_distinctions", {})
        self.assertIn("pluvial_vs_fluvial", dist)
        self.assertIn("modeled_vs_observed", dist)
        self.assertIn("complaints_vs_physical_evidence", dist)
        
    def test_next_steps_and_missing_evidence(self):
        """Required evidence and next steps must be explicitly enumerated."""
        ev = self.m3.get("required_evidence_for_future_validation", [])
        self.assertGreaterEqual(len(ev), 4)
        ns = self.m3.get("next_steps", [])
        self.assertGreaterEqual(len(ns), 4)

if __name__ == "__main__":
    unittest.main()
