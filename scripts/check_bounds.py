import json
import rasterio.warp

for name in ['Discharge', 'GravityMains', 'Inlets', 'Manholes']:
    with open(f'C:/AquaPredict_tests/feat_{name}.json', encoding='utf-8-sig') as f:
        d = json.load(f)
    xs, ys = [], []
    for feat in d['features']:
        geom = feat['geometry']
        if 'x' in geom:
            xs.append(geom['x'])
            ys.append(geom['y'])
        elif 'paths' in geom:
            for path in geom['paths']:
                for pt in path:
                    xs.append(pt[0])
                    ys.append(pt[1])
    lons, lats = rasterio.warp.transform('EPSG:2278', 'EPSG:4326', xs, ys)
    print(f"{name} ({len(d['features'])} features):")
    print(f"  Lon: [{min(lons):.5f}, {max(lons):.5f}], Lat: [{min(lats):.5f}, {max(lats):.5f}]")
