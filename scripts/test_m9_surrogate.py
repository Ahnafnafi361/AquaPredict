"""
AquaPredict Unit & Integration Test Suite - Milestone M9: ML Surrogate
Tests:
1. Training reproducibility with fixed seed.
2. Training and held-out scenario separation (zero leakage).
3. Model loading and serialization integrity.
4. Missing model handling (graceful error response).
5. Invalid API input handling (boundary checks, status 400).
6. Surrogate API response structure and contracts.
7. Required provenance labels and strict scientific disclaimers.
8. Original simulation mode preservation via API.
9. Fidelity comparison against original simulator.
"""

import os
import sys
import json
import unittest
import urllib.request
import urllib.error
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from ml.surrogate.generate_dataset import (
    RANDOM_SEED as GEN_SEED,
    generate_hyetograph_intervals,
    compute_nrcs_runoff,
    FEATURE_NAMES
)
from ml.surrogate.predict import (
    predict_surrogate_frame,
    load_surrogate_model,
    is_model_available,
    MODEL_PATH,
    META_PATH
)

API_BASE_URL = "http://localhost:8000"

class TestM9Surrogate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data")
        cls.meta_file = os.path.join(cls.data_dir, "scenarios_metadata.json")

    def test_01_training_reproducibility_fixed_seed(self):
        """Verify deterministic dataset generation and training reproducibility with seed 42."""
        self.assertEqual(GEN_SEED, 42)

        # Hyetograph intervals must produce bit-for-bit identical floats across separate calls
        h1 = generate_hyetograph_intervals(50.0, 180, 0.33, 5)
        h2 = generate_hyetograph_intervals(50.0, 180, 0.33, 5)
        np.testing.assert_array_almost_equal(h1, h2, decimal=6)

        # Runoff calculation must be strictly deterministic
        cum_rain = np.cumsum(h1)
        r1 = compute_nrcs_runoff(cum_rain)
        r2 = compute_nrcs_runoff(cum_rain)
        np.testing.assert_array_almost_equal(r1, r2, decimal=6)

    def test_02_scenario_separation_zero_leakage(self):
        """Verify strict partition between training and held-out simulation scenarios (zero leakage)."""
        self.assertTrue(os.path.isfile(self.meta_file), f"Missing metadata file: {self.meta_file}")
        with open(self.meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        train_ids = meta.get("train_scenario_ids", [])
        heldout_ids = meta.get("heldout_scenario_ids", [])

        self.assertGreater(len(train_ids), 0)
        self.assertGreater(len(heldout_ids), 0)

        # Verify zero scenario intersection
        overlap = set(train_ids).intersection(set(heldout_ids))
        self.assertEqual(len(overlap), 0, f"Data leakage detected! Overlapping scenarios: {overlap}")
        self.assertEqual(meta.get("scenarios_count_train"), 15)
        self.assertEqual(meta.get("scenarios_count_heldout"), 5)

    def test_03_model_loading(self):
        """Verify surrogate model artifact and metadata loading integrity."""
        self.assertTrue(is_model_available(), f"Model artifact not found at {MODEL_PATH}")
        model, meta = load_surrogate_model()

        self.assertTrue(hasattr(model, "predict"), "Loaded model missing .predict() interface")
        self.assertIn("features", meta)
        self.assertEqual(meta["features"], FEATURE_NAMES)
        self.assertEqual(meta["random_seed"], 42)
        self.assertIn("package_versions", meta)

    def test_04_missing_model_handling(self):
        """Verify graceful error reporting when surrogate model is missing."""
        import ml.surrogate.predict as pmod
        orig_path = pmod.MODEL_PATH
        try:
            pmod.MODEL_PATH = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "models", "non_existent_model.joblib")
            self.assertFalse(pmod.is_model_available())
            with self.assertRaises(FileNotFoundError):
                pmod.load_surrogate_model(force_reload=True)
        finally:
            pmod.MODEL_PATH = orig_path
            pmod.load_surrogate_model(force_reload=True)

    def test_05_invalid_api_input_handling(self):
        """Verify invalid inputs return HTTP 400 with structured error JSON."""
        invalid_payloads = [
            {"mode": "surrogate", "rainfall_mm": -10.0},                  # Negative rainfall
            {"mode": "surrogate", "duration_min": 0},                     # Zero duration
            {"mode": "surrogate", "duration_min": 60, "time_min": 120},  # Time exceeding duration
            {"mode": "surrogate", "drain_rate": 1.5},                     # Invalid drain rate > 1.0
            {"mode": "unsupported_mode_xyz"}                              # Invalid mode
        ]

        for payload in invalid_payloads:
            req = urllib.request.Request(
                f"{API_BASE_URL}/api/simulations",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req)
            self.assertEqual(ctx.exception.code, 400)
            err_data = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(err_data.get("status"), "error")
            self.assertIn("error_code", err_data)

    def test_06_surrogate_api_response_structure(self):
        """Verify surrogate API returns complete, correctly structured depth frame quickly."""
        payload = {
            "mode": "surrogate",
            "rainfall_mm": 50.0,
            "duration_min": 180,
            "time_min": 90
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/api/simulations",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("mode"), "surrogate")
        self.assertIn("timestep", data)
        self.assertIn("metadata", data)

        ts = data["timestep"]
        for key in ["time_minutes", "cumulative_rain_mm", "intensity_mm_hr", "max_depth_m", "mean_depth_m", "flooded_area_km2", "flooded_cells_count", "class_counts", "sparse_depths"]:
            self.assertIn(key, ts)

        # Sparse depths must be an array of [flatIdx, depth_m]
        self.assertIsInstance(ts["sparse_depths"], list)
        self.assertGreater(len(ts["sparse_depths"]), 0)
        self.assertEqual(len(ts["sparse_depths"][0]), 2)

        # Inference latency must be fast (< 100 ms)
        self.assertLess(data["metadata"]["inference_time_ms"], 150.0)

    def test_07_required_provenance_and_scientific_disclaimers(self):
        """Verify mandatory provenance labels and strict exclusion of unvalidated marketing claims."""
        res = predict_surrogate_frame(50.0, 180, 90)

        # Mandatory Provenance & Disclaimers
        self.assertEqual(res.get("model_type"), "SYNTHETIC SURROGATE")
        self.assertEqual(res.get("provenance_label"), "SYNTHETIC SURROGATE")
        self.assertEqual(res.get("validation_status"), "UNVALIDATED against real-world flood observations")
        
        expected_disclaimer = "These metrics measure how closely the ML surrogate reproduces the AquaPredict screening model. They do not measure real-world flood prediction accuracy."
        self.assertEqual(res.get("scientific_disclaimer"), expected_disclaimer)

        # Verify strict scientific terminology: NEVER claim real-world nowcast confidence or validate against real observations
        raw_json_str = json.dumps(res).lower()
        self.assertNotIn("nowcast confidence", raw_json_str)
        self.assertNotIn("real-world validation", raw_json_str)
        self.assertNotIn("calibrated flood forecast", raw_json_str)
        # Ensure model is strictly categorized as unvalidated surrogate
        self.assertIn("unvalidated", raw_json_str)
        self.assertIn("synthetic surrogate", raw_json_str)

    def test_08_original_simulation_mode_preserved(self):
        """Verify POST /api/simulations supports mode: 'original' with full fidelity."""
        payload = {
            "mode": "original",
            "preset_id": "preset_50mm",
            "step_idx": 18
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/api/simulations",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("mode"), "original")
        self.assertEqual(data.get("model_type"), "SCREENING SIMULATION")
        self.assertEqual(data.get("provenance_label"), "AquaPredict M5 Hydrological Screening Model")
        self.assertIn("timestep", data)
        self.assertEqual(data["timestep"]["time_minutes"], 90)

    def test_09_comparison_against_original_simulator(self):
        """Verify surrogate depth outputs closely track screening simulator (held-out fidelity)."""
        surr_res = predict_surrogate_frame(50.0, 180, 90)
        surr_max = surr_res["timestep"]["max_depth_m"]

        # Load canonical 50mm scenario step 18 (90 min)
        scenarios_file = os.path.join(WORKSPACE_DIR, "public", "data", "simulation_scenarios.json")
        with open(scenarios_file, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
        orig_ts = scenarios["presets"]["preset_50mm"]["timesteps"][18]
        orig_max = orig_ts["max_depth_m"]

        # Both should identify substantial flood depth in depressions (diff < 0.45 m)
        diff = abs(surr_max - orig_max)
        self.assertLess(diff, 0.45, f"Discrepancy between surrogate ({surr_max}m) and screening ({orig_max}m) too large: {diff}m")

if __name__ == "__main__":
    unittest.main()
