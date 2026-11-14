import os
import json
from collections import Counter
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(WORKSPACE_DIR, "public", "data")

def audit_dataset(filename):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    feats = data.get("features", [])
    geom_types = Counter(f["geometry"]["type"] for f in feats)
    
    print(f"\n{'='*70}")
    print(f"FILE: {filename}")
    print(f"{'='*70}")
    print(f"Total Features: {len(feats)}")
    print(f"Geometry Types: {dict(geom_types)}")
    print(f"CRS: {data.get('crs', 'WGS84 implied')}")
    
    if not feats:
        return
    
    all_keys = list(feats[0]["properties"].keys())
    print(f"Attributes Count: {len(all_keys)}")
    print(f"Attribute Names: {all_keys}")
    
    # Analyze null / blank / valid counts per attribute
    field_stats = {}
    for k in all_keys:
        vals = [f["properties"].get(k) for f in feats]
        non_null = [v for v in vals if v is not None and v != "" and v != " " and v != "null"]
        field_stats[k] = {
            "total": len(vals),
            "non_null_count": len(non_null),
            "pct_complete": round(len(non_null) / len(vals) * 100, 2),
            "sample_values": non_null[:5] if non_null else []
        }
    
    print("\nAttribute Completeness & Samples:")
    for k, st in field_stats.items():
        print(f"  {k:25} | {st['non_null_count']:4d}/{st['total']:4d} ({st['pct_complete']:6.2f}%) | Samples: {st['sample_values'][:3]}")
        
    return feats, field_stats

# Run audit on all 4 files
mains_feats, mains_stats = audit_dataset("gravity_mains.geojson")
inlets_feats, inlets_stats = audit_dataset("inlets.geojson")
manholes_feats, manholes_stats = audit_dataset("manholes.geojson")
discharge_feats, discharge_stats = audit_dataset("discharge.geojson")
