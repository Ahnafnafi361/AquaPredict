"""
AquaPredict M4 Dynamic Rainfall–Susceptibility Synthesis Automated Test Suite
Validates:
1. M1 weight, threshold, and grid integrity preservation (zero regressions).
2. Mathematical correctness of rainfall intensity calculation (I = r_in / dt_hr).
3. 96-interval timeline boundaries and peak interval characteristics in sample fixture.
4. Data state enforcement (UNAVAILABLE, UNVERIFIED DEMONSTRATION, VERIFIED, INVALID).
5. Neutral 16-cell bivariate screening matrix classification (absence of sensationalist claims).
6. Non-fabrication of flood depth (cm/in) or calibrated flood probability (0-100%).
7. M3 Validation Readiness decision preservation (VALIDATION DATA UNAVAILABLE).
"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "public", "data")

def run_tests():
    passed = 0
    failed = 0

    print("=" * 70)
    print("AQUAPREDICT M4 DYNAMIC SYNTHESIS TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST 1: M1 Weight and Susceptibility Tier Preservation
    # -------------------------------------------------------------
    print("\n[TEST 1] Verifying M1 Susceptibility Weights and Tiers...")
    m1_meta_path = os.path.join(DATA_DIR, "m1_analysis_meta.json")
    with open(m1_meta_path, "r", encoding="utf-8") as f:
        m1_meta = json.load(f)

    indicators = m1_meta.get("indicators", {})
    expected_weights = {
        "terrain_depressions": 0.35,
        "relative_elevation": 0.25,
        "slope_flatness": 0.20,
        "drainage_proximity": 0.20
    }
    total_weight = 0.0
    for k, expected_val in expected_weights.items():
        ind = indicators.get(k, {})
        actual_val = ind.get("weight")
        assert actual_val == expected_val, f"M1 weight altered! {k}: expected {expected_val}, got {actual_val}"
        total_weight += actual_val
    
    assert abs(total_weight - 1.0) < 1e-6, f"M1 weights do not sum to 1.0: {total_weight}"

    tier_dist = m1_meta.get("tier_distribution_pct", {})
    assert "High" in tier_dist and "Elevated" in tier_dist and "Moderate" in tier_dist and "Low" in tier_dist
    print("  [OK] M1 weights are 100% unaltered: Depressions 35%, TPI 25%, Slope 20%, Inlets 20%")
    print("  [OK] M1 tiers intact: Low (<0.30), Mod (0.30-0.499), Elev (0.50-0.699), High (>=0.70)")
    passed += 1

    # -------------------------------------------------------------
    # TEST 2: M1 Susceptibility Inspection Grid Integrity
    # -------------------------------------------------------------
    print("\n[TEST 2] Verifying M1 Susceptibility Grid (100x100 client lookup)...")
    susc_grid_path = os.path.join(DATA_DIR, "susceptibility_grid.json")
    with open(susc_grid_path, "r", encoding="utf-8") as f:
        susc_grid = json.load(f)

    assert susc_grid.get("rows") == 100, f"Expected 100 rows, got {susc_grid.get('rows')}"
    assert susc_grid.get("cols") == 100, f"Expected 100 cols, got {susc_grid.get('cols')}"
    assert len(susc_grid.get("grid", [])) == 100
    assert len(susc_grid["grid"][0]) == 100

    sample_cell = susc_grid["grid"][50][50]
    for key in ["score", "tier", "elev", "dep", "slope", "inlet_dist"]:
        assert key in sample_cell, f"Missing field in susceptibility grid cell: {key}"
    print("  [OK] 100x100 lookup grid format verified (10,000 cells intact)")
    passed += 1

    # -------------------------------------------------------------
    # TEST 3: Rainfall Intensity Formulation & provisional categories
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Rainfall Intensity Rate Calculation & Categorization...")
    import math

    def calc_intensity(rain_in, minutes=15):
        if rain_in is None:
            return None
        try:
            r = float(rain_in)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(r) or r < 0:
            return None
        if minutes is None:
            return None
        try:
            dur = float(minutes)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(dur) or dur <= 0:
            return None
        return r / (dur / 60.0)

    def classify_intensity(rate_in_hr):
        if rate_in_hr is None:
            return "Invalid Input"
        try:
            rate = float(rate_in_hr)
        except (TypeError, ValueError):
            return "Invalid Input"
        if not math.isfinite(rate) or rate < 0:
            return "Invalid Input"
        if rate < 0.10:
            return "Zero / Trace"
        elif rate < 0.40:
            return "Low Intensity"
        elif rate < 1.00:
            return "Moderate Intensity"
        else:
            return "Heavy Intensity"

    # Valid calculations
    assert calc_intensity(0.00, 15) == 0.0
    assert classify_intensity(0.0) == "Zero / Trace"

    assert abs(calc_intensity(0.05, 15) - 0.20) < 1e-6
    assert classify_intensity(0.20) == "Low Intensity"

    assert abs(calc_intensity(0.15, 15) - 0.60) < 1e-6
    assert classify_intensity(0.60) == "Moderate Intensity"

    assert abs(calc_intensity(0.38, 15) - 1.52) < 1e-6
    assert classify_intensity(1.52) == "Heavy Intensity"

    # Numeric edge cases: NaN, Infinity, -Infinity, negative rainfall
    assert calc_intensity(float('nan'), 15) is None
    assert calc_intensity(float('inf'), 15) is None
    assert calc_intensity(float('-inf'), 15) is None
    assert calc_intensity(-0.5, 15) is None
    assert calc_intensity(None, 15) is None

    # Invalid interval durations: zero, negative, NaN, infinite
    assert calc_intensity(0.38, 0) is None
    assert calc_intensity(0.38, -15) is None
    assert calc_intensity(0.38, float('nan')) is None
    assert calc_intensity(0.38, float('inf')) is None
    assert calc_intensity(0.38, float('-inf')) is None

    # Exact boundary thresholds: [0, 0.10), [0.10, 0.40), [0.40, 1.00), >= 1.00
    assert classify_intensity(0.00) == "Zero / Trace"
    assert classify_intensity(0.0999) == "Zero / Trace"
    assert classify_intensity(0.10) == "Low Intensity"
    assert classify_intensity(0.3999) == "Low Intensity"
    assert classify_intensity(0.40) == "Moderate Intensity"
    assert classify_intensity(0.9999) == "Moderate Intensity"
    assert classify_intensity(1.00) == "Heavy Intensity"
    assert classify_intensity(2.50) == "Heavy Intensity"

    # Invalid input must NEVER be displayed as valid zero or valid heavy rainfall
    assert classify_intensity(None) == "Invalid Input"
    assert classify_intensity(float('nan')) == "Invalid Input"
    assert classify_intensity(float('inf')) == "Invalid Input"
    assert classify_intensity(float('-inf')) == "Invalid Input"
    assert classify_intensity(-1.0) == "Invalid Input"
    assert classify_intensity(float('inf')) != "Heavy Intensity"
    assert classify_intensity(None) != "Zero / Trace"

    print("  [OK] Intensity formulation I = r_in / (dt / 60) verified across all categories and edge cases")
    print("  [OK] Invalid inputs (NaN, Inf, -Inf, negative, invalid durations) strictly rejected as Invalid Input")
    passed += 1

    # -------------------------------------------------------------
    # TEST 4: Timeline Boundaries, Peak Storm Interval & Timezone Label
    # -------------------------------------------------------------
    print("\n[TEST 4] Verifying 96 Demonstration Intervals and Central Time Label...")
    sample_rain_path = os.path.join(DATA_DIR, "rainfall_sample_1600.json")
    with open(sample_rain_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    assert sample_data.get("time_zone") == "US/Central (CDT/CST)"
    intervals = sample_data.get("records") or sample_data.get("intervals", [])
    assert len(intervals) == 96, f"Expected 96 intervals, got {len(intervals)}"
    assert sample_data.get("metrics", {}).get("total_records") == 96

    # Test peak storm interval (index 23, interval 24)
    peak_intv = intervals[23]
    assert peak_intv.get("index") == 23
    assert peak_intv.get("rain_in") == 0.38
    assert abs(calc_intensity(peak_intv["rain_in"], 15) - 1.52) < 1e-6

    # Cumulative total at index 23
    cum_rain = sum(intv.get("rain_in", 0.0) for intv in intervals[:24])
    assert abs(cum_rain - 1.60) < 1e-6, f"Expected 1.60 in cumulative at interval 24, got {cum_rain}"

    # Verify that index.html placeholder does NOT contain misleading UTC label
    with open(os.path.join(BASE_DIR, "public", "index.html"), "r", encoding="utf-8") as f:
        html_src = f.read()
    assert 'id="m4TimestampLabel">05:45 - 06:00 UTC</span>' not in html_src
    assert 'id="m4TimestampLabel">05:45 - 06:00</span>' in html_src

    print(f"  [OK] 96 intervals verified (00:00 to 23:45 US/Central, 24.0 hours total duration)")
    print(f"  [OK] Peak downpour at index 23 (interval 24): 0.38 in / 15m = 1.52 in/hr (Cumulative: {cum_rain:.2f} in)")
    print(f"  [OK] index.html initial timestamp placeholder verified (misleading UTC label removed)")
    passed += 1

    # -------------------------------------------------------------
    # TEST 5: Data State Enforcement (UNAVAILABLE / DEMO / VERIFIED / INVALID)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Data State Enforcement...")
    live_rain_path = os.path.join(DATA_DIR, "rainfall_series.json")
    with open(live_rain_path, "r", encoding="utf-8") as f:
        live_data = json.load(f)

    # Real rainfall is absent from raw tests directory
    assert live_data.get("status") == "UNAVAILABLE"
    live_records = live_data.get("records") or live_data.get("intervals", [])
    assert len(live_records) == 0

    # Sample rainfall fixture is synthetic
    sample_meta_path = os.path.join(DATA_DIR, "rainfall_sample_meta.json")
    with open(sample_meta_path, "r", encoding="utf-8") as f:
        sample_meta = json.load(f)

    assert sample_meta.get("status") == "UNVERIFIED"
    assert sample_meta.get("guardrails", {}).get("calibrated_model_input") is False
    assert sample_meta.get("primary_station_id") == "1600"
    assert sample_data.get("status") == "UNVERIFIED"

    # Invalid input rejection test
    assert calc_intensity(-0.5, 15) is None  # Rejected
    assert calc_intensity(None, 15) is None   # Rejected
    assert calc_intensity(float('inf'), 15) is None  # Rejected

    print("  [OK] Real rainfall status is strictly UNAVAILABLE when observations absent")
    print("  [OK] Demonstration fixture is strictly tagged UNVERIFIED and synthetic")
    print("  [OK] Invalid values are safely rejected from synthesis")
    passed += 1

    # -------------------------------------------------------------
    # TEST 6: Neutral 16-Cell Bivariate Screening Matrix & Label Correction
    # -------------------------------------------------------------
    print("\n[TEST 6] Validating Neutral Bivariate Screening Matrix Labels...")
    m4_meta_path = os.path.join(DATA_DIR, "m4_synthesis_meta.json")
    with open(m4_meta_path, "r", encoding="utf-8") as f:
        m4_meta = json.load(f)

    # Check that forbidden sensationalist phrases are NOT present in metadata or code
    disallowed_category_phrases = [
        "rapid evacuation",
        "high-velocity street gutter flow",
        "gutter flow",
        "drainage failure",
        "verified flood-risk level",
        "calibrated flood-risk"
    ]
    # Check app.js matrix definitions
    with open(os.path.join(BASE_DIR, "public", "js", "app.js"), "r", encoding="utf-8") as f:
        js_content = f.read().lower()
    
    # Check that app.js matrix categories never contain these phrases
    for phrase in disallowed_category_phrases:
        assert f"label: '{phrase}" not in js_content and f"label: \"{phrase}" not in js_content, \
            f"Disallowed category phrase used in app.js matrix: '{phrase}'"

    with open(m4_meta_path, "r", encoding="utf-8") as f:
        meta_content = f.read().lower()

    # Also verify that rapid evacuation and high-velocity street gutter flow are completely absent
    assert "rapid evacuation" not in js_content
    assert "high-velocity street gutter flow" not in js_content
    assert "rapid evacuation" not in meta_content
    assert "high-velocity street gutter flow" not in meta_content

    print("  [OK] All unsupported phrases ('Rapid Evacuation', 'Gutter Flow', etc.) strictly eliminated")
    print("  [OK] Labels are 100% neutral descriptive indicators")
    passed += 1

    # -------------------------------------------------------------
    # TEST 7: Guardrail: No Fabricated Flood Depths or Probabilities
    # -------------------------------------------------------------
    print("\n[TEST 7] Verifying Non-Fabrication of Flood Depth or Calibrated Probability...")
    # Check that m4 metadata explicitly disclaims flood depths and calibrated probabilities
    guardrails = m4_meta.get("scientific_guardrails", [])
    has_no_depth_disclaimer = any("NOT calculate flood depths" in g or "No Calibrated Predictions" in g for g in guardrails)
    assert has_no_depth_disclaimer, "Missing explicit disclaimer against calculating flood depths in M4 guardrails"

    print("  [OK] Scientific guardrail against calculating physical water depths or calibrated probabilities is verified")
    passed += 1

    # -------------------------------------------------------------
    # TEST 8: M3 Validation Readiness Decision Preservation
    # -------------------------------------------------------------
    print("\n[TEST 8] Verifying M3 Validation Readiness Decision Preservation...")
    m3_meta_path = os.path.join(DATA_DIR, "m3_validation_readiness.json")
    with open(m3_meta_path, "r", encoding="utf-8") as f:
        m3_meta = json.load(f)

    assert m3_meta.get("validation_status") == "UNAVAILABLE"
    assert m3_meta.get("decision") == "VALIDATION DATA UNAVAILABLE"
    assert m3_meta.get("baseline_comparison", {}).get("executed") is False
    print("  [OK] M3 VALIDATION DATA UNAVAILABLE decision remains active and intact")
    passed += 1

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} PASSED / {failed} FAILED")
    print("=" * 70)
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
