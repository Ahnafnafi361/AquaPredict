"""
AquaPredict Milestone 10 (M10) — Static Export Workflow
Exports precomputed scenarios, assets, GIS layers, and metadata
to allow offline/static hosting via plain HTTP server without Python backend.
"""

import os
import sys
import shutil
import json
import time

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

PUBLIC_DIR = os.path.join(WORKSPACE_DIR, "public")
DIST_STATIC_DIR = os.path.join(WORKSPACE_DIR, "dist_static")

PILOT_BBOX = [-95.3750, 29.7560, -95.3650, 29.7650]

REQUIRED_DATA_FILES = [
    "pilot_boundary.geojson",
    "dem_terrain.png",
    "dem_hillshade.png",
    "dem_grid.json",
    "dem_meta.json",
    "discharge.geojson",
    "gravity_mains.geojson",
    "inlets.geojson",
    "manholes.geojson",
    "quality_metrics.json",
    "susceptibility.png",
    "depressions.png",
    "inlet_proximity.png",
    "susceptibility_grid.json",
    "m1_analysis_meta.json",
    "rainfall_series.json",
    "rainfall_meta.json",
    "rainfall_sample_1600.json",
    "rainfall_sample_meta.json",
    "m3_validation_readiness.json",
    "m4_synthesis_meta.json",
    "rescue_priority_locations.json",
    "rescue_priority_meta.json",
    "simulation_scenarios.json",
    "m5_simulation_meta.json",
    "m6_drainage_network.json",
    "m6_analysis_meta.json",
    "street_network.geojson",
    "m7_routing_graph.json",
    "m7_route_planner_meta.json",
    "terrain_heightmap_256.json"
]

def generate_static_manifest():
    """Generates comprehensive static export manifest with scenario and provenance metadata."""
    scenarios_file = os.path.join(PUBLIC_DIR, "data", "simulation_scenarios.json")
    with open(scenarios_file, "r", encoding="utf-8") as f:
        scenarios_data = json.load(f)

    presets = scenarios_data.get("presets", {})
    exported_scenarios = {}
    for pid, pdata in presets.items():
        exported_scenarios[pid] = {
            "name": pdata.get("name", pid),
            "target_rainfall_mm": pdata.get("target_rainfall_mm"),
            "duration_minutes": pdata.get("duration_minutes", 180),
            "peak_minute": pdata.get("peak_minute", 60),
            "timestep_count": len(pdata.get("timesteps", [])),
            "timestep_interval_min": 5,
            "max_flood_depth_m": max((ts.get("max_depth_m", 0.0) for ts in pdata.get("timesteps", [])), default=0.0)
        }

    # Precompute sample routes for default landmarks so routing works offline in static mode
    precomputed_routes = {}
    try:
        from scripts.route_planner import DrainageInformedRoutingGraph
        rg = DrainageInformedRoutingGraph()
        rg.build_graph()
        # Default start and destination coordinates
        start_pt = [-95.3705, 29.7580]
        dest_pt = [-95.3680, 29.7645]
        for preset_val in [10, 25, 50, 75, 100]:
            precomputed_routes[f"preset_{preset_val}mm"] = rg.compare_alternatives(
                start_pt, dest_pt, preset_mm=preset_val, timestep_idx=12, mode="pedestrian"
            )
    except Exception as e:
        print(f"  [Notice] Precomputing routes: {e}")

    manifest = {
        "export_mode": "static_precomputed",
        "export_version": "1.0.0",
        "generated_timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "pilot_area": {
            "name": "Downtown Houston / Buffalo Bayou",
            "bounding_box_wgs84": PILOT_BBOX,
            "area_km2": 0.97
        },
        "model_framework": {
            "screening_model": "AquaPredict M5 Physical Hydrological Screening Model",
            "routing_engine": "M7 Drainage-Informed Network Routing Engine",
            "terrain_source": "NOAA 2018 StratMap LiDAR Bare Earth DEM (1m)",
            "drainage_source": "City of Houston Stormwater GIS (Inlets, Manholes, Gravity Mains, Outfalls)"
        },
        "scientific_disclaimers": [
            "EXPLORATORY SCREENING MODEL ONLY — NOT A CERTIFIED REAL-TIME FLOOD FORECASTING OR WARNING SYSTEM.",
            "SYNTHETIC SURROGATE & MODELLED ESTIMATES: Not calibrated or validated against historical flood sensor observations.",
            "Drainage capacity calculations assume clean, unobstructed conduits with free outfall into Buffalo Bayou.",
            "Static mode displays precomputed scenario simulations and pre-extracted continuous heightmaps."
        ],
        "scenarios": exported_scenarios,
        "precomputed_routes": precomputed_routes
    }
    return manifest

def export_static(output_dir=DIST_STATIC_DIR):
    print("=" * 70)
    print(" AquaPredict Milestone 10 (M10) — Static Export Generator")
    print(f" Target Directory: {output_dir}")
    print(f" Pilot Bounding Box: {PILOT_BBOX}")
    print("=" * 70)

    # 1. Clean and initialize target directory
    if os.path.exists(output_dir):
        print(f"Cleaning existing target directory: {output_dir}")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # 2. Copy directories
    for sub in ["css", "js", "i18n", "assets"]:
        src_sub = os.path.join(PUBLIC_DIR, sub)
        dst_sub = os.path.join(output_dir, sub)
        if os.path.exists(src_sub):
            shutil.copytree(src_sub, dst_sub)
            print(f"Copied directory: {sub}/")

    # Copy root i18n into dist_static/i18n if not present
    root_i18n = os.path.join(WORKSPACE_DIR, "i18n")
    dst_i18n = os.path.join(output_dir, "i18n")
    os.makedirs(dst_i18n, exist_ok=True)
    for fname in ["bn.json", "en.json"]:
        src_f = os.path.join(root_i18n, fname)
        dst_f = os.path.join(dst_i18n, fname)
        if os.path.exists(src_f) and not os.path.exists(dst_f):
            shutil.copy2(src_f, dst_f)

    # 3. Copy public/data files
    dst_data = os.path.join(output_dir, "data")
    os.makedirs(dst_data, exist_ok=True)
    src_data = os.path.join(PUBLIC_DIR, "data")

    copied_files_count = 0
    for fname in REQUIRED_DATA_FILES:
        src_f = os.path.join(src_data, fname)
        dst_f = os.path.join(dst_data, fname)
        if os.path.exists(src_f):
            shutil.copy2(src_f, dst_f)
            copied_files_count += 1
        else:
            print(f"  [WARNING] Required file not found: {fname}")

    print(f"Copied {copied_files_count} data files into data/")

    # 4. Generate and save static export manifest
    print("Generating static export manifest and precomputing routes...")
    manifest = generate_static_manifest()
    manifest_path = os.path.join(dst_data, "static_export_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written manifest to: data/static_export_manifest.json")

    # 5. Process and copy HTML files (index.html, app.html, pricing.html, auth.html) with static mode flag injected
    flag_script = """  <!-- Milestone M10: Precomputed Static Export Mode Flag -->
  <script>
    window.AQUAPREDICT_STATIC_MODE = true;
  </script>
</head>"""

    for html_file in ["index.html", "app.html", "pricing.html", "auth.html"]:
        src_path = os.path.join(PUBLIC_DIR, html_file)
        dst_path = os.path.join(output_dir, html_file)
        if os.path.exists(src_path):
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "</head>" in content and "window.AQUAPREDICT_STATIC_MODE" not in content:
                content = content.replace("</head>", flag_script, 1)
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Copied {html_file} to static output.")


    # 6. Summary
    total_size = 0
    total_files = 0
    for root, _, files in os.walk(output_dir):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
            total_files += 1

    print("-" * 70)
    print(" STATIC EXPORT COMPLETE")
    print(f" Total Files: {total_files}")
    print(f" Total Size : {round(total_size / (1024*1024), 2)} MB")
    print(f" Destination: {output_dir}")
    print("-" * 70)
    return output_dir

if __name__ == "__main__":
    export_static()
