import urllib.request
import json
import ssl
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

bbox = [-95.3750, 29.7560, -95.3650, 29.7650]
url = f'https://geogimsms.houstontx.gov/arcgis/rest/services/DIR/LandbaseandRoads_gx/MapServer/9/query?geometry={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&outSR=4326&f=json'

print("Querying City of Houston Street Centerlines (Layer 9)...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
    raw_data = json.loads(r.read().decode())

features = raw_data.get('features', [])
print(f"Total street centerline features received: {len(features)}")

# Save raw copy in scratch
os.makedirs('scripts/scratch', exist_ok=True)
with open('scripts/scratch/raw_street_centerlines.json', 'w', encoding='utf-8') as f:
    json.dump(raw_data, f, indent=2)

street_names = set()
one_way_vals = {}
road_classes = {}
total_len_ft = 0.0

for f in features:
    attrs = f.get('attributes', {})
    name = attrs.get('FULL_NAME')
    if name:
        street_names.add(name)
    ow = attrs.get('ONE_WAY', 'UNKNOWN')
    one_way_vals[ow] = one_way_vals.get(ow, 0) + 1
    rc = attrs.get('ROAD_CLASS', 'UNKNOWN')
    road_classes[rc] = road_classes.get(rc, 0) + 1
    total_len_ft += attrs.get('Shape.STLength()', 0.0)

print(f"Unique Street Names ({len(street_names)}):")
for n in sorted(street_names)[:25]:
    print(f"  - {n}")
print(f"One-Way distribution: {one_way_vals}")
print(f"Road Class distribution: {road_classes}")
print(f"Total Street Length: {total_len_ft:.1f} ft ({total_len_ft * 0.3048:.1f} m)")
