import urllib.request

endpoints = [
    '/',
    '/css/style.css',
    '/js/app.js',
    '/data/pilot_boundary.geojson',
    '/data/dem_terrain.png',
    '/data/dem_hillshade.png',
    '/data/dem_grid.json',
    '/data/dem_meta.json',
    '/data/discharge.geojson',
    '/data/gravity_mains.geojson',
    '/data/inlets.geojson',
    '/data/manholes.geojson',
    '/data/quality_metrics.json',
    '/data/susceptibility.png',
    '/data/depressions.png',
    '/data/inlet_proximity.png',
    '/data/susceptibility_grid.json',
    '/data/m1_analysis_meta.json',
    '/data/rainfall_series.json',
    '/data/rainfall_meta.json',
    '/data/rainfall_sample_1600.json',
    '/data/rainfall_sample_meta.json',
    '/data/m3_validation_readiness.json',
    '/data/m4_synthesis_meta.json',
    '/data/simulation_scenarios.json',
    '/data/m5_simulation_meta.json',
    '/data/m6_drainage_network.json',
    '/data/m6_analysis_meta.json',
    '/data/street_network.geojson',
    '/data/m7_routing_graph.json',
    '/data/m7_route_planner_meta.json',
    '/data/terrain_heightmap_256.json',
    '/api/terrain/heightmap'
]

def run_endpoint_checks():
    base = 'http://localhost:8000'
    for ep in endpoints:
        url = base + ep
        req = urllib.request.Request(url, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            print(f'[OK 200] {ep:35} {len(data):>9} bytes', flush=True)

    print(f'\nAll {len(endpoints)} endpoints returned 200 OK!', flush=True)

if __name__ == '__main__':
    run_endpoint_checks()

