"""
AquaPredict Milestone 5 - Automated Test Suite
Verifies:
- RAIN-01, RAIN-03: Scenario presets, input validation, sum to target
- RAIN-07: 180-min horizon, 36 intervals of 5 min, peak at min 60
- SIM-01, LAY-07: 5 discrete depth classes, boundary classification
- SIM-03: Peak statistics (max depth, flooded area >= 0.05m threshold)
- SIM-04: Mass balance conservation (< 1.0% tolerance)
- BAR-01, BAR-02: 6-field status bar indicators & honest M6 unavailable states
"""

import os
import json
import math
import unittest
import numpy as np
import sys

# Add scripts directory to path to import run_simulation functions
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

import run_simulation


class TestM5Simulation(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.scenarios_path = os.path.join(WORKSPACE_DIR, "public", "data", "simulation_scenarios.json")
        cls.meta_path = os.path.join(WORKSPACE_DIR, "public", "data", "m5_simulation_meta.json")
        
        with open(cls.scenarios_path, "r", encoding="utf-8") as f:
            cls.scenarios_data = json.load(f)
            
        with open(cls.meta_path, "r", encoding="utf-8") as f:
            cls.meta_data = json.load(f)

    # ----------------------------------------------------
    # 1. Preset & Hyetograph Verification
    # ----------------------------------------------------
    def test_all_five_presets_exist(self):
        """Verify all 5 required rainfall presets exist."""
        presets = self.scenarios_data.get("presets", {})
        expected = ["preset_10mm", "preset_25mm", "preset_50mm", "preset_75mm", "preset_100mm"]
        for p in expected:
            self.assertIn(p, presets, f"Missing preset {p}")

    def test_preset_sums_to_target(self):
        """Verify each preset's intervals sum exactly to target within numerical tolerance."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            target = sc["target_rainfall_mm"]
            hyeto = sc["hyetograph"]
            total_rain = sum(intv["rain_mm"] for intv in hyeto)
            self.assertAlmostEqual(
                total_rain, target, delta=1e-4,
                msg=f"Preset {pid} sum {total_rain} does not match target {target}"
            )

    def test_storm_peak_at_minute_60(self):
        """Verify peak rainfall intensity occurs at minute 60 (interval 11: 55-60 min)."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            hyeto = sc["hyetograph"]
            # Find interval with maximum rain
            max_intv = max(hyeto, key=lambda x: x["rain_mm"])
            # Interval 11 covers 55 to 60 min
            self.assertEqual(
                max_intv["interval_idx"], 11,
                f"Peak in {pid} is at interval {max_intv['interval_idx']} instead of 11 (55-60 min)"
            )
            self.assertEqual(max_intv["time_end_min"], 60)

    def test_hyetograph_duration_and_steps(self):
        """Verify duration is 180 min with 36 5-minute intervals and 37 timesteps."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            self.assertEqual(sc["duration_minutes"], 180)
            self.assertEqual(sc["interval_minutes"], 5)
            self.assertEqual(len(sc["hyetograph"]), 36)
            self.assertEqual(len(sc["timesteps"]), 37)
            
            # Check monotonic time progression
            for s, ts in enumerate(sc["timesteps"]):
                self.assertEqual(ts["time_minutes"], s * 5)

    def test_input_validation_rejects_invalid_values(self):
        """Verify simulation rejects negative, NaN, or non-finite inputs."""
        with self.assertRaises(ValueError):
            run_simulation.generate_hyetograph(-10.0)
            
        with self.assertRaises(ValueError):
            run_simulation.generate_hyetograph(float("nan"))
            
        with self.assertRaises(ValueError):
            run_simulation.generate_hyetograph(float("inf"))

    # ----------------------------------------------------
    # 2. Physical & Numerical Mass Balance Tests
    # ----------------------------------------------------
    def test_zero_rainfall_produces_zero_depth(self):
        """Verify zero rainfall produces zero water depth across all cells."""
        dep_arr, elev_arr = run_simulation.load_depression_and_elev()
        sc_zero = run_simulation.simulate_preset(0.0, dep_arr, elev_arr)
        for ts in sc_zero["timesteps"]:
            self.assertEqual(ts["max_depth_m"], 0.0)
            self.assertEqual(ts["flooded_area_km2"], 0.0)
            self.assertEqual(len(ts["sparse_depths"]), 0)

    def test_all_depth_values_are_finite_and_non_negative(self):
        """Verify no depth value is negative or NaN."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            for ts in sc["timesteps"]:
                self.assertGreaterEqual(ts["max_depth_m"], 0.0)
                self.assertTrue(math.isfinite(ts["max_depth_m"]))
                for item in ts["sparse_depths"]:
                    depth = item[1]
                    self.assertGreater(depth, 0.0)
                    self.assertTrue(math.isfinite(depth))

    def test_mass_balance_strictly_conserved(self):
        """Verify mass-balance residual is within the 1.0% tolerance across all timesteps."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            mb_verif = sc["mass_balance_verification"]
            self.assertEqual(mb_verif["status"], "CONSERVED")
            self.assertTrue(mb_verif["passed"])
            self.assertLess(mb_verif["max_relative_residual_pct"], 1.0)
            
            for ts in sc["timesteps"]:
                mb = ts["mass_balance"]
                p = mb["precip_m3"]
                f = mb["infil_m3"]
                s = mb["storage_m3"]
                o = mb["outfall_m3"]
                res = mb["residual_m3"]
                self.assertAlmostEqual(p, f + s + o, delta=1e-3, msg=f"Mass balance mismatch at {pid} t={ts['time_minutes']}")
                self.assertLess(mb["relative_residual_pct"], 1.0)

    # ----------------------------------------------------
    # 3. Depth Classification & Flooded Area (SIM-01, LAY-07)
    # ----------------------------------------------------
    def test_depth_classification_boundaries(self):
        """Verify depth boundaries map uniquely to the 5 discrete classes."""
        self.assertEqual(run_simulation.classify_depth(0.0), 0)  # Dry
        self.assertEqual(run_simulation.classify_depth(0.02), 1)  # Shallow
        self.assertEqual(run_simulation.classify_depth(0.05), 1)  # Shallow boundary
        self.assertEqual(run_simulation.classify_depth(0.0501), 2)  # Moderate
        self.assertEqual(run_simulation.classify_depth(0.15), 2)  # Moderate
        self.assertEqual(run_simulation.classify_depth(0.20), 2)  # Moderate boundary
        self.assertEqual(run_simulation.classify_depth(0.2001), 3)  # Deep
        self.assertEqual(run_simulation.classify_depth(0.40), 3)  # Deep
        self.assertEqual(run_simulation.classify_depth(0.50), 3)  # Deep boundary
        self.assertEqual(run_simulation.classify_depth(0.5001), 4)  # Very Deep
        self.assertEqual(run_simulation.classify_depth(2.5), 4)  # Very Deep

    def test_flooded_area_threshold_consistency(self):
        """Verify flooded area matches count of cells with depth >= 0.05m multiplied by cell area."""
        presets = self.scenarios_data["presets"]
        cell_area_km2 = (run_simulation.TOTAL_AREA_M2 / run_simulation.TOTAL_CELLS) / 1_000_000.0
        
        for pid, sc in presets.items():
            for ts in sc["timesteps"]:
                classes = ts["class_counts"]
                # Classes 2, 3, 4 are >= 0.05m
                flooded_count = classes["moderate_c2"] + classes["deep_c3"] + classes["very_deep_c4"]
                expected_area = round(flooded_count * cell_area_km2, 4)
                self.assertEqual(
                    ts["flooded_cells_count"], flooded_count,
                    f"Flooded cells count mismatch at {pid} t={ts['time_minutes']}"
                )
                self.assertAlmostEqual(
                    ts["flooded_area_km2"], expected_area, delta=1e-4,
                    msg=f"Flooded area mismatch at {pid} t={ts['time_minutes']}"
                )

    # ----------------------------------------------------
    # 4. Honest M6 Unavailable Reporting (BAR-01, BAR-02)
    # ----------------------------------------------------
    def test_drainage_fields_marked_unavailable(self):
        """Verify drainage counts are reported as Unavailable (M6 Dependent), not false zeros."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            for ts in sc["timesteps"]:
                self.assertEqual(ts["drainage_surcharged_nodes"], "Unavailable (M6 Dependent)")
                self.assertEqual(ts["drainage_overloaded_conduits"], "Unavailable (M6 Dependent)")

    def test_active_warnings_distinguish_dry_from_unavailable_clustering(self):
        """Verify warnings report 'No inundation detected' at t=0 and honest M6 clustering status."""
        presets = self.scenarios_data["presets"]
        for pid, sc in presets.items():
            ts_0 = sc["timesteps"][0]  # t=0 min
            self.assertEqual(ts_0["active_warning"]["status"], "clear")
            self.assertIn("No inundation", ts_0["active_warning"]["message"])
            self.assertEqual(ts_0["active_warning"]["clustering_status"], "Unavailable (M6 Dependent)")

    # ----------------------------------------------------
    # 5. Metadata Schema & Workflow Steps
    # ----------------------------------------------------
    def test_metadata_workflow_steps(self):
        """Verify seven-step hydrological workflow is documented with accurate M5/M6 states."""
        steps = self.meta_data.get("workflow_steps", [])
        self.assertEqual(len(steps), 7)
        
        expected_steps = [
            (1, "Rainfall", "COMPLETED"),
            (2, "Terrain", "COMPLETED"),
            (3, "Runoff", "COMPLETED"),
            (4, "Routing", "COMPLETED"),
            (5, "Drainage", "UNAVAILABLE"),
            (6, "Statistics", "COMPLETED"),
            (7, "Hotspots", "UNAVAILABLE")
        ]
        for idx, name, status in expected_steps:
            st = steps[idx - 1]
            self.assertEqual(st["step"], idx)
            self.assertEqual(st["name"], name)
            self.assertEqual(st["status"], status)


if __name__ == "__main__":
    unittest.main()
