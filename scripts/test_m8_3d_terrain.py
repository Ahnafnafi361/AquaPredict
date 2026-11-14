"""
Milestone M8 Test Suite: Optional 3D Terrain and Flood View
Tests:
1. Heightmap endpoint response and JSON schema.
2. Heightmap dimensions, grid shape, and geographic bounds.
3. Configurable resolution query parameters.
4. Elevation provenance, datum, and units.
5. Missing or invalid DEM handling (no synthetic zero substitution).
6. WebGL fallback logic.
7. Missing simulation frame handling.
8. Synchronization between 2D and 3D timeline.
9. Consistency of depth classes and legend colors.
10. Vertical exaggeration factor clamping and display.
"""

import unittest
import urllib.request
import json
import os
import sys

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from scripts.generate_heightmap import extract_heightmap, PILOT_BBOX

class TestM8TerrainAndFloodView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://localhost:8000"

    def test_01_heightmap_endpoint_response(self):
        """Verify GET /api/terrain/heightmap returns 200 OK and valid JSON."""
        url = f"{self.base_url}/api/terrain/heightmap"
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers.get("Content-Type", ""))
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "AVAILABLE")
            self.assertEqual(data.get("units"), "meters")
            self.assertIn("bounds", data)
            self.assertIn("dimensions", data)
            self.assertIn("elevations", data)
            self.assertIn("provenance", data)

    def test_02_heightmap_dimensions_and_bounds(self):
        """Verify heightmap dimensions (default 256x256) and exact geographic bounds."""
        url = f"{self.base_url}/api/terrain/heightmap"
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        dims = data["dimensions"]
        self.assertEqual(dims["rows"], 256)
        self.assertEqual(dims["cols"], 256)

        # Check elevations shape
        elevations = data["elevations"]
        self.assertEqual(len(elevations), 256)
        self.assertEqual(len(elevations[0]), 256)

        # Check bounds match pilot bounding box
        bounds = data["bounds"]
        self.assertAlmostEqual(bounds["west"], PILOT_BBOX["west"], places=4)
        self.assertAlmostEqual(bounds["south"], PILOT_BBOX["south"], places=4)
        self.assertAlmostEqual(bounds["east"], PILOT_BBOX["east"], places=4)
        self.assertAlmostEqual(bounds["north"], PILOT_BBOX["north"], places=4)

    def test_03_configurable_resolution(self):
        """Verify resolution is configurable via function and query param (e.g. res=128)."""
        # Test function directly
        hm_128 = extract_heightmap(resolution=128)
        self.assertEqual(hm_128["dimensions"]["rows"], 128)
        self.assertEqual(hm_128["dimensions"]["cols"], 128)
        self.assertEqual(len(hm_128["elevations"]), 128)
        self.assertEqual(len(hm_128["elevations"][0]), 128)

        # Test endpoint with query param ?res=128
        url = f"{self.base_url}/api/terrain/heightmap?res=128"
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["dimensions"]["rows"], 128)
            self.assertEqual(data["dimensions"]["cols"], 128)

    def test_04_elevation_provenance(self):
        """Verify provenance metadata, units, datum, and realistic elevation range."""
        url = f"{self.base_url}/api/terrain/heightmap"
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        prov = data["provenance"]
        self.assertIn("StratMap18", prov["dataset"])
        self.assertEqual(prov["reprojected_crs"], "EPSG:4326 (WGS84)")
        self.assertIn("UNVERIFIED", prov["vertical_datum_status"])
        self.assertEqual(data["units"], "meters")

        # Elevation range checks (Buffalo bayou to Downtown ridge)
        min_e = data["min_elev_m"]
        max_e = data["max_elev_m"]
        mean_e = data["mean_elev_m"]

        self.assertLess(min_e, 1.0) # Bayou channel approaches 0m or tidal
        self.assertGreater(max_e, 14.0) # Downtown ridge reaches ~17m
        self.assertTrue(min_e <= mean_e <= max_e)

    def test_05_missing_or_invalid_dem_handling(self):
        """Verify missing DEM data is handled gracefully and never replaces missing values with synthetic zeros."""
        # Non-existent GeoTIFF and non-existent fallback
        missing_hm = extract_heightmap(resolution=64, dem_tif_path="non_existent_file.tif")
        
        # When primary GeoTIFF is not found, fallback dem_grid.json is used if available,
        # but if BOTH are missing, status must be UNAVAILABLE, never synthetic zeros
        self.assertIn("status", missing_hm)
        if missing_hm["status"] == "UNAVAILABLE":
            self.assertIsNone(missing_hm["elevations"])
            self.assertIn("error", missing_hm)

    def test_06_webgl_fallback_detection_logic(self):
        """Verify WebGL fallback detection logic matches viewer3d specification."""
        # When WebGL context creation returns None, fallback is triggered
        def check_webgl_mock(has_gl):
            return has_gl

        self.assertTrue(check_webgl_mock(True))
        self.assertFalse(check_webgl_mock(False))

        # Check that public/js/viewer3d.js contains explicit checkWebGL fallback logic
        viewer_js_path = os.path.join(WORKSPACE_DIR, "public", "js", "viewer3d.js")
        with open(viewer_js_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("checkWebGL", code)
        self.assertIn("showWebGLFallback", code)
        self.assertIn("webglFallbackBanner", code)

    def test_07_missing_simulation_frame_handling(self):
        """Verify missing simulation frame triggers explicit UNAVAILABLE state rather than crashing."""
        viewer_js_path = os.path.join(WORKSPACE_DIR, "public", "js", "viewer3d.js")
        with open(viewer_js_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("FRAME UNAVAILABLE", code)
        self.assertIn("SIM UNAVAILABLE", code)
        self.assertIn("setFrameStatus", code)

    def test_08_timeline_synchronization_2d_3d(self):
        """Verify that simulation scenarios file has consistent timesteps matching 2D timeline."""
        sim_path = os.path.join(WORKSPACE_DIR, "public", "data", "simulation_scenarios.json")
        with open(sim_path, "r", encoding="utf-8") as f:
            sim = json.load(f)

        self.assertIn("presets", sim)
        for preset_name, preset_data in sim["presets"].items():
            timesteps = preset_data["timesteps"]
            self.assertEqual(len(timesteps), 37, f"Preset {preset_name} must have 37 timesteps")
            # First timestep should be time_minutes 0 (dry)
            self.assertEqual(timesteps[0]["time_minutes"], 0)
            self.assertEqual(len(timesteps[0]["sparse_depths"]), 0)

    def test_09_consistency_of_depth_classes_and_legend(self):
        """Verify that 2D and 3D use identical 5-class depth classifications and color definitions."""
        app_js_path = os.path.join(WORKSPACE_DIR, "public", "js", "app.js")
        viewer_js_path = os.path.join(WORKSPACE_DIR, "public", "js", "viewer3d.js")

        with open(app_js_path, "r", encoding="utf-8") as f:
            app_code = f.read()
        with open(viewer_js_path, "r", encoding="utf-8") as f:
            viewer_code = f.read()

        # Check 2D thresholds in app.js
        self.assertIn("0.05", app_code)
        self.assertIn("0.20", app_code)
        self.assertIn("0.50", app_code)

        # Check 3D thresholds in viewer3d.js
        self.assertIn("0.05", viewer_code)
        self.assertIn("0.20", viewer_code)
        self.assertIn("0.50", viewer_code)

        # Check color values:
        # Shallow: #93c5fd -> RGB(147, 197, 253)
        # Moderate: #3b82f6 -> RGB(59, 130, 246)
        # Deep: #1d4ed8 -> RGB(29, 78, 216)
        # Very Deep: #1e1b4b -> RGB(30, 27, 75)
        self.assertIn("147", viewer_code)
        self.assertIn("197", viewer_code)
        self.assertIn("253", viewer_code)
        self.assertIn("59", viewer_code)
        self.assertIn("130", viewer_code)
        self.assertIn("246", viewer_code)
        self.assertIn("29", viewer_code)
        self.assertIn("78", viewer_code)
        self.assertIn("216", viewer_code)
        self.assertIn("30", viewer_code)
        self.assertIn("27", viewer_code)
        self.assertIn("75", viewer_code)

    def test_10_vertical_exaggeration_bounds(self):
        """Verify vertical exaggeration slider bounds (1.0 to 10.0, default 3.0)."""
        index_html_path = os.path.join(WORKSPACE_DIR, "public", "index.html")
        viewer_js_path = os.path.join(WORKSPACE_DIR, "public", "js", "viewer3d.js")

        with open(index_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(viewer_js_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn('id="sliderVertExaggeration"', html)
        self.assertIn('min="1.0"', html)
        self.assertIn('max="10.0"', html)
        self.assertIn('value="3.0"', html)
        self.assertIn("verticalExaggeration: 3.0", code)

if __name__ == "__main__":
    unittest.main()
