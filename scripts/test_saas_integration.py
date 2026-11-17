"""
Comprehensive Integration Test for AquaPredict SaaS Marketing Website & Existing GIS Application
Tests route resolution, HTML structure, navigation links, and feature preservation.
"""

import unittest
import urllib.request
import re

BASE_URL = "http://localhost:8000"

class TestSaaSIntegration(unittest.TestCase):
    def _get(self, path):
        req = urllib.request.Request(f"{BASE_URL}{path}", headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_01_landing_page_structure_and_links(self):
        status, html = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("AquaPredict", html)
        self.assertIn("Next-Gen Urban Flood Intelligence", html)
        self.assertIn("heroCanvas", html)
        self.assertIn("app.html", html)
        self.assertIn("pricing.html", html)
        self.assertIn("auth.html", html)
        self.assertIn("staticModeBanner", html)

        # Core Features
        self.assertIn("Terrain & Depression Screening", html)
        self.assertIn("Dynamic Flood Detection", html)
        self.assertIn("Rescue Priority Predictor", html)
        self.assertIn("Safest Route Planner", html)
        self.assertIn("Drainage Hydraulic Diagnostics", html)
        self.assertIn("3D Terrain & Flood Elevation", html)

        # FAQ & Use Cases
        self.assertIn("Emergency Medical Dispatch", html)
        self.assertIn("Municipal Flood Resilience", html)
        self.assertIn("Frequently Asked Questions", html)

    def test_02_gis_app_preservation(self):
        for path in ["/app", "/app.html"]:
            status, html = self._get(path)
            self.assertEqual(status, 200)
            self.assertIn("AquaPredict", html)
            self.assertIn('id="map"', html)
            self.assertIn("Flood Detection", html)
            self.assertIn("Rescue Priority Predictor", html)
            self.assertIn("Safest Route Planner", html)
            self.assertIn("Drainage & Capacity", html)
            self.assertIn("tabView2D", html)
            self.assertIn("tabView3D", html)
            self.assertIn("back-home-btn", html) # Verification of link to SaaS marketing site

    def test_03_pricing_page_structure(self):
        for path in ["/pricing", "/pricing.html"]:
            status, html = self._get(path)
            self.assertEqual(status, 200)
            self.assertIn("Explorer", html)
            self.assertIn("Pro Analyst", html)
            self.assertIn("Team Professional", html)
            self.assertIn("billingSwitch", html)
            self.assertIn("matrix-table", html)
            self.assertIn("Pilot Demonstration Notice", html)
            self.assertIn("app.html", html)

    def test_04_auth_page_structure(self):
        for path in ["/auth", "/auth.html"]:
            status, html = self._get(path)
            self.assertEqual(status, 200)
            self.assertIn("Sign In to AquaPredict", html)
            self.assertIn('id="signInForm"', html)
            self.assertIn('id="signUpForm"', html)
            self.assertIn('id="forgotForm"', html)
            self.assertIn("analyst@aquapredict.io", html)
            self.assertIn("AquaPredict2026!", html)
            self.assertIn("app.html", html)

    def test_05_assets_load_correctly(self):
        for asset in ["/css/saas.css", "/js/saas.js", "/assets/logo.png"]:
            req = urllib.request.Request(f"{BASE_URL}{asset}", headers={"Connection": "close"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertGreater(len(resp.read()), 100)

if __name__ == "__main__":
    unittest.main()
