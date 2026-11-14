import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

bbox = [-95.375, 29.756, -95.365, 29.765]
print("Pilot bounds:", bbox)

# 1. Check USGS STN for HWMs in bbox
try:
    url = f"https://stn.wim.usgs.gov/STNServices/HWMs.json?sw_lat={bbox[1]}&sw_lon={bbox[0]}&ne_lat={bbox[3]}&ne_lon={bbox[2]}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        hwms = json.loads(resp.read().decode())
        print(f"USGS STN HWM count in pilot bbox: {len(hwms)}")
        for h in hwms:
            print(f"  HWM ID {h.get('hwm_id')}: Waterbody={h.get('waterbody')}, Elev={h.get('elev_ft')} ft ({h.get('vdatum_id')}), Type={h.get('hwm_type')}, Lat={h.get('latitude')}, Lon={h.get('longitude')}, Event={h.get('event_id')}")
except Exception as e:
    print("USGS STN query error:", e)

# 2. Check USGS STN Sensors in bbox
try:
    url = f"https://stn.wim.usgs.gov/STNServices/Instruments.json?sw_lat={bbox[1]}&sw_lon={bbox[0]}&ne_lat={bbox[3]}&ne_lon={bbox[2]}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        inst = json.loads(resp.read().decode())
        print(f"USGS STN Instruments in pilot bbox: {len(inst)}")
except Exception as e:
    print("USGS STN instruments error:", e)

# 3. Check City of Houston 311 for flood categories in bbox
try:
    url = f"https://geogimsms.houstontx.gov/arcgis/rest/services/EMC/Active311SR/FeatureServer/0/query?geometry={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        res = json.loads(resp.read().decode())
        feats = res.get('features', [])
        print(f"Houston Active 311 count in bbox: {len(feats)} (limit exceeded: {res.get('exceededTransferLimit')})")
        types = {}
        flood_related = []
        for f in feats:
            attrs = f.get('attributes', {})
            ct = attrs.get('CASE_TYPE', 'Unknown')
            types[ct] = types.get(ct, 0) + 1
            if any(term in str(attrs).lower() for term in ['flood', 'waterlog', 'high water', 'drain', 'pond']):
                flood_related.append(attrs)
        print("  Top 5 311 types:")
        for t, c in sorted(types.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    - {t}: {c}")
        print(f"  Flood/drainage related tickets in bbox: {len(flood_related)}")
        for fr in flood_related[:5]:
            print(f"    - {fr.get('CASE_TYPE')} | {fr.get('SR_CREATE_DATE')} | {fr.get('INCIDENT_ADDRESS')}")
except Exception as e:
    print("Houston 311 error:", e)
