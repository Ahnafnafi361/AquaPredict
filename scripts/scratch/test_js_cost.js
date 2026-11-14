const fs = require('fs');
const path = require('path');

const WORKSPACE_DIR = path.resolve(__dirname, '..', '..');
const graph = JSON.parse(fs.readFileSync(path.join(WORKSPACE_DIR, 'public', 'data', 'm7_routing_graph.json'), 'utf8'));
const sim = JSON.parse(fs.readFileSync(path.join(WORKSPACE_DIR, 'public', 'data', 'simulation_scenarios.json'), 'utf8'));
const m6 = JSON.parse(fs.readFileSync(path.join(WORKSPACE_DIR, 'public', 'data', 'm6_drainage_network.json'), 'utf8'));

// Exact calculateEdgeCost from app.js lines 3467-3549
function calculateEdgeCost(edge, presetMm, timestepIdx, mode) {
  const cBase = edge.length_m;
  const ewsi = edge.susc_mean !== undefined ? edge.susc_mean : 0.25;
  const mSusc = 1.0 + (1.0 * ewsi);

  // Modelled Depth from M5 sparse depths
  let maxDepthM = 0.0;
  if (sim) {
    const pKey = 'preset_' + presetMm + 'mm';
    const ts = sim.presets?.[pKey]?.timesteps?.[timestepIdx];
    if (ts && ts.sparse_depths) {
      const b = { west: -95.3750, south: 29.7560, east: -95.3650, north: 29.7650 };
      edge.coords.forEach(pt => {
        const lon = pt[0], lat = pt[1];
        if (lon >= b.west && lon <= b.east && lat >= b.south && lat <= b.north) {
          const col = Math.min(Math.max(Math.floor((lon - b.west) / (b.east - b.west) * 100), 0), 99);
          const row = Math.min(Math.max(Math.floor((b.north - lat) / (b.north - b.south) * 100), 0), 99);
          const flatIdx = row * 100 + col;
          const found = ts.sparse_depths.find(p => p[0] === flatIdx);
          if (found && found[1] > maxDepthM) maxDepthM = found[1];
        }
      });
    }
  }

  // Depth Penalty (P_depth)
  let pDepth = 0.0;
  if (maxDepthM > 0.0) {
    if (maxDepthM <= 0.05) {
      pDepth = (maxDepthM / 0.05) * 50.0;
    } else if (maxDepthM <= 0.20) {
      pDepth = 150.0 + ((maxDepthM - 0.05) / 0.15) * 350.0;
    } else if (maxDepthM <= 0.50) {
      pDepth = 500.0 + ((maxDepthM - 0.20) / 0.30) * 1500.0;
    } else {
      pDepth = 2000.0 + (maxDepthM - 0.50) * 5000.0;
    }
  }

  // Drainage Screening Penalty (P_drain)
  let pDrain = 0.0;
  let exceededCount = 0;
  let highCount = 0;
  if (m6 && edge.nearby_conduit_ids && edge.nearby_conduit_ids.length > 0) {
    const pKey = 'preset_' + presetMm + 'mm';
    const m6Step = m6.dynamic_simulation_loading?.[pKey]?.timesteps?.[timestepIdx];
    const baseInflow = m6Step ? m6Step.inflow_rate_per_inlet_m3s : 0.0;

    edge.nearby_conduit_ids.forEach(cid => {
      const c = m6.conduits?.[cid];
      if (c && c.capacity_m3s > 0) {
        const q = (c.contributing_inlet_fraction || 0.0) * baseInflow;
        const ratio = q / c.capacity_m3s;
        if (ratio > 1.0) exceededCount++;
        else if (ratio >= 0.70) highCount++;
      }
    });

    pDrain = (exceededCount * 100.0) + (highCount * 30.0);
  }

  // Data Uncertainty Penalty (P_uncert)
  let pUncert = 0.0;
  const midPt = edge.coords[Math.floor(edge.coords.length / 2)];
  if (midPt[0] < -95.3750 || midPt[0] > -95.3650 || midPt[1] < 29.7560 || midPt[1] > 29.7650) {
    pUncert += 80.0;
  }

  const totalCost = (cBase * mSusc) + pDepth + pDrain + pUncert;

  return {
    totalCost: Math.round(totalCost * 10) / 10,
    cBase: cBase,
    mSusc: mSusc,
    pDepth: Math.round(pDepth * 10) / 10,
    pDrain: Math.round(pDrain * 10) / 10,
    pUncert: Math.round(pUncert * 10) / 10,
    maxDepthM: Math.round(maxDepthM * 1000) / 1000,
    exceededCount: exceededCount,
    highCount: highCount,
    ewsi: ewsi
  };
}

// Compare edge 0, 10, 20 in JS
console.log("JS Edge Costs (50mm, step 12):");
for (const eId of [0, 10, 20, 22, 50, 100]) {
  const cost = calculateEdgeCost(graph.edges[eId], 50, 12, 'pedestrian');
  console.log(`  Edge ${eId} (${graph.edges[eId].name}): totalCost=${cost.totalCost}, cBase=${cost.cBase}, pDepth=${cost.pDepth}, pDrain=${cost.pDrain}, pUncert=${cost.pUncert}`);
}
