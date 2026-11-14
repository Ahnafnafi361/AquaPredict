import json
import os
import math

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_FILE = os.path.join(WORKSPACE_DIR, 'scripts', 'scratch', 'raw_street_centerlines.json')
OUT_GEOJSON = os.path.join(WORKSPACE_DIR, 'public', 'data', 'street_network.geojson')

with open(SCRATCH_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)

features = raw.get('features', [])
print(f"Loaded {len(features)} raw street features from Houston GIS")

geojson_features = []
total_length_m = 0.0

for idx, feat in enumerate(features):
    attrs = dict(feat.get('attributes', {}))
    geom = feat.get('geometry', {})
    paths = geom.get('paths', [])
    
    # If multiple paths, use MultiLineString, else LineString
    if len(paths) == 1:
        gtype = "LineString"
        coords = [[round(pt[0], 6), round(pt[1], 6)] for pt in paths[0]]
    else:
        gtype = "MultiLineString"
        coords = [[[round(pt[0], 6), round(pt[1], 6)] for pt in path] for path in paths]
        
    length_ft = attrs.get('Shape.STLength()', 0.0)
    length_m = round(length_ft * 0.3048, 2)
    total_length_m += length_m
    
    # Clean and preserve municipal properties
    props = {
        "objectid": attrs.get('OBJECTID', idx + 1),
        "starmap_id": attrs.get('STARMAP_ID'),
        "name": attrs.get('FULL_NAME') or (str(attrs.get('NAME', 'UNNAMED')) + ' ' + str(attrs.get('ST_TYPE', ''))).strip(),
        "road_class": attrs.get('ROAD_CLASS', 'LOCAL'),
        "one_way": attrs.get('ONE_WAY', ' ').strip() or 'BI',
        "speed_limit_mph": attrs.get('SPEED', 30),
        "length_ft": length_ft,
        "length_m": length_m,
        "source": "City of Houston Enterprise GIS (DIR/LandbaseandRoads_gx/MapServer/9)"
    }
    
    geojson_features.append({
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": gtype,
            "coordinates": coords
        }
    })

geojson_doc = {
    "type": "FeatureCollection",
    "name": "Houston_Downtown_Street_Centerlines",
    "crs": {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    },
    "metadata": {
        "source": "City of Houston Enterprise GIS",
        "layer": "DIR/LandbaseandRoads_gx/MapServer/9 (Street Centerlines)",
        "query_bounds": [-95.3750, 29.7560, -95.3650, 29.7650],
        "feature_count": len(geojson_features),
        "total_length_km": round(total_length_m / 1000.0, 2),
        "date_accessed": "October 2026",
        "scientific_disclaimer": "Municipal street centerlines for prototype routing research. Not certified for navigation or emergency evacuation."
    },
    "features": geojson_features
}

with open(OUT_GEOJSON, 'w', encoding='utf-8') as f:
    json.dump(geojson_doc, f, indent=2)

print(f"Wrote {len(geojson_features)} features to {OUT_GEOJSON}")
print(f"Total network length: {total_length_m / 1000.0:.2f} km")
