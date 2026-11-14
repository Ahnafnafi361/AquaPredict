"""
Acceptance Test for Static Export Mode (Milestone M10)
Spins up a plain, standard library http.server on port 8085 serving dist_static/
and verifies that all required assets, manifests, and precomputed datasets load cleanly
without calling or requiring any Python backend API.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import threading
import http.server
import socketserver
import unittest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_STATIC_DIR = os.path.join(WORKSPACE_DIR, "dist_static")
TEST_PORT = 8085

class PlainStaticServerThread(threading.Thread):
    def __init__(self, directory, port):
        super().__init__(daemon=True)
        self.directory = directory
        self.port = port
        self.httpd = None

    def run(self):
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=self.directory, **kwargs)
        with socketserver.TCPServer(("", self.port), handler) as httpd:
            self.httpd = httpd
            httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()

class TestStaticExportMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(DIST_STATIC_DIR):
            from scripts.export_static import export_static
            export_static()

        cls.server_thread = PlainStaticServerThread(DIST_STATIC_DIR, TEST_PORT)
        cls.server_thread.start()
        time.sleep(1.0) # wait for server to bind

    @classmethod
    def tearDownClass(cls):
        cls.server_thread.stop()

    def _get(self, path):
        url = f"http://localhost:{TEST_PORT}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "AquaPredict-Static-Test"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()

    def test_01_index_html_loads_and_has_static_flag(self):
        status, content = self._get("/")
        self.assertEqual(status, 200)
        text = content.decode("utf-8")
        self.assertIn("AQUAPREDICT_STATIC_MODE = true", text)
        self.assertIn("AquaPredict", text)
        self.assertIn("staticModeBanner", text)

    def test_02_css_and_js_assets_load(self):
        for path in ["/css/style.css", "/js/app.js", "/js/viewer3d.js", "/js/vendor/three.min.js"]:
            status, content = self._get(path)
            self.assertEqual(status, 200, f"Failed to load {path}")
            self.assertGreater(len(content), 1000, f"Asset {path} unexpectedly small")

    def test_03_i18n_dictionaries_load(self):
        # Bangla
        status, content = self._get("/i18n/bn.json")
        self.assertEqual(status, 200)
        bn_data = json.loads(content.decode("utf-8"))
        self.assertEqual(bn_data["locale"], "bn")
        self.assertIn("SYNTHETIC SURROGATE", bn_data["warnings_and_disclaimers"]["synthetic_surrogate"])
        self.assertIn("UNVALIDATED", bn_data["warnings_and_disclaimers"]["unvalidated"])

        # English
        status, content = self._get("/i18n/en.json")
        self.assertEqual(status, 200)
        en_data = json.loads(content.decode("utf-8"))
        self.assertEqual(en_data["locale"], "en")

    def test_04_static_export_manifest_integrity(self):
        status, content = self._get("/data/static_export_manifest.json")
        self.assertEqual(status, 200)
        manifest = json.loads(content.decode("utf-8"))
        self.assertEqual(manifest["export_mode"], "static_precomputed")
        self.assertEqual(manifest["pilot_area"]["bounding_box_wgs84"], [-95.3750, 29.7560, -95.3650, 29.7650])
        self.assertIn("preset_50mm", manifest["scenarios"])
        self.assertIn("preset_100mm", manifest["scenarios"])
        self.assertTrue(len(manifest["scientific_disclaimers"]) >= 3)

    def test_05_precomputed_simulation_scenarios_load(self):
        status, content = self._get("/data/simulation_scenarios.json")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertIn("presets", data)
        self.assertIn("preset_50mm", data["presets"])
        self.assertEqual(len(data["presets"]["preset_50mm"]["timesteps"]), 37)

    def test_06_precomputed_heightmap_loads(self):
        status, content = self._get("/data/terrain_heightmap_256.json")
        self.assertEqual(status, 200)
        hm = json.loads(content.decode("utf-8"))
        self.assertEqual(hm["dimensions"]["rows"], 256)
        self.assertEqual(hm["dimensions"]["cols"], 256)
        self.assertEqual(len(hm["elevations"]), 256)
        self.assertEqual(len(hm["elevations"][0]), 256)

    def test_07_routing_graph_loads(self):
        status, content = self._get("/data/m7_routing_graph.json")
        self.assertEqual(status, 200)
        graph = json.loads(content.decode("utf-8"))
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)

    def test_08_backend_api_is_not_served_or_needed(self):
        """Verifies that plain static server does NOT have /api/ endpoints (404 expected)."""
        for api_path in ["/api/health", "/api/simulations", "/api/terrain/heightmap"]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._get(api_path)
            self.assertEqual(ctx.exception.code, 404, f"API {api_path} unexpectedly responded on plain server")

if __name__ == "__main__":
    unittest.main()
