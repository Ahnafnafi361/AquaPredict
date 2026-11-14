/**
 * AquaPredict M7 — JavaScript cost/sampling parity bridge (test support only).
 *
 * Extracts the *actual* client-side functions `haversineDist`, `densifyPolyline`
 * and `calculateEdgeCost` verbatim from public/js/app.js (no hand-copied
 * duplicates, so drift between the browser code and this bridge is impossible),
 * evaluates them in an isolated VM context, and runs a batch of cases supplied
 * as JSON. Used by scripts/test_m7_parity.py to compare against route_planner.py.
 *
 * Usage:  node scripts/m7_js_parity_bridge.js <cases.json> <out.json>
 *
 * cases.json schema:
 * {
 *   "contexts": { "<name>": { "simScenarios": <obj|null>, "m6Data": <obj|null> } },
 *   "densify":  [ { "id": any, "coords": [[lon,lat],...] } ],
 *   "costs":    [ { "id": any, "ctx": "<name>", "edge": {...}, "preset": n, "step": n } ]
 * }
 * Context values may be the string "@real" to load the published data file.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const APP_JS = path.join(ROOT, 'public', 'js', 'app.js');

function extractFunction(src, name) {
  const sig = 'function ' + name + '(';
  const start = src.indexOf(sig);
  if (start < 0) throw new Error('Function not found in app.js: ' + name);
  const braceStart = src.indexOf('{', src.indexOf(')', start));
  let depth = 0;
  for (let i = braceStart; i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error('Unbalanced braces extracting ' + name);
}

function main() {
  const [casesPath, outPath] = process.argv.slice(2);
  if (!casesPath || !outPath) {
    console.error('usage: node m7_js_parity_bridge.js <cases.json> <out.json>');
    process.exit(2);
  }
  const appSrc = fs.readFileSync(APP_JS, 'utf8');
  const fnSrc = ['haversineDist', 'densifyPolyline', 'calculateEdgeCost']
    .map(n => extractFunction(appSrc, n)).join('\n\n');

  const sandbox = { state: { simScenarios: null, m6Data: null }, Math, console };
  vm.createContext(sandbox);
  vm.runInContext(fnSrc, sandbox, { filename: 'app.js[extracted]' });

  const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
  const realCache = {};
  const loadReal = (key) => {
    if (!realCache[key]) {
      const file = key === 'simScenarios' ? 'simulation_scenarios.json' : 'm6_drainage_network.json';
      realCache[key] = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'data', file), 'utf8'));
    }
    return realCache[key];
  };
  const contexts = {};
  for (const [name, ctx] of Object.entries(cases.contexts || {})) {
    contexts[name] = {
      simScenarios: ctx.simScenarios === '@real' ? loadReal('simScenarios') : ctx.simScenarios,
      m6Data: ctx.m6Data === '@real' ? loadReal('m6Data') : ctx.m6Data
    };
  }

  const out = { densify: [], costs: [] };
  for (const d of cases.densify || []) {
    out.densify.push({ id: d.id, samples: sandbox.densifyPolyline(d.coords, 10.0) });
  }
  for (const c of cases.costs || []) {
    const ctx = contexts[c.ctx];
    if (!ctx) throw new Error('Unknown context ' + c.ctx);
    sandbox.state.simScenarios = ctx.simScenarios;
    sandbox.state.m6Data = ctx.m6Data;
    const r = sandbox.calculateEdgeCost(c.edge, c.preset, c.step, 'pedestrian');
    out.costs.push(Object.assign({ id: c.id }, r));
  }
  fs.writeFileSync(outPath, JSON.stringify(out));
}

main();
