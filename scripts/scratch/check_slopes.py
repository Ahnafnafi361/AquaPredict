import json

with open('public/data/gravity_mains.geojson') as f:
    mains = json.load(f)['features']

count = 0
for m in mains:
    p = m['properties']
    sl = p.get('SLOPE')
    up = p.get('UPELEV')
    down = p.get('DOWNELEV')
    l = p.get('SHAPE.STLength()')
    if sl is not None and sl != '' and up is not None and down is not None and l and float(l) > 0:
        drop = float(up) - float(down)
        calc_ft_per_ft = drop / float(l)
        calc_pct = calc_ft_per_ft * 100.0
        calc_ft_per_1000 = calc_ft_per_ft * 1000.0
        print(f"FID: {p['FACILITYID']:8} | Source SLOPE: {float(sl):10.4f} | Drop: {drop:6.2f}ft, L: {float(l):6.1f}ft | Calc %: {calc_pct:8.4f} | Calc ft/1000: {calc_ft_per_1000:8.4f}")
        count += 1
        if count >= 20:
            break
