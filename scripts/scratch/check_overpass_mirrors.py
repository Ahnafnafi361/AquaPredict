import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

bbox = (29.7560, -95.3750, 29.7650, -95.3650)
query = f"""[out:json][timeout:15];
way["highway"~"primary|secondary|tertiary|residential|service|footway|pedestrian|path"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
(._;>;);
out body qt;"""

endpoints = [
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass-api.de/api/interpreter'
]

for ep in endpoints:
    try:
        print(f"Trying {ep}...")
        req = urllib.request.Request(ep, data=query.encode('utf-8'), headers={'User-Agent': 'AquaPredict-Auditor/1.0'})
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            ways = [e for e in data.get('elements', []) if e.get('type') == 'way']
            nodes = [e for e in data.get('elements', []) if e.get('type') == 'node']
            print(f"SUCCESS from {ep}: {len(ways)} ways, {len(nodes)} nodes")
            with open('scripts/scratch/osm_streets.json', 'w', encoding='utf-8') as f:
                json.dump(data, f)
            break
    except Exception as e:
        print(f"Failed {ep}: {e}")
