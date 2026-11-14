import json

with open("public/data/gravity_mains.geojson", "r", encoding="utf-8") as f:
    feats = json.load(f)["features"]

w_zero = 0
w_none = 0
w_neg = 0
for f in feats:
    p = f["properties"]
    w = p.get("WIDTH")
    if w is None or str(w).strip() == '':
        w_none += 1
    else:
        try:
            fw = float(w)
            if fw == 0.0:
                w_zero += 1
            elif fw < 0.0:
                w_neg += 1
        except:
            w_none += 1

print(f"WIDTH == 0: {w_zero}")
print(f"WIDTH is None or blank: {w_none}")
print(f"WIDTH < 0: {w_neg}")
print(f"Total diameter invalid: {w_zero + w_none + w_neg}")
