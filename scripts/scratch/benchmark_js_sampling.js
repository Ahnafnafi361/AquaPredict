const fs = require('fs');
const path = require('path');

const WORKSPACE_DIR = path.resolve(__dirname, '..', '..');
const graph = JSON.parse(fs.readFileSync(path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json'), 'utf8'));
const sim = JSON.parse(fs.readFileSync(path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json'), 'utf8'));

function haversineDist(lon1, lat1, lon2, lat2) {
  const R = 6371000;
  const p1 = lat1 * Math.PI / 180;
  const p2 = lat2 * Math.PI / 180;
  const dp = (lat2 - lat1) * Math.PI / 180;
  const dl = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dp / 2) * Math.sin(dp / 2) + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function densifyPolyline(coords, stepM = 10.0) {
  if (!coords || coords.length < 2) return coords || [];
  const samples = [];
  for (let i = 0; i < coords.length - 1; i++) {
    const p1 = coords[i];
    const p2 = coords[i + 1];
    const d = haversineDist(p1[0], p1[1], p2[0], p2[1]);
    if (d <= 0.001) continue;
    const nSteps = Math.max(1, Math.round(d / stepM));
    for (let s = 0; s < nSteps; s++) {
      const frac = s / nSteps;
      samples.push([
        Math.round((p1[0] + frac * (p2[0] - p1[0])) * 1000000) / 1000000,
        Math.round((p1[1] + frac * (p2[1] - p1[1])) * 1000000) / 1000000
      ]);
    }
  }
  const last = coords[coords.length - 1];
  samples.push([
    Math.round(last[0] * 1000000) / 1000000,
    Math.round(last[1] * 1000000) / 1000000
  ]);
  return samples;
}

// Measure time for all 210 edges
const t0 = Date.now();
let totalSamples = 0;
const ts = sim.presets['preset_50mm'].timesteps[12];
// Use Map for O(1) lookup
const depthMap = new Map(ts.sparse_depths);

graph.edges.forEach(e => {
  const pts = densifyPolyline(e.coords, 10.0);
  totalSamples += pts.length;
  let maxD = 0;
  pts.forEach(pt => {
    const col = Math.min(Math.max(Math.floor((pt[0] - (-95.3750)) / 0.0100 * 100), 0), 99);
    const row = Math.min(Math.max(Math.floor((29.7650 - pt[1]) / 0.0090 * 100), 0), 99);
    const fIdx = row * 100 + col;
    const d = depthMap.get(fIdx) || 0;
    if (d > maxD) maxD = d;
  });
});
const dt = Date.now() - t0;
console.log(`Densified sampling performance across all ${graph.edges.length} edges:`);
console.log(`  Total sample points: ${totalSamples}`);
console.log(`  Total execution time: ${dt} ms`);
