import os
import sys
import json

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(WORKSPACE_DIR, 'scripts'))
from route_planner import DrainageInformedRoutingGraph

g = DrainageInformedRoutingGraph()
g.build_graph()

start_landmarks = [
    ("-95.3740,29.7610", "Walker & Sabine (West Ridge)"),
    ("-95.3705,29.7580", "Bagby & McKinney (SW City Hall)"),
    ("-95.3730,29.7570", "Allen Pkwy & Clay (Southwest)"),
    ("-95.3670,29.7600", "Milam & Capitol (Central Core)"),
    ("-95.3710,29.7640", "Franklin & Bagby (Northwest)")
]

dest_landmarks = [
    ("-95.3680,29.7645", "Milam & Franklin (Bayou NE Channel)"),
    ("-95.3660,29.7610", "Main & Capitol (East Core)"),
    ("-95.3670,29.7570", "Travis & Bell (South Core)"),
    ("-95.3720,29.7625", "Preston & Heiner (Northwest Low)")
]

print("=== TESTING ALL LANDMARK PAIRS ===")
for s_coords, s_name in start_landmarks:
    s_lon, s_lat = map(float, s_coords.split(','))
    s_node, s_dist = g.snap_to_nearest_node(s_lon, s_lat)
    for d_coords, d_name in dest_landmarks:
        d_lon, d_lat = map(float, d_coords.split(','))
        d_node, d_dist = g.snap_to_nearest_node(d_lon, d_lat)

        res_ped = g.find_route([s_lon, s_lat], [d_lon, d_lat], mode="pedestrian")
        res_veh = g.find_route([s_lon, s_lat], [d_lon, d_lat], mode="vehicle")

        ped_ok = res_ped['status'] == 'SUCCESS'
        veh_ok = res_veh['status'] == 'SUCCESS'
        print(f"From '{s_name}' (node {s_node}) to '{d_name}' (node {d_node}):")
        print(f"  Pedestrian: {res_ped['status']} (dist={res_ped.get('total_distance_m')}m)")
        print(f"  Vehicle:    {res_veh['status']} (dist={res_veh.get('total_distance_m')}m)")
