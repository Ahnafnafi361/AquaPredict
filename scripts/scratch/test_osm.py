import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

bbox = (29.7560, -95.3750, 29.7650, -95.3650) # south, west, north, east
query = f"""[out:json][timeout:25];
(
  way["highway"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body;
>;
out skel qt;"""

url = 'https://overpass-api.de/api/interpreter'
req = urllib.request.Request(url, data=query.encode('utf-8'), headers={'User-Agent': 'AquaPredict/1.0'})
try:
    with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        ways = [e for e in data.get('elements', []) if e.get('type') == 'way']
        nodes = [e for e in data.get('elements', []) if e.get('type') == 'node']
        print(f"Overpass SUCCESS: Ways: {len(ways)}, Nodes: {len(nodes)}")
        with open('scripts/scratch/osm_raw.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
except Exception as e:
    print('Overpass error:', e)
