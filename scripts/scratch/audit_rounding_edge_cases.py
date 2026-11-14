"""Comprehensive cross-language comparison between Python and JavaScript rounding."""
import math
import subprocess
import json
import os

ROOT = r"c:\Users\ASUS\Desktop\AquaPredict"

# Test values across positive, negative, zero, and half-way boundaries
test_values = [
    # Negative longitude cases around Downtown Houston (-95.37...)
    -95.3700005,      # exact halfway between -95.370000 and -95.370001
    -95.370000499,    # just below halfway (closer to -95.370000)
    -95.370000501,    # just above halfway (closer to -95.370001)
    -95.3700015,
    -95.370001499,
    -95.370001501,
    -95.3700000,
    -95.3700001,
    -95.3700009,
    -95.3650005,
    -95.3750005,

    # Positive latitude cases around Downtown Houston (29.76...)
    29.7600005,       # exact halfway between 29.760000 and 29.760001
    29.760000499,     # just below halfway (closer to 29.760000)
    29.760000501,     # just above halfway (closer to 29.760001)
    29.7600015,
    29.760001499,
    29.760001501,
    29.7560005,
    29.7650005,

    # Fundamental half-way edge cases (integers * 0.5)
    -3.5, -2.5, -1.5, -0.5, 0.0, 0.5, 1.5, 2.5, 3.5,
    -0.5000005, -0.500000499, -0.500000501,
    0.5000005, 0.500000499, 0.500000501,

    # Micro edge cases near zero
    -0.0000005,
    -0.000000499,
    -0.000000501,
    0.0000005,
    0.000000499,
    0.000000501,
]

# Run JS Math.round via node
js_code = """
const fs = require('fs');
const vals = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const res = vals.map(v => {
  // Exact client formula from app.js line 3464-3465:
  // Math.round(v * 1000000) / 1000000
  const r6 = Math.round(v * 1000000) / 1000000;
  // Also 0 decimal places for comparison:
  const r0 = Math.round(v);
  return { v, r6, r0 };
});
fs.writeFileSync(process.argv[3], JSON.stringify(res, null, 2));
"""

tmp_in = os.path.join(ROOT, "scripts", "scratch", "vals_in.json")
tmp_out = os.path.join(ROOT, "scripts", "scratch", "vals_out.json")
tmp_js = os.path.join(ROOT, "scripts", "scratch", "eval_js_round.js")

with open(tmp_in, "w") as f:
    json.dump(test_values, f)
with open(tmp_js, "w") as f:
    f.write(js_code)

subprocess.run(["node", tmp_js, tmp_in, tmp_out], check=True)

with open(tmp_out, "r") as f:
    js_results = json.load(f)

# Python implementations
def py_round_half_up(val, places=6):
    mult = 10 ** places
    return math.floor(val * mult + 0.5) / mult

def py_std_round(val, places=6):
    return round(val, places)

def py_symmetric_round_away_from_zero(val, places=6):
    mult = 10 ** places
    if val >= 0:
        return math.floor(val * mult + 0.5) / mult
    else:
        return math.ceil(val * mult - 0.5) / mult

print(f"{'Input Value':20s} | {'JS Math.round':16s} | {'py round_half_up':16s} | {'py round()':16s} | {'py symmetric':16s} | {'Match?'}")
print("-" * 105)

mismatches_hu = 0
mismatches_std = 0
mismatches_sym = 0

for item in js_results:
    v = item["v"]
    js_r = item["r6"]
    py_hu = py_round_half_up(v, 6)
    py_std = py_std_round(v, 6)
    py_sym = py_symmetric_round_away_from_zero(v, 6)

    m_hu = (js_r == py_hu)
    m_std = (js_r == py_std)
    m_sym = (js_r == py_sym)

    if not m_hu: mismatches_hu += 1
    if not m_std: mismatches_std += 1
    if not m_sym: mismatches_sym += 1

    status = "OK" if m_hu else "MISMATCH"
    print(f"{v:<20.7f} | {js_r:<16.6f} | {py_hu:<16.6f} | {py_std:<16.6f} | {py_sym:<16.6f} | {status}")

print("-" * 105)
print(f"Summary on {len(test_values)} edge cases:")
print(f"  py round_half_up (math.floor(x*1e6+0.5)/1e6) vs JS Math.round: {mismatches_hu} mismatches")
print(f"  py standard round() (banker's round-half-to-even) vs JS Math.round: {mismatches_std} mismatches")
print(f"  py symmetric round (away from zero) vs JS Math.round: {mismatches_sym} mismatches")

# Clean up temporary scratch files
for p in [tmp_in, tmp_out, tmp_js]:
    if os.path.exists(p):
        os.remove(p)
