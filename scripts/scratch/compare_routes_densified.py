import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph, haversine_distance

def densify_polyline(coords, step_m=10.0):
    if len(coords) < 2:
        return list(coords)
    samples = []
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i+1]
        dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if dist <= 0.001:
            continue
        n_steps = max(1, int(round(dist / step_m)))
        for s in range(n_steps):
            frac = s / n_steps
            samples.append([p1[0] + frac * (p2[0] - p1[0]), p1[1] + frac * (p2[1] - p1[1])])
    samples.append(list(coords[-1]))
    return samples

# Create Graph 1: Original raw vertex sampling
g_raw = DrainageInformedRoutingGraph()
g_raw.build_graph()

# Create Graph 2: Densified 10m sampling
g_dens = DrainageInformedRoutingGraph()
g_dens.build_graph()

# Patch g_dens to use densified coords for depth lookup
orig_get_depth = g_dens._get_modelled_depth
def get_depth_densified(coords, preset_mm, timestep_idx):
    dens = densify_polyline(coords, 10.0)
    return orig_get_depth(dens, preset_mm, timestep_idx)
g_dens._get_modelled_depth = get_depth_densified

# Patch susc sampling too
orig_susc = g_dens._sample_susc_profile
def susc_densified(path):
    dens = densify_polyline(path, 10.0)
    return orig_susc(dens)
g_dens._sample_susc_profile = susc_densified

# Re-sample edge susc_mean in g_dens
for e in g_dens.edges:
    s_mean, s_max = susc_densified(e['coords'])
    e['susc_mean'] = round(s_mean, 3)
    e['susc_max'] = round(s_max, 3)

test_pairs = [
    ([-95.3705, 29.7580], [-95.3680, 29.7645], "Bagby & McKinney -> Milam & Franklin"),
    ([-95.3705, 29.7580], [-95.3660, 29.7610], "Bagby & McKinney -> Main & Capitol"),
    ([-95.3705, 29.7580], [-95.3670, 29.7570], "Bagby & McKinney -> Travis & Bell"),
    ([-95.3740, 29.7610], [-95.3660, 29.7610], "Walker & Sabine -> Main & Capitol"),
    ([-95.3730, 29.7570], [-95.3660, 29.7610], "Allen Pkwy & Clay -> Main & Capitol"),
    ([-95.3670, 29.7600], [-95.3670, 29.7570], "Milam & Capitol -> Travis & Bell"),
]

print("=== COMPARISON OF ROUTE COSTS: RAW VERTEX VS 10m DENSIFICATION ===")
for start, dest, label in test_pairs:
    for preset in [50, 100]:
        comp_raw = g_raw.compare_alternatives(start, dest, preset_mm=preset, timestep_idx=12, mode="pedestrian")
        comp_dens = g_dens.compare_alternatives(start, dest, preset_mm=preset, timestep_idx=12, mode="pedestrian")
        print(f"\n--- {label} ({preset}mm Storm @ Step 12) ---")
        for profile in ["baseline_shortest", "drainage_informed", "low_susceptibility"]:
            r_raw = comp_raw["alternatives"][profile]
            r_dens = comp_dens["alternatives"][profile]
            print(f"  {profile.upper()}:")
            print(f"    Raw:  Dist={r_raw['total_distance_m']}m, Score={r_raw['prototype_hazard_score']}, MaxDepth={r_raw['max_modelled_depth_m']}m, Submerged={r_raw['submerged_length_m']}m")
            print(f"    Dens: Dist={r_dens['total_distance_m']}m, Score={r_dens['prototype_hazard_score']}, MaxDepth={r_dens['max_modelled_depth_m']}m, Submerged={r_dens['submerged_length_m']}m")
