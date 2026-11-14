/**
 * AquaPredict M0 Prototype
 * Urban Waterlogging Risk Visualization - Houston Pilot Area
 */

// Strict Pilot Bounding Box (NOAA DEM Verified Extent)
const PILOT_BBOX = {
  west: -95.3750,
  south: 29.7560,
  east: -95.3650,
  north: 29.7650
};

const PILOT_BOUNDS = [
  [PILOT_BBOX.south, PILOT_BBOX.west],
  [PILOT_BBOX.north, PILOT_BBOX.east]
];

// Application State
const state = {
  map: null,
  layers: {
    pilotBoundary: null,
    demTerrain: null,
    demHillshade: null,
    susceptibility: null,
    depressions: null,
    inletProximity: null,
    gravityMains: null,
    inlets: null,
    manholes: null,
    discharge: null,
    rainfallGauge: null,
    m4SynthesisOverlay: null,
    simulationOverlay: null
  },
  basemaps: {},
  currentBasemap: 'dark',
  demMode: 'terrain', // 'terrain' or 'hillshade'
  demOpacity: 0.85,
  demGrid: null,
  suscMode: 'composite', // 'composite', 'depressions', 'proximity'
  suscOpacity: 0.75,
  suscGrid: null,
  m1Meta: null,
  qualityData: null,
  selectedFeature: null,
  rainfallSource: 'live', // 'live' or 'sample'
  rainfallLive: null,
  rainfallSample: null,
  rainfallMeta: null,
  validationReadiness: null,
  // Rescue Priority Predictor State (Replacing M4 Dynamic Synthesis)
  rescueLocations: null,
  rescueRiskAssessments: [],
  rescueMarkersLayerGroup: null,
  rescueWaterloggingLayerGroup: null,
  rescueHighlightLayerGroup: null,
  rescueShowMarkers: true,
  activeRescueLocId: null,
  // Milestone 5 (M5) Scenario Simulation State
  simScenarios: null,
  simActivePreset: 50,
  simActiveStepIdx: 0,
  simLayerEnabled: false,
  simOpacity: 0.85,
  simLifecycle: 'ready', // 'ready', 'running', 'paused', 'completed', 'reset'
  simIsPlaying: false,
  simTimer: null,
  simWorkflowDrawerOpen: false,
  // Milestone 9 (M9) ML Surrogate State
  simEngine: 'original', // 'original' or 'surrogate'
  surrogateCache: {},
  surrogateActiveFrame: null,
  // Milestone 6 (M6) Drainage Network & Hydraulic Capacity State
  m6Data: null,
  m6ActiveTraceLayer: null,
  drainageLoadingMode: false,
  activeInspectorAsset: null,
  // Milestone 7 (M7) Safest Route Planner State
  streetNetwork: null,
  routingGraph: null,
  m7Meta: null,
  streetNetworkLayer: null,
  routeLayerGroup: null,
  routeStartMarker: null,
  routeDestMarker: null,
  routeStartCoords: [-95.3705, 29.7580],
  routeDestCoords: [-95.3680, 29.7645],
  routeMode: 'pedestrian',
  activeRouteProfile: 'drainage_informed',
  routeAlternatives: null,
  pickingRoutePoint: null,
  // Milestone 10 (M10) Internationalisation & Static Export State
  currentLang: 'en',
  i18nDict: {},
  isStaticMode: false
};
window.state = state;

// =====================================================================
// Milestone M10: Internationalisation (i18n) Engine
// =====================================================================
const i18nDictionaries = {
  en: null,
  bn: null
};

async function loadLocaleDictionary(lang) {
  if (i18nDictionaries[lang]) return i18nDictionaries[lang];
  try {
    const res = await fetch(`i18n/${lang}.json`);
    if (res.ok) {
      i18nDictionaries[lang] = await res.json();
      return i18nDictionaries[lang];
    }
  } catch (err) {
    console.warn(`Could not load i18n dictionary for ${lang}:`, err);
  }
  return null;
}

function getNestedTranslation(dict, keyPath) {
  if (!dict || !keyPath) return null;
  const parts = keyPath.split('.');
  let curr = dict;
  for (const part of parts) {
    if (curr && typeof curr === 'object' && part in curr) {
      curr = curr[part];
    } else {
      return null;
    }
  }
  return typeof curr === 'string' ? curr : null;
}

window.setLanguage = async function(lang) {
  const dict = await loadLocaleDictionary(lang);
  if (!dict) return;
  state.currentLang = lang;
  state.i18nDict = dict;

  // 1. Update Switcher Button Text
  const langLabel = document.getElementById('langSwitchLabel');
  if (langLabel) {
    langLabel.textContent = lang === 'en' ? 'বাংলা' : 'English';
  }

  // 2. Update all DOM elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = getNestedTranslation(dict, key);
    if (text !== null) {
      el.textContent = text;
    }
  });

  // 3. Update titles/tooltips with data-i18n-title
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    const text = getNestedTranslation(dict, key);
    if (text !== null) {
      el.setAttribute('title', text);
    }
  });

  // 4. Update HTML document lang attribute
  document.documentElement.lang = lang;
  console.log(`AquaPredict: Language switched to ${lang.toUpperCase()}`);
};

async function checkStaticMode() {
  const isUrlStatic = window.location.search.includes('mode=static') || window.AQUAPREDICT_STATIC_MODE === true || window.location.protocol === 'file:';
  let hasManifest = false;
  try {
    const res = await fetch('data/static_export_manifest.json');
    if (res.ok) hasManifest = true;
  } catch (e) {}

  if (isUrlStatic || hasManifest) {
    state.isStaticMode = true;
    const banner = document.getElementById('staticModeBanner');
    if (banner) banner.style.display = 'block';
    console.log("AquaPredict: Running in Precomputed Static Export Mode");
  }
}

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  initMap();
  initBasemaps();
  setupEventListeners();
  checkStaticMode();
  loadLocaleDictionary('en');
  loadLocaleDictionary('bn');
  
  // Load data assets
  await Promise.all([
    loadPilotBoundary(),
    loadDemOverlays(),
    loadDemGrid(),
    loadSusceptibilityOverlays(),
    loadSusceptibilityGrid(),
    loadGisLayers(),
    loadQualityMetrics(),
    loadRainfallData(),
    loadValidationReadiness(),
    loadRescueLocations(),
    loadSimulationScenarios(),
    loadM6DrainageNetwork(),
    loadStreetNetworkAndGraph()
  ]);

  initSimulationUI();
  initM6UI();
  initRescuePriorityUI();

  console.log("AquaPredict initialized successfully with Rescue Priority Predictor.");
});

/**
 * Initialize Leaflet Map
 */
function initMap() {
  state.map = L.map('map', {
    center: [29.7605, -95.3700],
    zoom: 16,
    minZoom: 13,
    maxZoom: 19,
    zoomControl: true,
    attributionControl: false
  });

  // Fit to pilot bounds initially with nice padding
  state.map.fitBounds(PILOT_BOUNDS, { padding: [50, 50] });

  // Dedicated Leaflet pane for DEM raster (zIndex 250: above tilePane at 200, below overlayPane at 400)
  state.map.createPane('demPane');
  state.map.getPane('demPane').style.zIndex = 250;

  // Dedicated Leaflet pane for M1 Susceptibility raster (zIndex 260: above demPane at 250, below overlayPane at 400)
  state.map.createPane('suscPane');
  state.map.getPane('suscPane').style.zIndex = 260;

  // Dedicated Leaflet pane for M4 Dynamic Synthesis overlay (zIndex 270: above suscPane at 260, below overlayPane at 400)
  state.map.createPane('m4Pane');
  state.map.getPane('m4Pane').style.zIndex = 270;

  // Dedicated Leaflet pane for M5 Scenario Simulation flood raster (zIndex 280: above m4Pane at 270, below overlayPane at 400)
  state.map.createPane('floodPane');
  state.map.getPane('floodPane').style.zIndex = 280;

  // Leaflet attribution control removed to prevent overlap with bottom Telemetry HUD

  // Mouse move coordinate and elevation tracking
  state.map.on('mousemove', onMapMouseMove);
  state.map.on('click', onMapClickRouteHandler);
}

/**
 * Initialize Basemaps
 */
function initBasemaps() {
  state.basemaps.dark = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors'
  });

  state.basemaps.positron = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors'
  });

  state.basemaps.satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Esri, Maxar, Earthstar Geographics'
  });

  state.basemaps.osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  });

  // Add default basemap
  state.basemaps[state.currentBasemap].addTo(state.map);
}

/**
 * Load Pilot Boundary Polygon
 */
async function loadPilotBoundary() {
  try {
    const res = await fetch('data/pilot_boundary.geojson');
    const data = await res.json();
    
    state.layers.pilotBoundary = L.geoJSON(data, {
      style: {
        color: '#38bdf8',
        weight: 2,
        dashArray: '6, 6',
        fillColor: '#0284c7',
        fillOpacity: 0.04
      }
    }).addTo(state.map);
  } catch (err) {
    console.error("Failed to load pilot boundary:", err);
  }
}

/**
 * Load DEM Raster Visualizations (Topography Tint and Hillshade)
 */
async function loadDemOverlays() {
  try {
    // 1. Terrain Color Ramp Overlay
    state.layers.demTerrain = L.imageOverlay('data/dem_terrain.png', PILOT_BOUNDS, {
      opacity: state.demOpacity,
      interactive: false,
      pane: 'demPane'
    });

    // 2. 3D Hillshade Overlay
    state.layers.demHillshade = L.imageOverlay('data/dem_hillshade.png', PILOT_BOUNDS, {
      opacity: state.demOpacity,
      interactive: false,
      pane: 'demPane'
    });

    // Add active mode
    if (state.demMode === 'terrain') {
      state.layers.demTerrain.addTo(state.map);
    } else {
      state.layers.demHillshade.addTo(state.map);
    }
  } catch (err) {
    console.error("Failed to load DEM overlays:", err);
  }
}

/**
 * Load Downsampled DEM Grid for Real-time Cursor Elevation Query
 */
async function loadDemGrid() {
  try {
    const res = await fetch('data/dem_grid.json');
    state.demGrid = await res.json();
  } catch (err) {
    console.warn("Could not load DEM elevation grid for hover lookup:", err);
  }
}

/**
 * Load M1 Susceptibility Overlays (Composite, Depressions, Proximity)
 */
async function loadSusceptibilityOverlays() {
  try {
    // 1. Composite Susceptibility (EWSI)
    state.layers.susceptibility = L.imageOverlay('data/susceptibility.png', PILOT_BOUNDS, {
      opacity: state.suscOpacity,
      interactive: false,
      pane: 'suscPane'
    });

    // 2. Ponding Sinks / Topographic Depressions
    state.layers.depressions = L.imageOverlay('data/depressions.png', PILOT_BOUNDS, {
      opacity: state.suscOpacity,
      interactive: false,
      pane: 'suscPane'
    });

    // 3. Inlet Proximity / Metric Distance Rings
    state.layers.inletProximity = L.imageOverlay('data/inlet_proximity.png', PILOT_BOUNDS, {
      opacity: state.suscOpacity,
      interactive: false,
      pane: 'suscPane'
    });

    // Add active susceptibility mode by default
    state.layers.susceptibility.addTo(state.map);
  } catch (err) {
    console.error("Failed to load Susceptibility overlays:", err);
  }
}

/**
 * Load M1 Susceptibility Grid for Real-time Inspector Readout
 */
async function loadSusceptibilityGrid() {
  try {
    const res = await fetch('data/susceptibility_grid.json');
    state.suscGrid = await res.json();
  } catch (err) {
    console.warn("Could not load susceptibility grid:", err);
  }
}

/**
 * Load Vector GIS Layers (Gravity Mains, Inlets, Manholes, Outfalls)
 */
async function loadGisLayers() {
  // 1. Gravity Mains (Drainage Pipes)
  try {
    const resPipes = await fetch('data/gravity_mains.geojson');
    const pipesData = await resPipes.json();
    
    state.layers.gravityMains = L.geoJSON(pipesData, {
      style: (feature) => {
        const width = feature.properties.WIDTH || 18;
        // Size-based line weight: larger trunk mains are rendered thicker
        let weight = 2;
        let color = '#3b82f6';
        if (width >= 36) {
          weight = 4;
          color = '#60a5fa';
        } else if (width >= 24) {
          weight = 3;
          color = '#38bdf8';
        }

        return {
          color: color,
          weight: weight,
          opacity: 0.88,
          lineCap: 'round',
          lineJoin: 'round'
        };
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const id = p.FACILITYID || p.OBJECTID || 'Unknown ID';
        const width = p.WIDTH ? `${p.WIDTH}"` : 'Unspecified';
        const mat = p.MATERIAL || 'Unrecorded';
        
        layer.bindTooltip(`
          <div style="font-weight:600; color:#38bdf8;">Pipe #${id}</div>
          <div>Dia/Width: ${width} · Mat: ${mat}</div>
        `, { className: 'custom-tooltip', sticky: true });

        layer.on({
          mouseover: (e) => {
            const l = e.target;
            l.setStyle({ weight: 5, color: '#f8fafc', opacity: 1 });
            l.bringToFront();
          },
          mouseout: (e) => {
            state.layers.gravityMains.resetStyle(e.target);
          },
          click: () => {
            openInspector('Gravity Main', feature.properties);
          }
        });
      }
    }).addTo(state.map);

    document.getElementById('countGravityMains').textContent = pipesData.features.length;
  } catch (err) {
    console.error("Failed to load Gravity Mains:", err);
  }

  // 2. Storm Inlets
  try {
    const resInlets = await fetch('data/inlets.geojson');
    const inletsData = await resInlets.json();

    state.layers.inlets = L.geoJSON(inletsData, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 4.5,
          fillColor: '#14b8a6',
          color: '#ffffff',
          weight: 1.2,
          opacity: 0.95,
          fillOpacity: 0.88
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const id = p.FACILITYID || p.OBJECTID || 'Unknown ID';
        const rim = p.RIMELEV !== null && p.RIMELEV !== undefined ? `${p.RIMELEV} ft` : 'Unrecorded';
        
        layer.bindTooltip(`
          <div style="font-weight:600; color:#2dd4bf;">Inlet #${id}</div>
          <div>Rim Elev: ${rim}</div>
        `, { className: 'custom-tooltip', sticky: true });

        layer.on({
          mouseover: (e) => {
            e.target.setStyle({ radius: 7, fillColor: '#5eead4', weight: 2 });
          },
          mouseout: (e) => {
            e.target.setStyle({ radius: 4.5, fillColor: '#14b8a6', weight: 1.2 });
          },
          click: () => {
            openInspector('Storm Inlet', feature.properties);
          }
        });
      }
    }).addTo(state.map);

    document.getElementById('countInlets').textContent = inletsData.features.length;
  } catch (err) {
    console.error("Failed to load Inlets:", err);
  }

  // 3. Storm Manholes
  try {
    const resMh = await fetch('data/manholes.geojson');
    const mhData = await resMh.json();

    state.layers.manholes = L.geoJSON(mhData, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 5,
          fillColor: '#a855f7',
          color: '#ffffff',
          weight: 1.2,
          opacity: 0.95,
          fillOpacity: 0.88
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const id = p.FACILITYID || p.OBJECTID || 'Unknown ID';
        const depth = p.DEPTH !== null && p.DEPTH !== undefined ? `${p.DEPTH} ft` : 'Unrecorded';
        
        layer.bindTooltip(`
          <div style="font-weight:600; color:#c084fc;">Manhole #${id}</div>
          <div>Depth: ${depth}</div>
        `, { className: 'custom-tooltip', sticky: true });

        layer.on({
          mouseover: (e) => {
            e.target.setStyle({ radius: 7.5, fillColor: '#d8b4fe', weight: 2 });
          },
          mouseout: (e) => {
            e.target.setStyle({ radius: 5, fillColor: '#a855f7', weight: 1.2 });
          },
          click: () => {
            openInspector('Storm Manhole', feature.properties);
          }
        });
      }
    }).addTo(state.map);

    document.getElementById('countManholes').textContent = mhData.features.length;
  } catch (err) {
    console.error("Failed to load Manholes:", err);
  }

  // 4. Discharge Points (Outfalls)
  try {
    const resDis = await fetch('data/discharge.geojson');
    const disData = await resDis.json();

    state.layers.discharge = L.geoJSON(disData, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 8,
          fillColor: '#f59e0b',
          color: '#ffffff',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.95
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const id = p.FACILITYID || p.OBJECTID || 'Unknown ID';
        const typ = p.DISCHRGTYP || 'Outfall';
        const width = p.WIDTH ? `${p.WIDTH}"` : 'Unspecified';
        
        layer.bindTooltip(`
          <div style="font-weight:700; color:#fbbf24;">Outfall #${id}</div>
          <div>Type: ${typ} · Dia: ${width}</div>
        `, { className: 'custom-tooltip', sticky: true });

        layer.on({
          mouseover: (e) => {
            e.target.setStyle({ radius: 11, fillColor: '#fde047', weight: 3 });
          },
          mouseout: (e) => {
            e.target.setStyle({ radius: 8, fillColor: '#f59e0b', weight: 2 });
          },
          click: () => {
            openInspector('Discharge Outfall', feature.properties);
          }
        });
      }
    }).addTo(state.map);

    document.getElementById('countDischarge').textContent = disData.features.length;
  } catch (err) {
    console.error("Failed to load Discharge Points:", err);
  }
}

/**
 * Handle Map Mouse Move for Live Coordinates and DEM Elevation Lookup
 */
function onMapMouseMove(e) {
  const lat = e.latlng.lat;
  const lng = e.latlng.lng;

  // Update coordinate display
  const coordsElem = document.getElementById('cursorCoordsText');
  if (coordsElem) {
    coordsElem.textContent = `${lat.toFixed(5)}° N, ${lng.toFixed(5)}° W`;
  }

  // Elevation Lookup
  const elevElem = document.getElementById('cursorElevationText');
  if (!elevElem || !state.demGrid) return;

  const b = state.demGrid.bbox;
  if (lng >= b.west && lng <= b.east && lat >= b.south && lat <= b.north) {
    // Map lat/lon to grid indices
    const colPct = (lng - b.west) / (b.east - b.west);
    const rowPct = (b.north - lat) / (b.north - b.south); // row 0 is North

    const col = Math.min(Math.max(Math.floor(colPct * state.demGrid.cols), 0), state.demGrid.cols - 1);
    const row = Math.min(Math.max(Math.floor(rowPct * state.demGrid.rows), 0), state.demGrid.rows - 1);

    const elevMeters = state.demGrid.grid[row][col];
    const elevFeet = (elevMeters * 3.28084).toFixed(1);

    // Geomorphology zone label
    let zoneLabel = "Downtown Terrace";
    if (elevMeters < 3.0) zoneLabel = "Buffalo Bayou Channel";
    else if (elevMeters < 7.0) zoneLabel = "Riparian Floodplain";
    else if (elevMeters > 15.0) zoneLabel = "Urban Elevation Crest";

    elevElem.innerHTML = `<strong>${elevMeters.toFixed(2)} m</strong> (${elevFeet} ft) · <span style="color:#38bdf8;">${zoneLabel}</span>`;

    // M1 Susceptibility Lookup
    const suscElem = document.getElementById('cursorSuscText');
    if (suscElem && state.suscGrid) {
      const sCell = state.suscGrid.grid[row][col];
      const depText = sCell.dep > 0.04 ? `<span style="color:#38bdf8;">${sCell.dep.toFixed(2)}m sink</span>` : 'No sink';
      suscElem.innerHTML = `
        <span class="badge-tier tier-${sCell.tier.toLowerCase()}">${sCell.tier}</span>
        <span style="font-size:0.72rem; color:var(--text-secondary); margin-left:6px;">
          ${depText} · Slope ${sCell.slope}° · Inlet ${sCell.inlet_dist}m
        </span>
      `;
    }

    // Rescue Priority Indicator in Telemetry Bar
    const rescueCursorElem = document.getElementById('cursorRescueText');
    if (rescueCursorElem && state.rescueRiskAssessments) {
      const atRiskCount = state.rescueRiskAssessments.filter(a => a.isCriticalRisk).length;
      if (atRiskCount > 0) {
        rescueCursorElem.innerHTML = `<span class="badge-tier" style="background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3);">${atRiskCount} Critical</span>`;
      } else {
        rescueCursorElem.innerHTML = `<span class="badge-tier" style="background:rgba(16,185,129,0.15); color:#059669; border:1px solid rgba(16,185,129,0.3);">Safe</span>`;
      }
    }

    // M5 Scenario Simulation Depth Lookup
    const simCursorElem = document.getElementById('cursorSimDepthText');
    if (simCursorElem) {
      if (!state.simLayerEnabled) {
        simCursorElem.innerHTML = `<span class="badge-tier tier-inactive">Simulation Layer Off</span>`;
      } else if (state.simScenarios) {
        const scenario = state.simScenarios.presets['preset_' + state.simActivePreset + 'mm'];
        if (scenario) {
          const ts = scenario.timesteps[state.simActiveStepIdx];
          const flatIdx = row * 100 + col;
          let cellDepth = 0.0;
          if (ts && ts.sparse_depths) {
            const found = ts.sparse_depths.find(p => p[0] === flatIdx);
            if (found) cellDepth = found[1];
          }
          if (cellDepth > 0.0) {
            let clsName = 'Shallow';
            let color = '#93c5fd';
            if (cellDepth > 0.50) { clsName = 'Very Deep'; color = '#c7d2fe'; }
            else if (cellDepth > 0.20) { clsName = 'Deep'; color = '#60a5fa'; }
            else if (cellDepth > 0.05) { clsName = 'Moderate'; color = '#38bdf8'; }
            simCursorElem.innerHTML = `
              <strong style="color:${color};">${cellDepth.toFixed(2)} m</strong>
              <span style="font-size:0.72rem; color:var(--text-secondary); margin-left:6px;">(${clsName})</span>
            `;
          } else {
            simCursorElem.innerHTML = `<span style="color:#94a3b8; font-size:0.75rem;">Dry (0.00 m)</span>`;
          }
        }
      }
    }
  } else {
    elevElem.textContent = "Outside pilot boundary";
    const suscElem = document.getElementById('cursorSuscText');
    if (suscElem) {
      suscElem.innerHTML = `<span class="badge-tier tier-unavailable">Unavailable (Outside Pilot)</span>`;
    }
    const rescueCursorElem = document.getElementById('cursorRescueText');
    if (rescueCursorElem) {
      rescueCursorElem.innerHTML = `<span class="badge-tier" style="color:#94a3b8;">Outside Pilot</span>`;
    }
    const simCursorElem = document.getElementById('cursorSimDepthText');
    if (simCursorElem) {
      simCursorElem.innerHTML = `<span class="badge-tier tier-unavailable">Outside Pilot Bounds</span>`;
    }
  }
}

/**
 * Load Quality Metrics from JSON
 */
async function loadQualityMetrics() {
  try {
    const res = await fetch('data/quality_metrics.json');
    state.qualityData = await res.json();
    renderCompletenessTab();
  } catch (err) {
    console.warn("Could not load quality metrics:", err);
  }
}

/**
 * Render Completeness Tab inside Data Quality Panel
 */
function renderCompletenessTab() {
  const container = document.getElementById('completenessGridContainer');
  if (!container || !state.qualityData) return;

  const datasets = state.qualityData.datasets;
  let html = '';

  const layerKeys = [
    { key: 'gravity_mains', title: 'Gravity Mains', total: 624 },
    { key: 'inlets', title: 'Storm Inlets', total: 265 },
    { key: 'manholes', title: 'Manholes', total: 283 },
    { key: 'discharge', title: 'Discharge / Outfalls', total: 4 }
  ];

  layerKeys.forEach(l => {
    const ds = datasets[l.key];
    if (!ds || !ds.metrics) return;

    // Filter to the most hydraulically significant fields
    const keyFields = ['WIDTH', 'HEIGHT', 'MATERIAL', 'DOWNELEV', 'UPELEV', 'SLOPE', 'RIMELEV', 'INVERTELEV', 'DEPTH', 'INLETMAT', 'FLOWELEV', 'DISCHRGTYP'];
    const filteredMetrics = ds.metrics.filter(m => keyFields.includes(m.field));

    html += `
      <div class="comp-card">
        <div class="comp-card-header">
          <span class="comp-card-title">${l.title}</span>
          <span class="comp-stat-badge">${l.total} Total Features</span>
        </div>
        <div class="comp-metrics-list">
    `;

    filteredMetrics.forEach(m => {
      const pct = m.completeness_pct;
      let levelClass = 'high';
      if (pct < 40) levelClass = 'low';
      else if (pct < 80) levelClass = 'medium';

      html += `
        <div class="comp-metric-row">
          <div class="comp-label-row">
            <span class="comp-field-name">${m.field}</span>
            <span class="comp-pct-val ${levelClass}">${pct}% (${(100 - pct).toFixed(1)}% blank)</span>
          </div>
          <div class="comp-progress-bar">
            <div class="comp-fill ${levelClass}" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

/**
 * Open Inspector Card for clicked GIS Asset
 */
function openInspector(layerType, props) {
  const card = document.getElementById('assetInspectorCard');
  const pill = document.getElementById('inspLayerPill');
  const title = document.getElementById('inspAssetId');
  const body = document.getElementById('inspBody');
  const traceActions = document.getElementById('inspectorTraceActions');

  if (!card || !body) return;

  const id = String(props.FACILITYID || props.OBJECTID || 'N/A');
  state.activeInspectorAsset = { layerType, props, id };
  pill.textContent = layerType;
  title.textContent = `FACILITY #${id}`;

  let m6Html = '';

  // Check if asset is part of M6 Drainage Network
  const isDrainageAsset = ['Gravity Main', 'Storm Inlet', 'Storm Manhole', 'Discharge Outfall'].includes(layerType);
  if (traceActions) {
    traceActions.style.display = isDrainageAsset ? 'flex' : 'none';
  }

  if (state.m6Data) {
    if (layerType === 'Gravity Main') {
      const c = state.m6Data.conduits
        ? (state.m6Data.conduits[id] || Object.values(state.m6Data.conduits).find(x => String(x.objectid) === id || String(x.ufid) === id))
        : null;
      if (c) {
        let connPillClass = 'm6-pill-confirmed';
        let connLabel = 'Source Confirmed';
        if (c.connectivity_type === 'source_partial_snapped') {
          connPillClass = 'm6-pill-snapped';
          connLabel = 'Single-End Snapped (≤1.0m)';
        } else if (c.connectivity_type === 'inferred_snapped') {
          connPillClass = 'm6-pill-snapped';
          connLabel = 'Dual-End Snapped (≤1.0m)';
        } else if (c.connectivity_type === 'dangling_boundary') {
          connPillClass = 'm6-pill-dangling';
          connLabel = 'Dangling Boundary Trunk';
        }

        const isCalculable = c.capacity_status && c.capacity_status.startsWith('CALCULAT');
        let capStatusPill = `<span class="m6-pill m6-pill-unavailable">UNAVAILABLE</span>`;
        if (c.capacity_status === 'CALCULATED') {
          capStatusPill = `<span class="m6-pill m6-pill-calculable">CALCULATED</span>`;
        } else if (c.capacity_status === 'CALCULATED_WITH_ASSUMED_N') {
          capStatusPill = `<span class="m6-pill m6-pill-snapped" title="Roughness assumed n=0.013 for unrecorded material">ESTIMATED (ASSUMED n)</span>`;
        }

        const capValueText = isCalculable && c.capacity_cfs !== null
          ? `<strong>${c.capacity_cfs.toFixed(2)} cfs</strong> (${c.capacity_m3s.toFixed(3)} m³/s)`
          : `<span style="color:#f87171; font-size:0.72rem;">${c.capacity_reason || 'Missing slope/diameter'}</span>`;

        const outfallText = c.reaches_bayou_outfall
          ? `<span style="color:#34d399; font-weight:600;">✓ Reaches Bayou Outfall #${c.target_outfall_id}</span>`
          : `<span style="color:#a855f7;">✗ Boundary Trunk / Disconnected (Unresolved Mapped Connectivity)</span>`;

        // Check active simulation loading state
        let loadingStateHtml = '';
        if (state.simScenarios) {
          const pKey = 'preset_' + state.simActivePreset + 'mm';
          const simStep = state.m6Data.dynamic_simulation_loading?.[pKey]?.timesteps?.[state.simActiveStepIdx];
          if (simStep) {
            let loadState = 'NORMAL';
            let loadColor = '#38bdf8';
            if (c.connectivity_type === 'dangling_boundary' && !c.reaches_bayou_outfall) {
              loadState = 'DISCONNECTED (Unresolved Mapped Connectivity)';
              loadColor = '#a855f7';
            } else if (!isCalculable || c.capacity_m3s === null || c.capacity_m3s === undefined || c.capacity_m3s <= 0) {
              loadState = 'INSUFFICIENT_DATA';
              loadColor = '#64748b';
            } else {
              const qCond = (c.contributing_inlet_fraction !== undefined ? c.contributing_inlet_fraction : 0.0) * simStep.inflow_rate_per_inlet_m3s;
              const ratio = qCond / c.capacity_m3s;
              if (ratio > 1.0) {
                loadState = 'CAPACITY_EXCEEDED';
                loadColor = '#ef4444';
              } else if (ratio >= 0.70) {
                loadState = 'HIGH_LOADING';
                loadColor = '#fbbf24';
              } else {
                loadState = 'NORMAL';
                loadColor = '#38bdf8';
              }
            }
            loadingStateHtml = `
              <div class="attr-row">
                <span class="attr-name">Sim Loading State:</span>
                <span class="attr-val" style="color:${loadColor}; font-weight:700;">${loadState}</span>
              </div>
            `;
          }
        }

        m6Html = `
          <div class="inspector-m6-block">
            <div class="inspector-m6-header">
              <span>M6 Hydraulic Capacity & Topology</span>
              ${capStatusPill}
            </div>
            <div class="attr-row">
              <span class="attr-name">Topology Class:</span>
              <span class="attr-val"><span class="m6-pill ${connPillClass}">${connLabel}</span></span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Upstream Node:</span>
              <span class="attr-val">${c.from_node ? '#' + c.from_node : 'Dangling / Boundary'}</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Downstream Node:</span>
              <span class="attr-val">${c.to_node ? '#' + c.to_node : 'Dangling / Boundary'}</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Pipe Slope:</span>
              <span class="attr-val">${c.slope_pct !== null ? c.slope_pct.toFixed(2) + '%' : 'Unrecorded'} (${c.slope_source || 'missing'})</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Full Pipe Capacity:</span>
              <span class="attr-val">${capValueText}</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Bayou Reachability:</span>
              <span class="attr-val">${outfallText}</span>
            </div>
            ${loadingStateHtml}
          </div>
        `;
      }
    } else if (['Storm Inlet', 'Storm Manhole', 'Discharge Outfall'].includes(layerType)) {
      const node = state.m6Data.nodes
        ? (state.m6Data.nodes[id] || Object.values(state.m6Data.nodes).find(x => String(x.objectid) === id))
        : null;
      if (node) {
        const outfallText = node.reaches_bayou_outfall
          ? `<span style="color:#34d399; font-weight:600;">✓ Traces to Outfall #${node.target_outfall_id} (${node.dist_to_outfall_m}m)</span>`
          : `<span style="color:#a855f7;">✗ Not Connected to Bayou</span>`;

        m6Html = `
          <div class="inspector-m6-block">
            <div class="inspector-m6-header">
              <span>M6 Topological Node Status</span>
              <span class="m6-pill m6-pill-confirmed">${node.node_type.toUpperCase()}</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Incoming Conduits:</span>
              <span class="attr-val">${node.incoming_conduits.length} pipes</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Outgoing Conduits:</span>
              <span class="attr-val">${node.outgoing_conduits.length} pipes</span>
            </div>
            <div class="attr-row">
              <span class="attr-name">Bayou Outfall Status:</span>
              <span class="attr-val">${outfallText}</span>
            </div>
          </div>
        `;
      }
    }
  }

  let rowsHtml = '';
  const displayKeys = Object.keys(props).filter(k => !k.startsWith('_') && k !== 'GlobalID' && k !== 'UFID' && k !== 'created_user' && k !== 'last_edited_user');

  displayKeys.forEach(k => {
    let val = props[k];
    let isMissing = val === null || val === undefined || val === '' || val === ' ';
    let displayVal = isMissing ? 'Unrecorded (null)' : val;
    let cssClass = isMissing ? 'attr-val missing-val' : 'attr-val';

    rowsHtml += `
      <div class="attr-row">
        <span class="attr-name">${k}</span>
        <span class="${cssClass}">${displayVal}</span>
      </div>
    `;
  });

  body.innerHTML = m6Html + rowsHtml;
  card.style.display = 'block';
}

/**
 * Setup Event Listeners
 */
function setupEventListeners() {
  // Milestone M10: Language Switcher Toggle
  const btnLangToggle = document.getElementById('btnLangToggle');
  if (btnLangToggle) {
    btnLangToggle.addEventListener('click', () => {
      const nextLang = state.currentLang === 'en' ? 'bn' : 'en';
      window.setLanguage(nextLang);
    });
  }

  // Milestone M8: 2D / 3D View Mode Switcher
  const tabView2D = document.getElementById('tabView2D');
  const tabView3D = document.getElementById('tabView3D');

  if (tabView2D && tabView3D) {
    tabView2D.addEventListener('click', () => {
      tabView2D.classList.add('active');
      tabView2D.setAttribute('aria-selected', 'true');
      tabView3D.classList.remove('active');
      tabView3D.setAttribute('aria-selected', 'false');
      if (window.viewer3D) window.viewer3D.deactivate();
    });

    tabView3D.addEventListener('click', async () => {
      tabView3D.classList.add('active');
      tabView3D.setAttribute('aria-selected', 'true');
      tabView2D.classList.remove('active');
      tabView2D.setAttribute('aria-selected', 'false');
      if (window.viewer3D) await window.viewer3D.activate();
    });
  }

  // 3D Fallback & Return Buttons
  const btnReturnTo2D = document.getElementById('btnReturnTo2D');
  if (btnReturnTo2D && tabView2D) {
    btnReturnTo2D.addEventListener('click', () => tabView2D.click());
  }

  const btnReturnTo2DFps = document.getElementById('btnReturnTo2DFps');
  if (btnReturnTo2DFps && tabView2D) {
    btnReturnTo2DFps.addEventListener('click', () => tabView2D.click());
  }

  const btnDismissFpsWarn = document.getElementById('btnDismissFpsWarn');
  if (btnDismissFpsWarn) {
    btnDismissFpsWarn.addEventListener('click', () => {
      const card = document.getElementById('fpsWarningCard');
      if (card) card.style.display = 'none';
      if (window.viewer3D) window.viewer3D.fpsWarnDismissed = true;
    });
  }

  // 3D Vertical Exaggeration Slider
  const sliderVert = document.getElementById('sliderVertExaggeration');
  if (sliderVert) {
    sliderVert.addEventListener('input', (e) => {
      if (window.viewer3D) window.viewer3D.setVerticalExaggeration(e.target.value);
    });
  }

  // 3D Reset Camera Button
  const btnResetCamera3D = document.getElementById('btnResetCamera3D');
  if (btnResetCamera3D) {
    btnResetCamera3D.addEventListener('click', () => {
      if (window.viewer3D) window.viewer3D.setDefaultCameraPosition();
    });
  }

  // 3D Overlays Toggles
  const toggle3DTerrainMesh = document.getElementById('toggle3DTerrainMesh');
  if (toggle3DTerrainMesh) {
    toggle3DTerrainMesh.addEventListener('change', (e) => {
      if (window.viewer3D) {
        window.viewer3D.showTerrain = e.target.checked;
        if (window.viewer3D.terrainMesh) window.viewer3D.terrainMesh.visible = e.target.checked;
      }
    });
  }

  const toggle3DFloodSurface = document.getElementById('toggle3DFloodSurface');
  if (toggle3DFloodSurface) {
    toggle3DFloodSurface.addEventListener('change', (e) => {
      if (window.viewer3D) {
        window.viewer3D.showFlood = e.target.checked;
        if (window.viewer3D.floodMesh) window.viewer3D.floodMesh.visible = e.target.checked;
      }
    });
  }

  const toggle3DDrainagePipes = document.getElementById('toggle3DDrainagePipes');
  if (toggle3DDrainagePipes) {
    toggle3DDrainagePipes.addEventListener('change', (e) => {
      if (window.viewer3D) {
        window.viewer3D.showDrainage = e.target.checked;
        if (window.viewer3D.drainageGroup) window.viewer3D.drainageGroup.visible = e.target.checked;
      }
    });
  }

  // Fit Pilot Extent Button
  document.getElementById('btnRecenter').addEventListener('click', () => {
    state.map.fitBounds(PILOT_BOUNDS, { padding: [50, 50], animate: true });
  });

  // Sidebar Toggle Minimize
  const toggleSidebarBtn = document.getElementById('toggleSidebar');
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener('click', () => {
      document.body.classList.toggle('sidebar-collapsed');
      setTimeout(() => state.map.invalidateSize(), 300);
    });
  }

  // Sidebar Open / Restore Button
  const openSidebarBtn = document.getElementById('btnOpenSidebar');
  if (openSidebarBtn) {
    openSidebarBtn.addEventListener('click', () => {
      document.body.classList.remove('sidebar-collapsed');
      setTimeout(() => state.map.invalidateSize(), 300);
    });
  }

  // Bottom Map Telemetry HUD Minimize / Expand Toggle
  const toggleHudBtn = document.getElementById('btnToggleHud');
  if (toggleHudBtn) {
    toggleHudBtn.addEventListener('click', () => {
      const hud = document.getElementById('bottomHud');
      if (hud) hud.classList.toggle('collapsed');
    });
  }

  // Static Mode Banner Dismiss Button
  const closeStaticBannerBtn = document.getElementById('btnCloseStaticBanner');
  if (closeStaticBannerBtn) {
    closeStaticBannerBtn.addEventListener('click', () => {
      const banner = document.getElementById('staticModeBanner');
      if (banner) banner.style.display = 'none';
    });
  }

  // DEM Terrain Visibility Toggle
  document.getElementById('toggleDemTerrain').addEventListener('change', (e) => {
    const checked = e.target.checked;
    const subcontrols = document.getElementById('demSubcontrols');
    if (subcontrols) subcontrols.style.display = checked ? 'flex' : 'none';

    if (checked) {
      if (state.demMode === 'terrain') {
        state.layers.demTerrain.addTo(state.map);
      } else {
        state.layers.demHillshade.addTo(state.map);
      }
    } else {
      if (state.layers.demTerrain) state.map.removeLayer(state.layers.demTerrain);
      if (state.layers.demHillshade) state.map.removeLayer(state.layers.demHillshade);
    }
  });

  // DEM Mode Selector (Topography vs Hillshade)
  const modeBtns = document.querySelectorAll('.dem-mode-selector .mode-btn');
  modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const mode = btn.dataset.mode;
      state.demMode = mode;

      const isChecked = document.getElementById('toggleDemTerrain').checked;
      if (!isChecked) return;

      if (mode === 'terrain') {
        if (state.layers.demHillshade) state.map.removeLayer(state.layers.demHillshade);
        state.layers.demTerrain.addTo(state.map);
        document.getElementById('demLegendBox').style.display = 'flex';
      } else {
        if (state.layers.demTerrain) state.map.removeLayer(state.layers.demTerrain);
        state.layers.demHillshade.addTo(state.map);
        document.getElementById('demLegendBox').style.display = 'none';
      }
    });
  });

  // DEM Opacity Slider
  const opacitySlider = document.getElementById('demOpacitySlider');
  const opacityVal = document.getElementById('demOpacityVal');
  opacitySlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    const alpha = val / 100.0;
    state.demOpacity = alpha;
    opacityVal.textContent = `${val}%`;

    if (state.layers.demTerrain) state.layers.demTerrain.setOpacity(alpha);
    if (state.layers.demHillshade) state.layers.demHillshade.setOpacity(alpha);
  });

  // M1 Susceptibility Visibility Toggle
  const toggleSusc = document.getElementById('toggleSusceptibility');
  if (toggleSusc) {
    toggleSusc.addEventListener('change', (e) => {
      const checked = e.target.checked;
      const subcontrols = document.getElementById('suscSubcontrols');
      if (subcontrols) subcontrols.style.display = checked ? 'flex' : 'none';

      const activeLayerKey = state.suscMode === 'composite' ? 'susceptibility' : (state.suscMode === 'depressions' ? 'depressions' : 'inletProximity');
      
      ['susceptibility', 'depressions', 'inletProximity'].forEach(key => {
        if (state.layers[key] && state.map.hasLayer(state.layers[key])) {
          state.map.removeLayer(state.layers[key]);
        }
      });

      if (checked && state.layers[activeLayerKey]) {
        state.layers[activeLayerKey].addTo(state.map);
      }
    });
  }

  // M1 Susceptibility Mode Selector (Composite, Depressions, Proximity)
  const suscModeBtns = document.querySelectorAll('.susc-mode-selector .mode-btn');
  suscModeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      suscModeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const mode = btn.dataset.mode;
      state.suscMode = mode;

      const isChecked = document.getElementById('toggleSusceptibility')?.checked;
      if (!isChecked) return;

      ['susceptibility', 'depressions', 'inletProximity'].forEach(key => {
        if (state.layers[key] && state.map.hasLayer(state.layers[key])) {
          state.map.removeLayer(state.layers[key]);
        }
      });

      const activeLayerKey = mode === 'composite' ? 'susceptibility' : (mode === 'depressions' ? 'depressions' : 'inletProximity');
      if (state.layers[activeLayerKey]) {
        state.layers[activeLayerKey].addTo(state.map);
      }
    });
  });

  // M1 Susceptibility Opacity Slider
  const suscOpacitySlider = document.getElementById('suscOpacitySlider');
  const suscOpacityVal = document.getElementById('suscOpacityVal');
  if (suscOpacitySlider && suscOpacityVal) {
    suscOpacitySlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      const alpha = val / 100.0;
      state.suscOpacity = alpha;
      suscOpacityVal.textContent = `${val}%`;

      ['susceptibility', 'depressions', 'inletProximity'].forEach(key => {
        if (state.layers[key]) state.layers[key].setOpacity(alpha);
      });
    });
  }

  // GIS Layer Toggles
  const layerToggleMap = [
    { id: 'toggleGravityMains', layerKey: 'gravityMains' },
    { id: 'toggleInlets', layerKey: 'inlets' },
    { id: 'toggleManholes', layerKey: 'manholes' },
    { id: 'toggleDischarge', layerKey: 'discharge' },
    { id: 'togglePilotBoundary', layerKey: 'pilotBoundary' }
  ];

  layerToggleMap.forEach(item => {
    const el = document.getElementById(item.id);
    if (!el) return;
    el.addEventListener('change', (e) => {
      const layer = state.layers[item.layerKey];
      if (!layer) return;
      if (e.target.checked) {
        state.map.addLayer(layer);
      } else {
        state.map.removeLayer(layer);
      }
    });
  });

  // Basemap Selector Buttons
  const basemapBtns = document.querySelectorAll('.basemap-btn');
  basemapBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      basemapBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const selected = btn.dataset.basemap;
      if (state.basemaps[state.currentBasemap]) {
        state.map.removeLayer(state.basemaps[state.currentBasemap]);
      }
      state.currentBasemap = selected;
      state.basemaps[selected].addTo(state.map);
      state.basemaps[selected].bringToBack();
    });
  });

  // Asset Inspector Close
  const closeInspBtn = document.getElementById('closeInspectorBtn');
  if (closeInspBtn) {
    closeInspBtn.addEventListener('click', () => {
      document.getElementById('assetInspectorCard').style.display = 'none';
    });
  }

  // Quality Modal Open / Close
  const modal = document.getElementById('qualityModalBackdrop');
  const openModalBtn = document.getElementById('btnQualityModal');
  const closeModalBtn = document.getElementById('closeQualityModalBtn');
  const dismissModalBtn = document.getElementById('dismissModalBtn');

  const openModal = () => { modal.style.display = 'flex'; };
  const closeModal = () => { modal.style.display = 'none'; };

  if (openModalBtn) openModalBtn.addEventListener('click', openModal);
  if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
  if (dismissModalBtn) dismissModalBtn.addEventListener('click', closeModal);

  // Close modal when clicking on backdrop
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  // Modal Tab Switching
  const tabBtns = document.querySelectorAll('.modal-tabs .tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const targetTab = btn.dataset.tab;
      document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
      });
      document.getElementById(targetTab).classList.add('active');
    });
  });

  // ==========================================
  // Milestone 2 (M2) — Rainfall Panel Events
  // ==========================================
  const rainfallModal = document.getElementById('rainfallModalBackdrop');
  const openRainfallBtn = document.getElementById('btnRainfallModal');
  const openRainfallSidebarBtn = document.getElementById('btnOpenRainfallFromSidebar');
  const closeRainfallBtn = document.getElementById('closeRainfallModalBtn');
  const dismissRainfallBtn = document.getElementById('dismissRainfallModalBtn');

  const openRainfallModal = () => {
    renderRainfallModal();
    if (rainfallModal) rainfallModal.style.display = 'flex';
  };
  const closeRainfallModal = () => {
    if (rainfallModal) rainfallModal.style.display = 'none';
  };

  if (openRainfallBtn) openRainfallBtn.addEventListener('click', openRainfallModal);
  if (openRainfallSidebarBtn) openRainfallSidebarBtn.addEventListener('click', openRainfallModal);
  if (closeRainfallBtn) closeRainfallBtn.addEventListener('click', closeRainfallModal);
  if (dismissRainfallBtn) dismissRainfallBtn.addEventListener('click', closeRainfallModal);

  if (rainfallModal) {
    rainfallModal.addEventListener('click', (e) => {
      if (e.target === rainfallModal) closeRainfallModal();
    });
  }

  // Rainfall Dataset Source Switcher
  const btnSourceLive = document.getElementById('btnSourceLive');
  const btnSourceSample = document.getElementById('btnSourceSample');

  if (btnSourceLive && btnSourceSample) {
    btnSourceLive.addEventListener('click', () => {
      state.rainfallSource = 'live';
      btnSourceLive.classList.add('active');
      btnSourceSample.classList.remove('active');
      const info = document.getElementById('sourceInfoLabel');
      if (info) info.textContent = 'Raw Directory: C:\\AquaPredict_tests\\rainfall\\ (0 files)';
      updateRainfallBadges();
      renderRainfallModal();
      updateM4UI();
    });

    btnSourceSample.addEventListener('click', () => {
      state.rainfallSource = 'sample';
      btnSourceSample.classList.add('active');
      btnSourceLive.classList.remove('active');
      const info = document.getElementById('sourceInfoLabel');
      if (info) info.textContent = 'Exploratory Fixture: HCFWS Station 1600 (Buffalo Bayou @ Milam St)';
      updateRainfallBadges();
      renderRainfallModal();
      updateM4UI();
    });
  }

  // Rainfall Gauge Pin Map Toggle
  const toggleRainfallGauge = document.getElementById('toggleRainfallGauge');
  if (toggleRainfallGauge) {
    toggleRainfallGauge.addEventListener('change', (e) => {
      if (!state.layers.rainfallGauge) return;
      if (e.target.checked) {
        state.map.addLayer(state.layers.rainfallGauge);
      } else {
        state.map.removeLayer(state.layers.rainfallGauge);
      }
    });
  }

  // ==========================================
  // Milestone 3 (M3) — Validation Readiness Events
  // ==========================================
  const valModal = document.getElementById('validationModalBackdrop');
  const openValBtn = document.getElementById('btnValidationModal');
  const closeValBtn = document.getElementById('closeValidationModalBtn');
  const dismissValBtn = document.getElementById('dismissValidationModalBtn');

  const openValidationModal = () => {
    renderValidationModal();
    if (valModal) valModal.style.display = 'flex';
  };
  const closeValidationModal = () => {
    if (valModal) valModal.style.display = 'none';
  };

  if (openValBtn) openValBtn.addEventListener('click', openValidationModal);
  if (closeValBtn) closeValBtn.addEventListener('click', closeValidationModal);
  if (dismissValBtn) dismissValBtn.addEventListener('click', closeValidationModal);

  if (valModal) {
    valModal.addEventListener('click', (e) => {
      if (e.target === valModal) closeValidationModal();
    });
  }

  // ==========================================
  // Rescue Priority Predictor Controls
  // ==========================================
  const toggleRescue = document.getElementById('toggleRescueMarkers');
  if (toggleRescue) {
    toggleRescue.addEventListener('change', (e) => {
      state.rescueShowMarkers = e.target.checked;
      renderRescueMapMarkers();
      renderRescueWaterloggedRoads();
    });
  }

  // ==========================================
  // Milestone 5 (M5) — Scenario Simulation Controls
  // ==========================================
  const toggleSim = document.getElementById('toggleSimulationLayer');
  if (toggleSim) {
    toggleSim.addEventListener('change', (e) => {
      toggleSimulationLayer(e.target.checked);
    });
  }

  const simOpacitySlider = document.getElementById('simOpacitySlider');
  const simOpacityVal = document.getElementById('simOpacityVal');
  if (simOpacitySlider) {
    simOpacitySlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      state.simOpacity = val / 100.0;
      if (simOpacityVal) simOpacityVal.textContent = `${val}%`;
      if (state.layers.simulationOverlay) {
        state.layers.simulationOverlay.setOpacity(state.simOpacity);
      }
    });
  }

  // Milestone M9: Simulation Engine Selector (Original Screening vs ML Surrogate)
  const btnEngineOrig = document.getElementById('btnEngineOriginal');
  if (btnEngineOrig) {
    btnEngineOrig.addEventListener('click', () => setSimulationEngine('original'));
  }
  const btnEngineSurr = document.getElementById('btnEngineSurrogate');
  if (btnEngineSurr) {
    btnEngineSurr.addEventListener('click', () => setSimulationEngine('surrogate'));
  }

  // Preset Buttons (RAIN-03)
  const presetBtns = document.querySelectorAll('.preset-buttons-grid .preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const val = parseInt(btn.dataset.preset, 10);
      selectSimPreset(val);
    });
  });

  // Timeline Slider (RAIN-07)
  const simSlider = document.getElementById('simTimelineSlider');
  if (simSlider) {
    simSlider.addEventListener('input', (e) => {
      onSimTimelineChange(e.target.value);
    });
  }

  // Lifecycle Playback Buttons (RAIN-04)
  const btnSimRun = document.getElementById('btnSimRun');
  if (btnSimRun) btnSimRun.addEventListener('click', startSimulation);

  const btnSimPause = document.getElementById('btnSimPause');
  if (btnSimPause) btnSimPause.addEventListener('click', pauseSimulation);

  const btnSimReset = document.getElementById('btnSimReset');
  if (btnSimReset) btnSimReset.addEventListener('click', resetSimulation);

  const btnSimPeak = document.getElementById('btnSimPeak');
  if (btnSimPeak) btnSimPeak.addEventListener('click', jumpToSimPeak);

  // Workflow Drawer Toggles (RAIN-05)
  const btnToggleDrawer = document.getElementById('btnToggleWorkflowDrawer');
  if (btnToggleDrawer) btnToggleDrawer.addEventListener('click', toggleWorkflowDrawer);

  const btnCloseDrawer = document.getElementById('btnCloseWorkflowDrawer');
  if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeWorkflowDrawer);

  // ==========================================
  // Milestone 6 (M6) — Drainage Network Events
  // ==========================================
  const drainModal = document.getElementById('drainageModalBackdrop');
  const openDrainBtn = document.getElementById('btnDrainageModal');
  const openDrainSidebarBtn = document.getElementById('btnOpenDrainageModalFromSidebar');
  const closeDrainBtn = document.getElementById('closeDrainageModalBtn');
  const dismissDrainBtn = document.getElementById('dismissDrainageModalBtn');

  const openDrainModal = () => {
    if (drainModal) drainModal.style.display = 'flex';
  };
  const closeDrainModal = () => {
    if (drainModal) drainModal.style.display = 'none';
  };

  if (openDrainBtn) openDrainBtn.addEventListener('click', openDrainModal);
  if (openDrainSidebarBtn) openDrainSidebarBtn.addEventListener('click', openDrainModal);
  if (closeDrainBtn) closeDrainBtn.addEventListener('click', closeDrainModal);
  if (dismissDrainBtn) dismissDrainBtn.addEventListener('click', closeDrainModal);

  if (drainModal) {
    drainModal.addEventListener('click', (e) => {
      if (e.target === drainModal) closeDrainModal();
    });
  }

  // Drainage Modal Tabs
  const drainTabBtns = document.querySelectorAll('#drainageModalTabs .tab-btn');
  drainTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      drainTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.draintab;
      document.querySelectorAll('.drain-tab-panel').forEach(p => p.classList.remove('active'));
      const activePanel = document.getElementById(target);
      if (activePanel) activePanel.classList.add('active');
    });
  });

  // Tracing Buttons in Inspector Card
  const btnTraceUp = document.getElementById('btnTraceUpstream');
  if (btnTraceUp) {
    btnTraceUp.addEventListener('click', () => {
      if (state.activeInspectorAsset) {
        traceUpstream(state.activeInspectorAsset.id);
      }
    });
  }

  const btnTraceDown = document.getElementById('btnTraceDownstream');
  if (btnTraceDown) {
    btnTraceDown.addEventListener('click', () => {
      if (state.activeInspectorAsset) {
        traceDownstream(state.activeInspectorAsset.id);
      }
    });
  }

  const btnClearTraceInsp = document.getElementById('btnClearTraceInsp');
  if (btnClearTraceInsp) {
    btnClearTraceInsp.addEventListener('click', clearTrace);
  }

  const btnClearTraceSidebar = document.getElementById('btnClearTraceSidebar');
  if (btnClearTraceSidebar) {
    btnClearTraceSidebar.addEventListener('click', clearTrace);
  }

  // Dynamic Drainage Loading Map Toggle
  const toggleLoading = document.getElementById('toggleDrainageLoadingMode');
  if (toggleLoading) {
    toggleLoading.addEventListener('change', (e) => {
      toggleDrainageLoadingMode(e.target.checked);
    });
  }

  // ==========================================
  // Milestone 7 (M7) — Safest Route Planner Events
  // ==========================================
  setupRoutePlannerEventListeners();
}

/**
 * ==========================================================================
 * Milestone 2 (M2) — Rainfall Data Ingestion & Visualization Implementation
 * ==========================================================================
 */

/**
 * Load Rainfall JSON assets (Live empty series, Live metadata, and Sample 1600 fixture)
 */
async function loadRainfallData() {
  try {
    // 1. Load Live Series
    const resLive = await fetch('data/rainfall_series.json');
    state.rainfallLive = await resLive.json();
  } catch (err) {
    console.warn("Could not load live rainfall_series.json:", err);
  }

  try {
    // 2. Load Live Metadata
    const resMeta = await fetch('data/rainfall_meta.json');
    state.rainfallMeta = await resMeta.json();
  } catch (err) {
    console.warn("Could not load rainfall_meta.json:", err);
  }

  try {
    // 3. Load Exploratory Sample Fixture (Station 1600)
    const resSample = await fetch('data/rainfall_sample_1600.json');
    state.rainfallSample = await resSample.json();
  } catch (err) {
    console.warn("Could not load rainfall_sample_1600.json:", err);
  }

  updateRainfallBadges();
  initRainfallGaugeMarker();
}

/**
 * Synchronize UI badges with active rainfall dataset status
 */
function updateRainfallBadges() {
  const data = state.rainfallSource === 'live' ? state.rainfallLive : state.rainfallSample;
  const status = data ? data.status : 'UNAVAILABLE';

  const badgeClassMap = {
    'UNAVAILABLE': 'pill-unavailable',
    'UNVERIFIED': 'pill-unverified',
    'VERIFIED': 'pill-verified',
    'INVALID': 'pill-invalid'
  };
  const cls = badgeClassMap[status] || 'pill-unavailable';

  // Header badge
  const headerBadge = document.getElementById('headerRainfallBadge');
  if (headerBadge) {
    headerBadge.className = `badge-status-pill ${cls}`;
    headerBadge.textContent = status;
  }

  // Sidebar status pill
  const sidebarPill = document.getElementById('sidebarRainfallStatusPill');
  if (sidebarPill) {
    sidebarPill.className = `status-m2-pill ${cls}`;
    sidebarPill.textContent = status;
  }

  // Sidebar quick card
  const quickCardStatus = document.getElementById('quickCardStatus');
  if (quickCardStatus) {
    quickCardStatus.textContent = status;
    quickCardStatus.style.color = status === 'UNAVAILABLE' ? '#94a3b8' : (status === 'UNVERIFIED' ? '#fbbf24' : '#34d49a');
  }

  // Sidebar station badge
  const sidebarGaugeBadge = document.getElementById('sidebarGaugeBadge');
  if (sidebarGaugeBadge) {
    sidebarGaugeBadge.textContent = (data && data.station_id) ? `Station ${data.station_id}` : 'HCFWS 1600';
  }

  // Modal header badge
  const modalBadge = document.getElementById('rainfallModalBadge');
  if (modalBadge) {
    modalBadge.className = `badge-status-pill ${cls}`;
    modalBadge.textContent = status;
  }
}

/**
 * Initialize Leaflet Gauge Marker pin on map (HCFWS Station 1600: [29.7642, -95.3653])
 */
function initRainfallGaugeMarker() {
  const coords = [29.7642, -95.3653]; // Buffalo Bayou at Milam St

  const gaugeIcon = L.divIcon({
    className: 'custom-gauge-pin-wrapper',
    html: `
      <div class="leaflet-gauge-marker" id="mapGaugeMarkerPin" title="HCFWS Station 1600 · Buffalo Bayou at Milam St">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path>
        </svg>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });

  const marker = L.marker(coords, { icon: gaugeIcon });

  marker.bindTooltip(`
    <div style="font-weight:700; color:#38bdf8;">HCFWS Station 1600</div>
    <div style="font-size:0.75rem; color:#f8fafc;">Buffalo Bayou @ Milam St</div>
    <div style="font-size:0.7rem; color:#94a3b8;">Click to open Hyetograph & Observations</div>
  `, { className: 'custom-tooltip', sticky: true });

  marker.on('click', () => {
    const modal = document.getElementById('rainfallModalBackdrop');
    renderRainfallModal();
    if (modal) modal.style.display = 'flex';
  });

  state.layers.rainfallGauge = marker;

  // Add to map by default if checkbox is checked
  const toggle = document.getElementById('toggleRainfallGauge');
  if (toggle && toggle.checked) {
    marker.addTo(state.map);
  }
}

/**
 * Render Content inside Rainfall Modal based on active dataset state
 */
function renderRainfallModal() {
  const body = document.getElementById('rainfallModalBody');
  if (!body) return;

  const data = state.rainfallSource === 'live' ? state.rainfallLive : state.rainfallSample;

  if (!data || data.status === 'UNAVAILABLE') {
    // ----------------------------------------------------
    // STATE 1: UNAVAILABLE (Clean, Informative Empty State)
    // ----------------------------------------------------
    body.innerHTML = `
      <div class="rainfall-empty-card">
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" stroke-width="2" fill="none">
            <path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25"></path>
            <line x1="2" y1="2" x2="22" y2="22"></line>
          </svg>
        </div>
        <div class="empty-state-title">No Usable Rainfall Gauge Records Found</div>
        <p class="empty-state-desc">
          The raw gauge directory <code>C:\\AquaPredict_tests\\rainfall\\</code> currently contains <strong>0 observation files</strong>.
          The pipeline state is set to <strong>UNAVAILABLE</strong>. In strict adherence to scientific guardrails,
          AquaPredict does <strong>NOT</strong> invent synthetic rain observations or fill missing periods with fabricated values.
        </p>

        <div class="empty-state-specs">
          <div class="spec-box">
            <div class="spec-box-title">Expected Gauge Station</div>
            <div class="spec-box-content">
              <strong>HCFWS Station 1600</strong> · Buffalo Bayou at Milam St<br>
              <span style="font-family:var(--font-mono); font-size:0.72rem; color:var(--text-muted);">29.7642° N, -95.3653° W (NE Pilot Corner)</span>
            </div>
          </div>

          <div class="spec-box">
            <div class="spec-box-title">Supported File Formats</div>
            <div class="spec-box-content">
              Excel (<code>.xls</code>, <code>.xlsx</code>), CSV (<code>.csv</code>), JSON (<code>.json</code>)
            </div>
          </div>

          <div class="spec-box">
            <div class="spec-box-title">Required Columns</div>
            <div class="spec-box-content">
              <code>Reading Date From</code>, <code>Reading Date To</code>, <code>Rain</code> (inches)
            </div>
          </div>

          <div class="spec-box">
            <div class="spec-box-title">Automated QA Pipeline</div>
            <div class="spec-box-content">
              Reusable script: <code>scripts/ingest_rainfall.py</code> validates intervals, spikes, and missing values.
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 10px;">
          <div class="empty-codebox">
            <span style="color:var(--text-muted);">$</span> python scripts/ingest_rainfall.py
          </div>
          <button class="source-tab-btn active" id="btnPreviewInsideEmpty" style="padding: 8px 16px;">
            <span>Preview Exploratory Test Fixture (Station 1600) &rarr;</span>
          </button>
        </div>

        <div class="limitation-box" style="max-width: 720px; width: 100%; text-align: left; margin-top: 12px;">
          <strong>Integration Guardrail:</strong> Waterlogging Susceptibility (M1) remains purely terrain- and inlet-driven. Unverified rainfall data is never coupled into hydraulic model inputs without verified calibration.
        </div>
      </div>
    `;

    // Hook up internal preview button
    const btnPreview = document.getElementById('btnPreviewInsideEmpty');
    if (btnPreview) {
      btnPreview.addEventListener('click', () => {
        const btnSample = document.getElementById('btnSourceSample');
        if (btnSample) btnSample.click();
      });
    }
    return;
  }

  if (data.status === 'INVALID') {
    body.innerHTML = `
      <div class="rainfall-empty-card" style="border-color: rgba(244,63,94,0.4);">
        <div class="empty-state-icon" style="background: rgba(244,63,94,0.15); color: #f43f5e; border-color: rgba(244,63,94,0.4);">
          <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" stroke-width="2" fill="none">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
        </div>
        <div class="empty-state-title" style="color:#fb7185;">Rainfall Dataset Rejected (INVALID)</div>
        <p class="empty-state-desc">${data.disclaimer || 'Data failed quality validation checks. Verify schema and numeric ranges.'}</p>
      </div>
    `;
    return;
  }

  // ----------------------------------------------------
  // STATE 2: ACTIVE OBSERVATIONS (UNVERIFIED / VERIFIED)
  // ----------------------------------------------------
  const m = data.metrics || {};
  const isDaily = data.temporal_resolution === 'daily';

  body.innerHTML = `
    <!-- Top Metadata Card -->
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
      <div>
        <h3 style="font-family: var(--font-heading); font-size: 1.15rem; color: #ffffff; display: flex; align-items: center; gap: 8px;">
          <span>${data.station_name || 'Station 1600'}</span>
          <span class="badge-status-pill pill-unverified">${data.status}</span>
        </h3>
        <p style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px;">
          ${data.source_organization || 'Harris County Flood Warning System'} · 
          <strong>Resolution:</strong> ${data.temporal_resolution} · 
          <strong>Time Zone:</strong> ${data.time_zone || 'US/Central (CDT)'}
        </p>
      </div>

      <div style="text-align: right;">
        <span style="font-size: 0.72rem; color: var(--text-muted);">Observation Window:</span>
        <div style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--hydro-cyan);">
          ${data.period.start || 'N/A'} &rarr; ${data.period.end || 'N/A'}
        </div>
      </div>
    </div>

    <!-- 4-Card Metrics Grid -->
    <div class="rainfall-metrics-grid">
      <div class="rain-metric-card">
        <span class="rain-metric-label">Cumulative Rainfall</span>
        <div class="rain-metric-val">${m.cumulative_in !== undefined ? m.cumulative_in.toFixed(2) : '0.00'} <span style="font-size:0.85rem; font-weight:400; color:var(--text-muted);">in</span></div>
        <span class="rain-metric-sub">${m.cumulative_mm !== undefined ? m.cumulative_mm.toFixed(1) : '0.0'} mm</span>
      </div>

      <div class="rain-metric-card">
        <span class="rain-metric-label">Peak Interval Reading</span>
        <div class="rain-metric-val">${m.max_reading_in !== undefined ? m.max_reading_in.toFixed(2) : '0.00'} <span style="font-size:0.85rem; font-weight:400; color:var(--text-muted);">in</span></div>
        <span class="rain-metric-sub">~${m.peak_intensity_in_hr !== undefined ? m.peak_intensity_in_hr.toFixed(2) : '0.00'} in/hr rate</span>
      </div>

      <div class="rain-metric-card">
        <span class="rain-metric-label">Interval Resolution</span>
        <div class="rain-metric-val" style="font-size: 1.15rem;">${isDaily ? 'Daily Summary' : (data.median_interval_minutes ? `${data.median_interval_minutes} min` : 'Sub-hourly')}</div>
        <span class="rain-metric-sub">${m.total_records || 0} Total Records</span>
      </div>

      <div class="rain-metric-card">
        <span class="rain-metric-label">Data Quality Audit</span>
        <div class="rain-metric-val" style="font-size: 1.15rem; color:#34d49a;">${m.valid_records || 0} Valid</div>
        <span class="rain-metric-sub" style="color:var(--text-muted);">${m.missing_records || 0} missing · ${m.duplicate_timestamps || 0} dupes</span>
      </div>
    </div>

    <!-- Hyetograph SVG Chart -->
    <div class="hyetograph-card">
      <div class="hyetograph-header">
        <div class="hyetograph-title-group">
          <h4>
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
            <span>Precipitation Hyetograph (${isDaily ? 'Daily Totals' : 'Interval Intensity'})</span>
          </h4>
        </div>
        <div class="hyetograph-units-pill">
          Units: Inches (in) / Millimeters (mm) · Timezone: US/Central
        </div>
      </div>

      <!-- Chart Tooltip -->
      <div class="chart-tooltip" id="hyetographTooltip"></div>

      <!-- SVG Viewport -->
      <div class="svg-chart-viewport" id="chartViewport">
        ${renderHyetographSvg(data.records, isDaily)}
      </div>
    </div>

    <!-- Scientific Disclaimer Banner -->
    <div class="limitation-box" style="margin-top: 14px;">
      <strong>SCIENTIFIC GUARDRAIL & LIMITATION:</strong>
      This time series is tagged as <strong>UNVERIFIED EXPLORATORY DATA</strong>. It has not been reconciled against NOAA Atlas 14 precipitation frequency statistics or radar ground-truth. 
      In accordance with Milestone 2 guardrails, it is <strong>NOT</strong> coupled as dynamic boundary forcing for hydrodynamic or flood model calculations.
    </div>
  `;

  // Attach hover handlers to SVG bars
  attachHyetographInteractions(data.records);
}

/**
 * Generate Responsive SVG Hyetograph Markup
 */
function renderHyetographSvg(records, isDaily) {
  if (!records || records.length === 0) {
    return `<div style="text-align:center; padding:40px; color:var(--text-muted);">No records available to render.</div>`;
  }

  const svgW = 820;
  const svgH = 200;
  const padLeft = 45;
  const padRight = 15;
  const padTop = 15;
  const padBottom = 30;

  const chartW = svgW - padLeft - padRight;
  const chartH = svgH - padTop - padBottom;

  const validVals = records.map(r => (r.rain_in !== null && r.rain_in !== undefined) ? r.rain_in : 0);
  const maxVal = Math.max(0.1, ...validVals);
  const yMax = maxVal * 1.25;

  const n = records.length;
  const barSlotW = chartW / n;
  const barW = Math.max(2, barSlotW * 0.75);

  // Y-axis gridlines (4 steps)
  let gridLines = '';
  for (let s = 0; s <= 4; s++) {
    const val = (yMax * (4 - s) / 4);
    const y = padTop + (chartH * s / 4);
    gridLines += `
      <line x1="${padLeft}" y1="${y}" x2="${svgW - padRight}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />
      <text x="${padLeft - 8}" y="${y + 4}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="end">${val.toFixed(2)}"</text>
    `;
  }

  // Bars
  let bars = '';
  let cumSum = 0;

  records.forEach((rec, idx) => {
    const val = (rec.rain_in !== null && rec.rain_in !== undefined) ? rec.rain_in : 0;
    cumSum += val;
    rec._cumulative = cumSum;

    const h = (val / yMax) * chartH;
    const x = padLeft + idx * barSlotW + (barSlotW - barW) / 2;
    const y = padTop + chartH - h;

    // Intensity color gradient (subtle cyan to deep hydro blue)
    const intensityRatio = Math.min(1.0, val / Math.max(0.01, maxVal));
    const fill = val === 0 ? 'rgba(56, 189, 248, 0.12)' : (intensityRatio > 0.6 ? '#38bdf8' : '#0284c7');

    bars += `
      <rect class="rain-bar" 
            x="${x}" 
            y="${val === 0 ? padTop + chartH - 2 : y}" 
            width="${barW}" 
            height="${val === 0 ? 2 : Math.max(2, h)}" 
            fill="${fill}" 
            rx="1" 
            data-idx="${idx}" />
    `;
  });

  // X-axis time marks (5 marks)
  let xLabels = '';
  const step = Math.max(1, Math.floor(n / 5));
  for (let i = 0; i < n; i += step) {
    const r = records[i];
    const x = padLeft + i * barSlotW + barSlotW / 2;
    // Format label: HH:MM if sub-hourly or MM-DD if daily
    let label = r.timestamp || '';
    if (label.includes(' ')) {
      label = label.split(' ')[1].substring(0, 5);
    }
    xLabels += `
      <text x="${x}" y="${svgH - 8}" fill="#94a3b8" font-size="10" font-family="JetBrains Mono" text-anchor="middle">${label}</text>
    `;
  }

  return `
    <svg viewBox="0 0 ${svgW} ${svgH}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="barGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="100%" stop-color="#0284c7" />
        </linearGradient>
      </defs>
      ${gridLines}
      ${bars}
      ${xLabels}
    </svg>
  `;
}

/**
 * Attach Hover Tooltip Interactions to Hyetograph Bars
 */
function attachHyetographInteractions(records) {
  const chartViewport = document.getElementById('chartViewport');
  const tooltip = document.getElementById('hyetographTooltip');
  if (!chartViewport || !tooltip) return;

  const barElements = chartViewport.querySelectorAll('.rain-bar');
  barElements.forEach(bar => {
    bar.addEventListener('mouseenter', (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const rec = records[idx];
      if (!rec) return;

      const rainIn = (rec.rain_in !== null && rec.rain_in !== undefined) ? rec.rain_in.toFixed(2) : 'Missing';
      const rainMm = (rec.rain_mm !== null && rec.rain_mm !== undefined) ? `${rec.rain_mm.toFixed(1)} mm` : 'N/A';
      const cumIn = rec._cumulative !== undefined ? rec._cumulative.toFixed(2) : '0.00';

      tooltip.innerHTML = `
        <div class="chart-tooltip-time">${rec.timestamp}</div>
        <div class="chart-tooltip-rain">Reading: <strong>${rainIn}"</strong> (${rainMm})</div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Cumulative: ${cumIn}"</div>
        <div style="font-size:0.65rem; color:#64748b;">Quality: ${rec.quality_flag}</div>
      `;
      tooltip.style.display = 'block';
    });

    bar.addEventListener('mousemove', (e) => {
      const rect = chartViewport.getBoundingClientRect();
      const x = e.clientX - rect.left + 12;
      const y = e.clientY - rect.top - 40;
      tooltip.style.left = `${Math.min(x, rect.width - 150)}px`;
      tooltip.style.top = `${Math.max(10, y)}px`;
    });

    bar.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
  });
}

/**
 * ==========================================================================
 * Milestone 3 (M3) — Historical Flood Validation Readiness Implementation
 * ==========================================================================
 */

/**
 * Load M3 Validation Readiness payload from JSON
 */
async function loadValidationReadiness() {
  try {
    const res = await fetch('data/m3_validation_readiness.json');
    state.validationReadiness = await res.json();
    renderValidationModal();
  } catch (err) {
    console.warn("Could not load M3 validation readiness payload:", err);
  }
}

/**
 * Render Candidate Source Inventory Table inside M3 Validation Modal
 */
function renderValidationModal() {
  const tbody = document.getElementById('candidateSourcesTableBody');
  if (!tbody || !state.validationReadiness) return;

  const sources = state.validationReadiness.candidate_sources || [];
  if (sources.length === 0) return;

  let html = '';
  sources.forEach((s, idx) => {
    const isLast = idx === sources.length - 1;
    const borderStyle = isLast ? '' : 'border-bottom: 1px solid var(--border-subtle);';
    const statusBadge = `<span class="badge-status-pill pill-unavailable">DISQUALIFIED</span>`;
    const rationale = s.limitations && s.limitations.length > 0 ? s.limitations[0] : 'Incompatible with pluvial street waterlogging';

    html += `
      <tr style="${borderStyle}">
        <td style="padding: 10px 12px; font-weight: 500; color: var(--text-primary);">${s.name}</td>
        <td style="padding: 10px 12px; color: var(--text-secondary);">${s.provenance}</td>
        <td style="padding: 10px 12px; color: var(--text-secondary);">${s.geographic_coverage}</td>
        <td style="padding: 10px 12px;">${statusBadge}</td>
        <td style="padding: 10px 12px; color: var(--text-muted); font-size: 0.74rem;">${rationale}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

/**
 * ==========================================================================
 * Rescue Priority Predictor Implementation (Replacing M4 Dynamic Synthesis)
 * ==========================================================================
 */

/**
 * Load Rescue Priority Locations Dataset
 */
async function loadRescueLocations() {
  try {
    const res = await fetch('data/rescue_priority_locations.json');
    const data = await res.json();
    state.rescueLocations = data.locations || [];
    console.log(`Loaded ${state.rescueLocations.length} real locations for Rescue Priority Predictor.`);
  } catch (err) {
    console.warn("Could not load rescue_priority_locations.json:", err);
  }
}

/**
 * Initialize Rescue Priority Predictor UI & Map Layers
 */
function initRescuePriorityUI() {
  if (!state.map) return;
  if (!state.rescueWaterloggingLayerGroup) {
    state.rescueWaterloggingLayerGroup = L.layerGroup().addTo(state.map);
  }
  if (!state.rescueHighlightLayerGroup) {
    state.rescueHighlightLayerGroup = L.layerGroup().addTo(state.map);
  }
  if (!state.rescueMarkersLayerGroup) {
    state.rescueMarkersLayerGroup = L.layerGroup().addTo(state.map);
  }

  evaluateRescuePriorities();
}

/**
 * Fast Euclidean distance between two lon/lat points in survey meters
 */
function distanceMeters(lon1, lat1, lon2, lat2) {
  const dx = (lon1 - lon2) * 111320.0 * Math.cos(29.76 * Math.PI / 180.0);
  const dy = (lat1 - lat2) * 110540.0;
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Evaluate Risk Assessment & Rescue Priority for All Available Locations
 * Based on active M5 modeled ponding depth and M7 road network connectivity.
 */
function evaluateRescuePriorities() {
  if (!state.rescueLocations || state.rescueLocations.length === 0) return;

  const presetMm = state.simActivePreset || 50;
  const stepIdx = state.simActiveStepIdx || 0;
  const depthMap = getTimestepDepthMap(presetMm, stepIdx);

  // Update scenario context in UI
  const presetEl = document.getElementById('rescueActivePresetText');
  const stepEl = document.getElementById('rescueActiveStepText');
  if (presetEl) presetEl.textContent = `${presetMm} mm`;
  if (stepEl) stepEl.textContent = `${stepIdx} / ${stepIdx * 5}m`;

  const assessments = [];

  state.rescueLocations.forEach(loc => {
    // 1. Snap to nearest node in street network
    let nearestNode = null;
    let bestDist = Infinity;
    if (state.routingGraph && state.routingGraph.nodes) {
      for (const n of state.routingGraph.nodes) {
        const c = n.coords;
        const d = distanceMeters(c[0], c[1], loc.coords[0], loc.coords[1]);
        if (d < bestDist) {
          bestDist = d;
          nearestNode = n;
        }
      }
    }

    // 2. Identify connecting/access edges
    const accessEdges = [];
    if (nearestNode && state.routingGraph && state.routingGraph.edges) {
      state.routingGraph.edges.forEach(e => {
        if (e.from_node === nearestNode.id || e.to_node === nearestNode.id) {
          accessEdges.push(e);
        } else if (loc.access_roads && loc.access_roads.includes(e.name)) {
          // Corridor road matching
          accessEdges.push(e);
        }
      });
    }

    // 3. Assess depth & impassability across connecting access roads
    let maxConnectingDepth = 0.0;
    let impassableEdgesCount = 0;
    const dataAvailable = (depthMap !== null);
    const floodedEdges = [];

    accessEdges.forEach(e => {
      const assessment = assessEdgeWaterlogging(e, presetMm, stepIdx, 'vehicle');
      if (assessment.maxDepthM > maxConnectingDepth) {
        maxConnectingDepth = assessment.maxDepthM;
      }
      if (assessment.isImpassable || assessment.maxDepthM >= 0.30) {
        impassableEdgesCount++;
      }
      if (assessment.maxDepthM > 0.02) {
        floodedEdges.push({
          edge: e,
          assessment: assessment
        });
      }
    });

    // 4. Determine Risk Category
    let riskReason = null;
    let isCriticalRisk = false;

    if (!dataAvailable) {
      riskReason = 'Assessment Unavailable';
    } else if (accessEdges.length > 0 && impassableEdgesCount === accessEdges.length) {
      riskReason = 'Community Isolation Risk';
      isCriticalRisk = true;
    } else if (impassableEdgesCount > 0) {
      riskReason = 'Road Failure Risk';
      isCriticalRisk = true;
    } else {
      riskReason = 'No Critical Risk Detected';
      isCriticalRisk = false;
    }

    assessments.push({
      ...loc,
      nearestNodeId: nearestNode ? nearestNode.id : null,
      snapDistM: Math.round(bestDist),
      accessEdges: accessEdges,
      floodedEdges: floodedEdges,
      accessEdgesCount: accessEdges.length,
      impassableEdgesCount: impassableEdgesCount,
      maxConnectingDepthM: maxConnectingDepth,
      riskReason: riskReason,
      isCriticalRisk: isCriticalRisk,
      dataAvailable: dataAvailable
    });
  });

  // 5. Rescue Priority Ranking
  // Critical facilities (Hospitals) and Community Isolation receive highest urgency
  const atRisk = assessments.filter(a => a.isCriticalRisk);
  atRisk.sort((a, b) => {
    // Critical facility priority
    if (a.is_critical && !b.is_critical) return -1;
    if (!a.is_critical && b.is_critical) return 1;

    // Isolation Risk higher than Road Failure Risk
    if (a.riskReason === 'Community Isolation Risk' && b.riskReason !== 'Community Isolation Risk') return -1;
    if (a.riskReason !== 'Community Isolation Risk' && b.riskReason === 'Community Isolation Risk') return 1;

    // Max water depth severity
    return b.maxConnectingDepthM - a.maxConnectingDepthM;
  });

  // Assign sequential Priority 1, Priority 2, Priority 3...
  let priorityRank = 1;
  atRisk.forEach(loc => {
    loc.priority = priorityRank++;
  });

  state.rescueRiskAssessments = assessments;

  // 6. Update UI List, Map Markers, and Flooded Access Corridors
  renderRescuePriorityList();
  renderRescueMapMarkers();
  renderRescueWaterloggedRoads();

  // 7. Update Header/Sidebar Badge
  const countBadge = document.getElementById('rescueActiveAlertCountBadge');
  if (countBadge) {
    countBadge.textContent = `${atRisk.length} Critical`;
    countBadge.style.background = atRisk.length > 0 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)';
    countBadge.style.color = atRisk.length > 0 ? '#ef4444' : '#059669';
  }
}

/**
 * Render Categorized Location List in Sidebar
 */
function renderRescuePriorityList() {
  const container = document.getElementById('rescueCategoriesTree');
  if (!container || !state.rescueRiskAssessments) return;

  const categories = [
    { key: 'Hospitals', icon: '🏥' },
    { key: 'Residential Areas', icon: '🏡' },
    { key: 'Societies', icon: '🏛️' },
    { key: 'Villages', icon: '🏘️' },
    { key: 'Communities', icon: '👥' }
  ];

  let html = '';

  categories.forEach(cat => {
    const locs = state.rescueRiskAssessments.filter(a => a.category === cat.key);
    if (locs.length === 0) return;

    const riskCount = locs.filter(a => a.isCriticalRisk).length;

    html += `
      <div class="rescue-cat-group">
        <div class="rescue-cat-header" onclick="toggleRescueCategory(this)" title="Click to collapse/expand ${cat.key}">
          <div class="rescue-cat-header-title">
            <span class="rescue-cat-chevron">▼</span>
            <span>${cat.icon}</span>
            <span>${cat.key}</span>
          </div>
          <span class="rescue-cat-count">${riskCount > 0 ? `<strong style="color:#ef4444;">${riskCount} at risk</strong> / ` : ''}${locs.length} total</span>
        </div>
        <div class="rescue-cat-items">
    `;

    locs.forEach(loc => {
      const isActive = state.activeRescueLocId === loc.id;
      let statusHtml = '';

      if (!loc.dataAvailable) {
        statusHtml = `<span class="risk-unavail-text">— Assessment Unavailable</span>`;
      } else if (loc.isCriticalRisk) {
        const riskClass = loc.riskReason === 'Community Isolation Risk' ? 'risk-tag-isolation' : 'risk-tag-road-failure';
        const floodedCount = loc.floodedEdges ? loc.floodedEdges.length : 0;
        statusHtml = `
          <span class="rescue-danger-dot">🔴</span>
          <span class="${riskClass}">${loc.riskReason}</span>
          <span class="priority-tag-pill">Priority ${loc.priority}</span>
          <span style="font-size:0.67rem; color:#1d4ed8; font-weight:600; margin-left:3px;">
            (${floodedCount} flooded road${floodedCount === 1 ? '' : 's'})
          </span>
        `;
      } else {
        statusHtml = `<span class="risk-safe-text">— No Critical Risk Detected</span>`;
      }

      html += `
        <div class="rescue-loc-card ${loc.isCriticalRisk ? 'has-risk' : 'has-no-risk'} ${isActive ? 'is-active' : ''}" onclick="zoomToRescueLocation('${loc.id}')" title="Click to inspect ${loc.name} and its flooded access roads on the map">
          <div class="rescue-loc-card-header">${loc.name}</div>
          <div class="rescue-loc-card-status">${statusHtml}</div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

/**
 * Toggle Collapse / Expand on Rescue Category
 */
function toggleRescueCategory(headerEl) {
  if (!headerEl || !headerEl.parentElement) return;
  headerEl.parentElement.classList.toggle('is-collapsed');
}
window.toggleRescueCategory = toggleRescueCategory;

/**
 * Render Red Rescue Alert Markers on Map
 */
function renderRescueMapMarkers() {
  if (!state.rescueMarkersLayerGroup) return;
  state.rescueMarkersLayerGroup.clearLayers();

  if (!state.rescueShowMarkers || !state.rescueRiskAssessments) return;

  const atRisk = state.rescueRiskAssessments.filter(a => a.isCriticalRisk);

  atRisk.forEach(loc => {
    const markerHtml = `
      <div class="rescue-pulse-marker" title="${loc.name} (${loc.riskReason} - Priority ${loc.priority})">
        <span>${loc.priority}</span>
      </div>
    `;

    const icon = L.divIcon({
      className: 'custom-rescue-icon',
      html: markerHtml,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
      popupAnchor: [0, -14]
    });

    const marker = L.marker([loc.coords[1], loc.coords[0]], { icon: icon });

    let floodedRoadsList = '';
    if (loc.floodedEdges && loc.floodedEdges.length > 0) {
      floodedRoadsList = loc.floodedEdges.map(item => {
        const e = item.edge;
        const d = item.assessment.maxDepthM;
        const colorLabel = d >= 0.50 || d >= 0.30 ? 'Deep Blue' : d >= 0.20 ? 'Blue' : 'Sky Blue';
        return `<li><strong>${e.name || 'Access Road'}</strong>: ${d.toFixed(2)}m (${colorLabel})</li>`;
      }).join('');
    }

    const popupHtml = `
      <div class="rescue-popup-container">
        <div class="rescue-popup-title">${loc.name}</div>
        <div class="rescue-popup-category">${loc.category} · ${loc.address || 'Houston Pilot Area'}</div>
        <div class="rescue-popup-risk-badge">
          <span>🔴</span>
          <span>${loc.riskReason} — Priority ${loc.priority}</span>
        </div>
        <div style="font-size:0.72rem; color:#475569; margin-top:4px; line-height:1.4;">
          <div>Modeled Access Depth: <strong>${loc.maxConnectingDepthM.toFixed(2)}m</strong></div>
          <div>Impassable Access Roads: <strong>${loc.impassableEdgesCount} of ${loc.accessEdgesCount}</strong></div>
          ${floodedRoadsList ? `
            <div style="margin-top:6px; padding-top:4px; border-top:1px dashed #cbd5e1;">
              <strong style="color:#b91c1c;">Flooded Access Roads:</strong>
              <ul style="margin:2px 0 0; padding-left:14px; color:#1e293b;">
                ${floodedRoadsList}
              </ul>
            </div>
          ` : ''}
          <div style="margin-top:5px; font-size:0.67rem; color:#94a3b8;">Source: ${loc.source}</div>
        </div>
      </div>
    `;

    marker.bindPopup(popupHtml);
    loc._marker = marker;
    state.rescueMarkersLayerGroup.addLayer(marker);
  });
}

/**
 * Render Modeled Waterlogging along Access Roads and Critical Corridors
 * Color mapped strictly to M5 modeled water depth:
 * - High-risk / deeper water (>=0.50m or >=0.30m impassable) -> Deep Blue (#1d4ed8)
 * - Medium-risk waterlogging (0.20m to 0.50m) -> Blue (#2563eb)
 * - Lower-depth waterlogging (0.02m to 0.20m) -> Sky Blue (#60a5fa)
 */
function renderRescueWaterloggedRoads() {
  if (!state.rescueWaterloggingLayerGroup) return;
  state.rescueWaterloggingLayerGroup.clearLayers();
  if (state.rescueHighlightLayerGroup) state.rescueHighlightLayerGroup.clearLayers();

  if (!state.rescueShowMarkers || !state.rescueRiskAssessments) return;

  const presetMm = state.simActivePreset || 50;
  const stepIdx = state.simActiveStepIdx || 0;
  const depthMap = getTimestepDepthMap(presetMm, stepIdx);
  if (!depthMap || !state.routingGraph || !state.routingGraph.edges) return;

  // Map each edge to the rescue locations that rely on it
  const edgeLocationMap = new Map();
  state.rescueRiskAssessments.forEach(loc => {
    if (loc.floodedEdges) {
      loc.floodedEdges.forEach(item => {
        const eid = item.edge.edge_id;
        if (!edgeLocationMap.has(eid)) {
          edgeLocationMap.set(eid, {
            edge: item.edge,
            assessment: item.assessment,
            locations: [loc]
          });
        } else {
          edgeLocationMap.get(eid).locations.push(loc);
        }
      });
    }
  });

  // Also evaluate all other network edges within the pilot area to render visible waterlogging
  state.routingGraph.edges.forEach(e => {
    if (!edgeLocationMap.has(e.edge_id)) {
      const assessment = assessEdgeWaterlogging(e, presetMm, stepIdx, 'vehicle');
      if (assessment.maxDepthM > 0.02) {
        edgeLocationMap.set(e.edge_id, {
          edge: e,
          assessment: assessment,
          locations: []
        });
      }
    }
  });

  let floodedCount = 0;

  edgeLocationMap.forEach(({ edge, assessment, locations }) => {
    const maxD = assessment.maxDepthM;
    if (maxD <= 0.02) return;
    floodedCount++;

    let waterColor, casingColor, weight, casingWeight, depthCategory;
    if (maxD >= 0.50 || assessment.isImpassable || maxD >= 0.30) {
      waterColor = '#1d4ed8'; // Deep Blue
      casingColor = '#1e3a8a';
      weight = 5.5;
      casingWeight = 9.0;
      depthCategory = 'Deep Blue — High Risk (Impassable ≥0.30m)';
    } else if (maxD >= 0.20) {
      waterColor = '#2563eb'; // Blue
      casingColor = '#3b82f6';
      weight = 4.5;
      casingWeight = 7.5;
      depthCategory = 'Blue — Medium-Risk Waterlogging (0.20m–0.50m)';
    } else {
      waterColor = '#60a5fa'; // Sky Blue
      casingColor = '#93c5fd';
      weight = 3.5;
      casingWeight = 6.0;
      depthCategory = 'Sky Blue — Lower-Depth Waterlogging (≤0.20m)';
    }

    const latLngs = edge.coords.map(c => [c[1], c[0]]);

    // Outer glow casing
    const casing = L.polyline(latLngs, {
      color: casingColor,
      weight: casingWeight,
      opacity: 0.35,
      lineCap: 'round',
      lineJoin: 'round',
      interactive: false
    });
    state.rescueWaterloggingLayerGroup.addLayer(casing);

    // Inner water core
    const waterPolyline = L.polyline(latLngs, {
      color: waterColor,
      weight: weight,
      opacity: 0.90,
      lineCap: 'round',
      lineJoin: 'round',
      interactive: true,
      className: 'rescue-water-polyline'
    });

    const isAccessCorridor = locations.length > 0;
    const connectedHtml = isAccessCorridor
      ? `<div style="margin-top:5px; padding-top:4px; border-top:1px dashed #cbd5e1; font-size:0.71rem; color:#1e293b;">
           <strong>Critical Access Corridor for:</strong><br>
           ${locations.map(l => `• <strong>${l.name}</strong> (${l.isCriticalRisk ? 'Priority ' + l.priority : 'Passable'})`).join('<br>')}
         </div>`
      : '';

    waterPolyline.bindTooltip(`
      <div style="font-size:0.76rem; line-height:1.4; max-width:260px;">
        <div style="font-weight:700; color:${waterColor}; font-size:0.82rem;">
          🌊 ${edge.name || 'Road Segment'}
        </div>
        <div style="font-size:0.72rem; color:#475569; margin-top:2px;">
          Modeled Water Depth: <strong>${maxD.toFixed(2)}m</strong> (${depthCategory})
        </div>
        ${connectedHtml}
      </div>
    `, { sticky: true, className: 'custom-tooltip' });

    waterPolyline.on('click', () => {
      if (locations.length > 0) {
        zoomToRescueLocation(locations[0].id);
      }
    });

    state.rescueWaterloggingLayerGroup.addLayer(waterPolyline);
  });

  // Connector lines for off-road/critical facilities to their closest flooded access road
  state.rescueRiskAssessments.filter(a => a.isCriticalRisk).forEach(loc => {
    if (!loc.coords || !loc.floodedEdges || loc.floodedEdges.length === 0) return;
    let closestPt = null;
    let closestDist = Infinity;
    loc.floodedEdges.forEach(({ edge }) => {
      edge.coords.forEach(pt => {
        const d = distanceMeters(loc.coords[0], loc.coords[1], pt[0], pt[1]);
        if (d < closestDist) {
          closestDist = d;
          closestPt = pt;
        }
      });
    });

    if (closestPt && closestDist > 25) {
      const connector = L.polyline([
        [loc.coords[1], loc.coords[0]],
        [closestPt[1], closestPt[0]]
      ], {
        color: '#ef4444',
        weight: 2,
        dashArray: '5, 7',
        opacity: 0.75,
        interactive: false
      });
      state.rescueWaterloggingLayerGroup.addLayer(connector);
    }
  });

  // Update flooded corridors counter badge in sidebar
  const countBadge = document.getElementById('rescueFloodedRoadsCountBadge');
  if (countBadge) {
    countBadge.textContent = `${floodedCount} Flooded Roads`;
  }
}

/**
 * Zoom to and Highlight a Rescue Location and its Flooded Access Roads
 */
function zoomToRescueLocation(locId) {
  if (!state.rescueRiskAssessments) return;
  const loc = state.rescueRiskAssessments.find(a => a.id === locId);
  if (!loc || !state.map) return;

  state.activeRescueLocId = locId;
  renderRescuePriorityList();

  ensure2DMapView();

  if (state.rescueHighlightLayerGroup) {
    state.rescueHighlightLayerGroup.clearLayers();
  }

  const allPoints = [[loc.coords[1], loc.coords[0]]];
  let floodedCorridorsList = '';

  if (loc.floodedEdges && loc.floodedEdges.length > 0) {
    floodedCorridorsList = loc.floodedEdges.map(item => {
      const e = item.edge;
      const d = item.assessment.maxDepthM;
      e.coords.forEach(pt => allPoints.push([pt[1], pt[0]]));

      // Golden glowing highlight casing on the active flooded access road
      if (state.rescueHighlightLayerGroup) {
        const highlightLine = L.polyline(e.coords.map(c => [c[1], c[0]]), {
          color: '#f59e0b',
          weight: 10,
          opacity: 0.85,
          className: 'rescue-active-road-highlight',
          interactive: false
        });
        state.rescueHighlightLayerGroup.addLayer(highlightLine);
      }

      const colorName = d >= 0.50 || d >= 0.30 ? 'Deep Blue' : d >= 0.20 ? 'Blue' : 'Sky Blue';
      return `<li style="margin-top:2px;"><strong>${e.name || 'Access Road'}</strong>: ${d.toFixed(2)}m (${colorName})</li>`;
    }).join('');
  }

  // Frame both the location marker and its flooded access roads
  if (allPoints.length > 1) {
    const bounds = L.latLngBounds(allPoints);
    state.map.fitBounds(bounds.pad(0.35), { animate: true, maxZoom: 17 });
  } else {
    state.map.setView([loc.coords[1], loc.coords[0]], 17, { animate: true });
  }

  const riskBadgeHtml = loc.isCriticalRisk
    ? `<div class="rescue-popup-risk-badge">
         <span>🔴</span>
         <span>${loc.riskReason} — Priority ${loc.priority}</span>
       </div>`
    : `<div style="font-size:0.72rem; color:#059669; font-weight:600; margin-bottom:6px;">
         🟢 No Critical Risk Detected (Passable)
       </div>`;

  const floodedInfoHtml = floodedCorridorsList
    ? `<div style="margin-top:6px; padding-top:4px; border-top:1px dashed #cbd5e1;">
         <strong style="color:#b91c1c;">Flooded Access Roads:</strong>
         <ul style="margin:2px 0 0; padding-left:14px; color:#1e293b;">
           ${floodedCorridorsList}
         </ul>
       </div>`
    : '';

  const popupHtml = `
    <div class="rescue-popup-container">
      <div class="rescue-popup-title">${loc.name}</div>
      <div class="rescue-popup-category">${loc.category} · ${loc.address || 'Houston Pilot Area'}</div>
      ${riskBadgeHtml}
      <div style="font-size:0.72rem; color:#475569; line-height:1.4;">
        <div>Max Modeled Depth: <strong>${loc.maxConnectingDepthM.toFixed(2)}m</strong></div>
        <div>Impassable Access Corridors: <strong>${loc.impassableEdgesCount} of ${loc.accessEdgesCount}</strong></div>
        ${floodedInfoHtml}
        <div style="margin-top:4px; font-size:0.67rem; color:#94a3b8;">Source: ${loc.source}</div>
      </div>
    </div>
  `;

  if (loc._marker) {
    loc._marker.setPopupContent(popupHtml);
    loc._marker.openPopup();
  } else {
    L.popup()
      .setLatLng([loc.coords[1], loc.coords[0]])
      .setContent(popupHtml)
      .openOn(state.map);
  }
}

/**
 * ==========================================================================
 * Milestone 5 (M5) — Scenario Simulation Engine & Dynamic Outputs
 * ==========================================================================
 */

/**
 * Load M5 Simulation Scenarios JSON
 */
async function loadSimulationScenarios() {
  try {
    const res = await fetch('data/simulation_scenarios.json');
    state.simScenarios = await res.json();
    console.log("Loaded M5 simulation scenarios successfully.");
  } catch (err) {
    console.warn("Could not load simulation_scenarios.json:", err);
  }
}

/**
 * Initialize M5 Simulation UI
 */
function initSimulationUI() {
  updateSimUI();
  updateRainfallModeIndicator();
}

/**
 * Update Header Rainfall Mode Indicator (SHL-05)
 * Distinguishes: Scenario Simulation, Synthetic Demonstration, Live Gauge, Inactive
 */
function updateRainfallModeIndicator() {
  const pill = document.getElementById('rainModePill');
  const text = document.getElementById('rainModeText');
  if (!pill || !text) return;

  if (state.simLayerEnabled) {
    pill.className = 'rain-mode-pill mode-scenario';
    if (state.simEngine === 'surrogate') {
      text.textContent = `Mode: ML Surrogate Simulation (${state.simActivePreset}mm Preset) [UNVALIDATED]`;
    } else {
      text.textContent = `Mode: Scenario Simulation (${state.simActivePreset}mm Preset)`;
    }
  } else if (state.m4Enabled && state.rainfallSource === 'sample') {
    pill.className = 'rain-mode-pill mode-demo';
    text.textContent = 'Mode: Synthetic Demonstration (Station 1600)';
  } else if (state.rainfallSource === 'live') {
    pill.className = 'rain-mode-pill mode-live';
    text.textContent = 'Mode: Live Gauge (Unavailable - 0 Files)';
  } else {
    pill.className = 'rain-mode-pill';
    text.textContent = 'Mode: Baseline Inactive';
  }
}

/**
 * Milestone M9: Set Simulation Engine (Original vs Surrogate)
 */
function setSimulationEngine(engine) {
  if (engine !== 'original' && engine !== 'surrogate') return;
  state.simEngine = engine;

  const btnOrig = document.getElementById('btnEngineOriginal');
  const btnSurr = document.getElementById('btnEngineSurrogate');
  const warningBanner = document.getElementById('surrogateWarningBanner');
  const engineLabel = document.getElementById('activeEngineLabel');

  if (btnOrig && btnSurr) {
    if (engine === 'original') {
      btnOrig.classList.add('active');
      btnOrig.style.background = '';
      btnOrig.style.color = '';
      btnOrig.style.fontWeight = '';

      btnSurr.classList.remove('active');
      btnSurr.style.background = '';
      btnSurr.style.color = '';
      btnSurr.style.fontWeight = '';

      if (warningBanner) warningBanner.style.display = 'none';
      if (engineLabel) {
        engineLabel.textContent = 'Physical Screening';
        engineLabel.style.color = 'var(--accent-primary)';
      }
    } else {
      btnSurr.classList.add('active');
      btnSurr.style.background = 'var(--Warning-surface)';
      btnSurr.style.color = '#1F2430';
      btnSurr.style.fontWeight = '700';

      btnOrig.classList.remove('active');
      btnOrig.style.background = '';
      btnOrig.style.color = '';
      btnOrig.style.fontWeight = '';

      if (warningBanner) warningBanner.style.display = 'block';
      if (engineLabel) {
        engineLabel.textContent = 'ML Surrogate (M9)';
        engineLabel.style.color = 'var(--amber-warning)';
      }
    }
  }

  updateRainfallModeIndicator();
  updateSimUI();
  evaluateRescuePriorities();
  if (state.simLayerEnabled) {
    renderSimDynamicOverlay();
  }
}

/**
 * Switch Active Rainfall Preset (RAIN-03)
 */
function selectSimPreset(val) {
  const validPresets = [10, 25, 50, 75, 100];
  if (!validPresets.includes(val)) return;

  // Clear running playback timer
  if (state.simIsPlaying) {
    clearInterval(state.simTimer);
    state.simTimer = null;
    state.simIsPlaying = false;
  }

  state.simActivePreset = val;
  state.simActiveStepIdx = 0;
  state.simLifecycle = 'ready';

  // Update preset buttons visual state
  const presetBtns = document.querySelectorAll('.preset-buttons-grid .preset-btn');
  presetBtns.forEach(btn => {
    const pVal = parseInt(btn.dataset.preset, 10);
    btn.classList.toggle('active', pVal === val);
  });

  const btnPause = document.getElementById('btnSimPause');
  const btnRun = document.getElementById('btnSimRun');
  if (btnPause) btnPause.disabled = true;
  if (btnRun) btnRun.disabled = false;

  updateSimUI();
  updateRainfallModeIndicator();
  evaluateRescuePriorities();

  if (state.simLayerEnabled) {
    renderSimDynamicOverlay();
  }
}

/**
 * Timeline Slider / Scrub Handler (RAIN-07)
 */
function onSimTimelineChange(stepVal) {
  const idx = Math.min(Math.max(parseInt(stepVal, 10), 0), 36);
  state.simActiveStepIdx = idx;

  const slider = document.getElementById('simTimelineSlider');
  if (slider && parseInt(slider.value, 10) !== idx) {
    slider.value = idx;
  }

  updateSimUI();
  evaluateRescuePriorities();

  if (state.simLayerEnabled) {
    renderSimDynamicOverlay();
  }
}

/**
 * Toggle M5 Simulation Layer Visibility
 */
function toggleSimulationLayer(enable) {
  state.simLayerEnabled = enable;
  const cursorSim = document.getElementById('cursorSimDepthText');

  if (!enable) {
    if (state.layers.simulationOverlay && state.map.hasLayer(state.layers.simulationOverlay)) {
      state.map.removeLayer(state.layers.simulationOverlay);
    }
    if (cursorSim) {
      cursorSim.innerHTML = `<span class="badge-tier tier-inactive">Simulation Layer Off</span>`;
    }
  } else {
    renderSimDynamicOverlay();
  }

  updateSimUI();
  updateRainfallModeIndicator();
}

/**
 * Render 5-Class Flood Depth Raster Overlay (SIM-01, LAY-07, M9 Surrogate)
 */
async function renderSimDynamicOverlay() {
  if (!state.simLayerEnabled) {
    if (state.layers.simulationOverlay && state.map.hasLayer(state.layers.simulationOverlay)) {
      state.map.removeLayer(state.layers.simulationOverlay);
    }
    return;
  }

  let sparseDepths = [];

  if (state.simEngine === 'surrogate') {
    const cacheKey = `${state.simActivePreset}_${state.simActiveStepIdx}`;
    let surrogateFrame = state.surrogateCache[cacheKey];

    if (!surrogateFrame) {
      try {
        const payload = {
          mode: 'surrogate',
          rainfall_mm: state.simActivePreset,
          duration_min: 180,
          time_min: state.simActiveStepIdx * 5,
          step_idx: state.simActiveStepIdx
        };
        const res = await fetch('/api/simulations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          surrogateFrame = data;
          state.surrogateCache[cacheKey] = data;
        } else {
          console.warn("Surrogate API returned status:", res.status);
        }
      } catch (err) {
        console.warn("Failed to fetch surrogate prediction:", err);
      }
    }

    if (surrogateFrame && surrogateFrame.timestep) {
      sparseDepths = surrogateFrame.timestep.sparse_depths || [];
      state.surrogateActiveFrame = surrogateFrame.timestep;
      const latencyEl = document.getElementById('surrogateLatencyReadout');
      if (latencyEl && surrogateFrame.metadata) {
        latencyEl.textContent = `Inference: ${surrogateFrame.metadata.inference_time_ms} ms | scikit-learn (HistGradientBoosting)`;
      }
    }
  } else {
    // Canonical M5 Screening Simulation
    if (!state.simScenarios) return;
    const scenario = state.simScenarios.presets['preset_' + state.simActivePreset + 'mm'];
    if (!scenario) return;
    const ts = scenario.timesteps[state.simActiveStepIdx];
    if (!ts) return;
    sparseDepths = ts.sparse_depths || [];
    state.surrogateActiveFrame = null;
  }

  const cols = 100;
  const rows = 100;

  let canvas = document.getElementById('simOffscreenCanvas');
  if (!canvas) {
    canvas = document.createElement('canvas');
    canvas.id = 'simOffscreenCanvas';
    canvas.width = cols;
    canvas.height = rows;
  }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, cols, rows);

  // Paint sparse depths
  if (sparseDepths && sparseDepths.length > 0) {
    for (let i = 0; i < sparseDepths.length; i++) {
      const item = sparseDepths[i];
      const flatIdx = item[0];
      const depth = item[1];
      const r = Math.floor(flatIdx / cols);
      const c = flatIdx % cols;

      let color = 'rgba(0,0,0,0)';
      if (depth <= 0.0) {
        color = 'rgba(0,0,0,0)';
      } else if (depth <= 0.05) {
        color = 'rgba(147, 197, 253, 0.75)'; // Shallow (#93c5fd)
      } else if (depth <= 0.20) {
        color = 'rgba(59, 130, 246, 0.85)';  // Moderate (#3b82f6)
      } else if (depth <= 0.50) {
        color = 'rgba(29, 78, 216, 0.90)';  // Deep (#1d4ed8)
      } else {
        color = 'rgba(30, 27, 75, 0.95)';   // Very Deep (#1e1b4b)
      }

      ctx.fillStyle = color;
      ctx.fillRect(c, r, 1, 1);
    }
  }

  const dataUrl = canvas.toDataURL();
  if (!state.layers.simulationOverlay) {
    state.layers.simulationOverlay = L.imageOverlay(dataUrl, PILOT_BOUNDS, {
      opacity: state.simOpacity,
      interactive: false,
      pane: 'floodPane'
    });
  } else {
    state.layers.simulationOverlay.setUrl(dataUrl);
    state.layers.simulationOverlay.setOpacity(state.simOpacity);
  }

  if (!state.map.hasLayer(state.layers.simulationOverlay)) {
    state.layers.simulationOverlay.addTo(state.map);
  }

  // Milestone M8: Synchronize 3D Flood Surface and HUD
  if (window.viewer3D && window.viewer3D.isInitialized) {
    window.viewer3D.updateFloodSurface();
  }
}

/**
 * Start Simulation Playback (RAIN-04)
 */
function startSimulation() {
  if (state.simIsPlaying) return;

  // Ensure simulation layer is active
  if (!state.simLayerEnabled) {
    const toggle = document.getElementById('toggleSimulationLayer');
    if (toggle) toggle.checked = true;
    toggleSimulationLayer(true);
  }

  // If at the end, restart from beginning
  if (state.simActiveStepIdx >= 36) {
    state.simActiveStepIdx = 0;
  }

  state.simIsPlaying = true;
  state.simLifecycle = 'running';

  const btnPause = document.getElementById('btnSimPause');
  const btnRun = document.getElementById('btnSimRun');
  if (btnPause) btnPause.disabled = false;
  if (btnRun) btnRun.disabled = true;

  updateSimUI();

  state.simTimer = setInterval(() => {
    let nextIdx = state.simActiveStepIdx + 1;
    if (nextIdx > 36) {
      clearInterval(state.simTimer);
      state.simTimer = null;
      state.simIsPlaying = false;
      state.simLifecycle = 'completed';
      if (btnPause) btnPause.disabled = true;
      if (btnRun) btnRun.disabled = false;
      updateSimUI();
      return;
    }
    onSimTimelineChange(nextIdx);
  }, 250); // 250ms per 5-minute timestep
}

/**
 * Pause Simulation Playback (RAIN-04)
 */
function pauseSimulation() {
  if (!state.simIsPlaying) return;

  clearInterval(state.simTimer);
  state.simTimer = null;
  state.simIsPlaying = false;
  state.simLifecycle = 'paused';

  const btnPause = document.getElementById('btnSimPause');
  const btnRun = document.getElementById('btnSimRun');
  if (btnPause) btnPause.disabled = true;
  if (btnRun) btnRun.disabled = false;

  updateSimUI();
}

/**
 * Reset Simulation State (RAIN-04)
 */
function resetSimulation() {
  if (state.simTimer) {
    clearInterval(state.simTimer);
    state.simTimer = null;
  }
  state.simIsPlaying = false;
  state.simLifecycle = 'ready';
  state.simActiveStepIdx = 0;

  const btnPause = document.getElementById('btnSimPause');
  const btnRun = document.getElementById('btnSimRun');
  if (btnPause) btnPause.disabled = true;
  if (btnRun) btnRun.disabled = false;

  onSimTimelineChange(0);
}

/**
 * Jump Directly to Peak Simulation Timestep
 */
function jumpToSimPeak() {
  if (!state.simScenarios) return;
  const scenario = state.simScenarios.presets['preset_' + state.simActivePreset + 'mm'];
  if (!scenario) return;

  const peakMin = scenario.peak_time_minutes || 60;
  const peakIdx = Math.round(peakMin / 5);
  onSimTimelineChange(peakIdx);
}

/**
 * Toggle Workflow Drawer (RAIN-05)
 */
function toggleWorkflowDrawer() {
  state.simWorkflowDrawerOpen = !state.simWorkflowDrawerOpen;
  const drawer = document.getElementById('workflowDrawer');
  if (drawer) {
    drawer.classList.toggle('open', state.simWorkflowDrawerOpen);
  }
}

/**
 * Close Workflow Drawer (RAIN-05)
 */
function closeWorkflowDrawer() {
  state.simWorkflowDrawerOpen = false;
  const drawer = document.getElementById('workflowDrawer');
  if (drawer) {
    drawer.classList.remove('open');
  }
}

/**
 * Update M5 UI Elements, Readouts, and Six-Field Status Bar (BAR-01 & BAR-02)
 */
function updateSimUI() {
  const lifecycleBadge = document.getElementById('simLifecycleBadge');
  const stateBadge = document.getElementById('simStateBadge');
  const timeLabel = document.getElementById('simTimeLabel');
  const intervalRain = document.getElementById('simIntervalRain');
  const intervalRate = document.getElementById('simIntervalIntensity');
  const cumRain = document.getElementById('simCumulativeRain');
  const cumRunoff = document.getElementById('simCumulativeRunoff');

  // Status Bar Fields
  const statusRain = document.getElementById('statusValRainTotal');
  const statusMaxDepth = document.getElementById('statusValMaxDepth');
  const statusArea = document.getElementById('statusValFloodedArea');
  const statusNodes = document.getElementById('statusValSurchargedNodes');
  const statusDrains = document.getElementById('statusValOverloadedDrains');
  const statusWarn = document.getElementById('statusValActiveWarnings');

  if (lifecycleBadge) {
    lifecycleBadge.className = `sim-lifecycle-pill pill-${state.simLifecycle}`;
    lifecycleBadge.textContent = state.simLifecycle.toUpperCase();
  }
  if (stateBadge) {
    stateBadge.className = `layer-badge badge-m5 pill-${state.simLifecycle}`;
    stateBadge.textContent = state.simLifecycle.toUpperCase();
  }

  const min = state.simActiveStepIdx * 5;
  const hh = String(Math.floor(min / 60)).padStart(2, '0');
  const mm = String(min % 60).padStart(2, '0');
  if (timeLabel) {
    timeLabel.textContent = `Time: ${hh}:${mm} (Min ${min} / 180)`;
  }

  if (!state.simScenarios) {
    if (statusRain) statusRain.textContent = '--';
    if (statusMaxDepth) statusMaxDepth.textContent = '--';
    if (statusArea) statusArea.textContent = '--';
    if (statusWarn) statusWarn.textContent = '--';
    return;
  }

  const scenario = state.simScenarios.presets['preset_' + state.simActivePreset + 'mm'];
  if (!scenario) return;

  const ts = scenario.timesteps[state.simActiveStepIdx];
  const hyeto = scenario.hyetograph;
  const currentInterval = (state.simActiveStepIdx > 0 && state.simActiveStepIdx <= hyeto.length)
    ? hyeto[state.simActiveStepIdx - 1]
    : null;

  // Readout Card (RAIN-06)
  if (state.simActiveStepIdx === 0 || !currentInterval) {
    if (intervalRain) intervalRain.textContent = '0.00 mm (0.00 in)';
    if (intervalRate) intervalRate.textContent = '0.00 mm/h (0.00 in/hr)';
    if (cumRain) cumRain.textContent = '0.00 mm (0.00 in)';
    if (cumRunoff) cumRunoff.textContent = '0.00 mm (CN=88)';
  } else {
    if (intervalRain) intervalRain.textContent = `${currentInterval.rain_mm.toFixed(2)} mm (${currentInterval.rain_in.toFixed(3)} in)`;
    if (intervalRate) intervalRate.textContent = `${currentInterval.intensity_mm_hr.toFixed(1)} mm/h (${currentInterval.intensity_in_hr.toFixed(2)} in/hr)`;
    if (cumRain) cumRain.textContent = `${ts.cumulative_rain_mm.toFixed(2)} mm (${(ts.cumulative_rain_mm / 25.4).toFixed(3)} in)`;
    if (cumRunoff) {
      const qMm = (ts.mass_balance.precip_m3 - ts.mass_balance.infil_m3) / 970000.0 * 1000.0;
      cumRunoff.textContent = `${Math.max(qMm, 0.0).toFixed(2)} mm (CN=88)`;
    }
  }

  // Six-Field Status Bar (BAR-01 & BAR-02)
  if (statusRain) {
    statusRain.textContent = `${scenario.target_rainfall_mm.toFixed(1)} mm`;
  }
  if (statusMaxDepth) {
    statusMaxDepth.textContent = `${ts.max_depth_m.toFixed(2)} m`;
  }
  if (statusArea) {
    statusArea.textContent = `${ts.flooded_area_km2.toFixed(3)} km²`;
  }
  // Milestone 6 Dynamic Drainage Loading Updates
  const presetKey = 'preset_' + state.simActivePreset + 'mm';
  const m6Step = state.m6Data?.dynamic_simulation_loading?.[presetKey]?.timesteps?.[state.simActiveStepIdx];

  if (statusNodes) {
    if (m6Step) {
      statusNodes.textContent = `${m6Step.surcharged_inlet_nodes_count} Surcharged (Est)`;
      statusNodes.style.color = m6Step.surcharged_inlet_nodes_count > 0 ? '#fbbf24' : '#34d399';
    } else {
      statusNodes.textContent = '0 Surcharged (Est)';
      statusNodes.style.color = '#34d399';
    }
  }

  if (statusDrains) {
    if (m6Step) {
      statusDrains.textContent = `${m6Step.overloaded_conduits_count} Overloaded Drains`;
      statusDrains.style.color = m6Step.overloaded_conduits_count > 0 ? '#f43f5e' : '#34d399';
    } else {
      statusDrains.textContent = '0 Overloaded Drains';
      statusDrains.style.color = '#34d399';
    }
  }

  if (statusWarn) {
    if (ts.max_depth_m < 0.05 && (!m6Step || m6Step.overloaded_conduits_count === 0)) {
      statusWarn.textContent = 'None (Dry / No Inundation)';
      statusWarn.style.color = '#34d399';
    } else {
      const topHotspot = state.m6Data?.hotspots?.[0]?.name || 'Milam & Commerce Bayou Approach';
      const overText = m6Step && m6Step.overloaded_conduits_count > 0 ? ` · ${m6Step.overloaded_conduits_count} pipes overloaded` : '';
      statusWarn.textContent = `Ponding: ${topHotspot} (${ts.max_depth_m.toFixed(2)} m)${overText}`;
      statusWarn.style.color = '#fbbf24';
    }
  }

  // If dynamic conduit loading mode is active, refresh pipe colors
  if (state.drainageLoadingMode) {
    updateConduitLoadingStyles();
  }

  // If routes are active, update dynamic route hazard exposure for new timestep
  if (typeof updateActiveRouteKPIs === 'function') {
    updateActiveRouteKPIs();
  }
}

/**
 * ==========================================================================
 * Milestone 6 (M6) — Drainage Network, Connectivity & Hydraulic Capacity Engine
 * ==========================================================================
 */

/**
 * Load M6 Drainage Network Topology & Capacity Data JSON
 */
async function loadM6DrainageNetwork() {
  try {
    const res = await fetch('data/m6_drainage_network.json');
    state.m6Data = await res.json();
    console.log("Loaded M6 Drainage Network model successfully:", state.m6Data.statistics);
    if (window.viewer3D && window.viewer3D.isInitialized) {
      window.viewer3D.buildDrainageLines();
    }
  } catch (err) {
    console.warn("Could not load m6_drainage_network.json:", err);
  }
}

/**
 * Initialize M6 Drainage UI
 */
function initM6UI() {
  if (state.m6Data) {
    const badge = document.getElementById('headerDrainageBadge');
    if (badge) {
      badge.textContent = 'M6 OPERATIONAL';
      badge.className = 'badge-status-pill pill-ready';
      badge.style.background = 'rgba(16, 185, 129, 0.15)';
      badge.style.color = '#34d399';
      badge.style.borderColor = 'rgba(16, 185, 129, 0.35)';
    }
  }
}

/**
 * Trace Upstream Path from clicked Conduit or Node using BFS
 */
function traceUpstream(startAssetId) {
  if (!state.m6Data) return;
  const assetId = String(startAssetId);

  const conduits = state.m6Data.conduits;
  const nodes = state.m6Data.nodes;

  const visitedConduits = new Set();
  const visitedNodes = new Set();
  const nodeQueue = [];

  // Determine starting point
  if (conduits[assetId]) {
    visitedConduits.add(assetId);
    const upNode = conduits[assetId].from_node;
    if (upNode && nodes[upNode]) {
      visitedNodes.add(upNode);
      nodeQueue.push(upNode);
    }
  } else if (nodes[assetId]) {
    visitedNodes.add(assetId);
    nodeQueue.push(assetId);
  } else {
    console.warn("Asset not found in drainage network for upstream trace:", assetId);
    return;
  }

  // BFS upstream along incoming conduits
  while (nodeQueue.length > 0) {
    const currNodeId = nodeQueue.shift();
    const currNode = nodes[currNodeId];
    if (!currNode || !currNode.incoming_conduits) continue;

    for (const inCid of currNode.incoming_conduits) {
      if (!visitedConduits.has(inCid)) {
        visitedConduits.add(inCid);
        const upConduit = conduits[inCid];
        if (upConduit && upConduit.from_node && !visitedNodes.has(upConduit.from_node)) {
          visitedNodes.add(upConduit.from_node);
          nodeQueue.push(upConduit.from_node);
        }
      }
    }
  }

  renderTracePath(visitedConduits, visitedNodes, 'upstream');
}

/**
 * Trace Downstream Path toward Outfall from clicked Conduit or Node using BFS
 */
function traceDownstream(startAssetId) {
  if (!state.m6Data) return;
  const assetId = String(startAssetId);

  const conduits = state.m6Data.conduits;
  const nodes = state.m6Data.nodes;

  const visitedConduits = new Set();
  const visitedNodes = new Set();
  const nodeQueue = [];

  // Determine starting point
  if (conduits[assetId]) {
    visitedConduits.add(assetId);
    const downNode = conduits[assetId].to_node;
    if (downNode && nodes[downNode]) {
      visitedNodes.add(downNode);
      nodeQueue.push(downNode);
    }
  } else if (nodes[assetId]) {
    visitedNodes.add(assetId);
    nodeQueue.push(assetId);
  } else {
    console.warn("Asset not found in drainage network for downstream trace:", assetId);
    return;
  }

  // BFS downstream along outgoing conduits
  while (nodeQueue.length > 0) {
    const currNodeId = nodeQueue.shift();
    const currNode = nodes[currNodeId];
    if (!currNode || !currNode.outgoing_conduits) continue;

    for (const outCid of currNode.outgoing_conduits) {
      if (!visitedConduits.has(outCid)) {
        visitedConduits.add(outCid);
        const downConduit = conduits[outCid];
        if (downConduit && downConduit.to_node && !visitedNodes.has(downConduit.to_node)) {
          visitedNodes.add(downConduit.to_node);
          nodeQueue.push(downConduit.to_node);
        }
      }
    }
  }

  renderTracePath(visitedConduits, visitedNodes, 'downstream');
}

/**
 * Render Highlighted Trace Layer on Leaflet Map
 */
function renderTracePath(visitedConduits, visitedNodes, direction) {
  clearTrace();

  const conduits = state.m6Data.conduits;
  const nodes = state.m6Data.nodes;

  const features = [];
  let totalLength = 0;

  visitedConduits.forEach(cid => {
    const c = conduits[cid];
    if (c) {
      totalLength += c.length_m || 0;
      if (c.coordinates) {
        features.push({
          type: 'Feature',
          properties: { id: cid, assetType: 'conduit', length_m: c.length_m },
          geometry: {
            type: 'LineString',
            coordinates: c.coordinates
          }
        });
      }
    }
  });

  let inletsCount = 0;
  let manholesCount = 0;
  let outfallsCount = 0;

  visitedNodes.forEach(nid => {
    const nd = nodes[nid];
    if (nd) {
      if (nd.node_type === 'inlet') inletsCount++;
      else if (nd.node_type === 'manhole') manholesCount++;
      else if (nd.node_type === 'discharge') outfallsCount++;

      if (nd.coords) {
        features.push({
          type: 'Feature',
          properties: { id: nid, assetType: 'node', nodeType: nd.node_type },
          geometry: {
            type: 'Point',
            coordinates: nd.coords
          }
        });
      }
    }
  });

  const geoJson = {
    type: 'FeatureCollection',
    features: features
  };

  state.m6ActiveTraceLayer = L.geoJSON(geoJson, {
    style: (feature) => {
      return {
        color: '#fbbf24',
        weight: 6,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round'
      };
    },
    pointToLayer: (feature, latlng) => {
      return L.circleMarker(latlng, {
        radius: 7,
        fillColor: '#fde047',
        color: '#ffffff',
        weight: 2,
        fillOpacity: 1.0
      });
    }
  }).addTo(state.map);

  state.m6ActiveTraceLayer.bringToFront();

  // Update Summary Box
  const summaryBox = document.getElementById('traceSummaryBox');
  if (summaryBox) {
    summaryBox.style.display = 'block';
    if (direction === 'upstream') {
      summaryBox.innerHTML = `
        <div style="font-weight:600; color:#fbbf24;">▲ Upstream Contributing Path:</div>
        <div>${visitedConduits.size} conduits (${totalLength.toFixed(1)} m)</div>
        <div style="color:var(--text-secondary); font-size:0.68rem; margin-top:2px;">
          ${inletsCount} street inlets · ${manholesCount} access junctions
        </div>
      `;
    } else {
      const reachesBayou = outfallsCount > 0;
      const reachText = reachesBayou
        ? `<span style="color:#34d399; font-weight:600;">✓ Connects to Buffalo Bayou Outfall</span>`
        : `<span style="color:#a855f7;">Boundary / Dangling Trunk</span>`;
      summaryBox.innerHTML = `
        <div style="font-weight:600; color:#fbbf24;">▼ Downstream Flow Path:</div>
        <div>${visitedConduits.size} conduits (${totalLength.toFixed(1)} m)</div>
        <div style="color:var(--text-secondary); font-size:0.68rem; margin-top:2px;">
          ${reachText} · ${manholesCount} junctions
        </div>
      `;
    }
  }

  // Show clear buttons
  const btnClearSide = document.getElementById('btnClearTraceSidebar');
  if (btnClearSide) btnClearSide.style.display = 'inline-flex';
}

/**
 * Clear Active Network Trace from Map
 */
function clearTrace() {
  if (state.m6ActiveTraceLayer && state.map.hasLayer(state.m6ActiveTraceLayer)) {
    state.map.removeLayer(state.m6ActiveTraceLayer);
  }
  state.m6ActiveTraceLayer = null;

  const summaryBox = document.getElementById('traceSummaryBox');
  if (summaryBox) summaryBox.style.display = 'none';

  const btnClearSide = document.getElementById('btnClearTraceSidebar');
  if (btnClearSide) btnClearSide.style.display = 'none';
}

/**
 * Toggle Dynamic Drainage Loading Styling on Gravity Mains
 */
function toggleDrainageLoadingMode(enable) {
  state.drainageLoadingMode = enable;
  if (enable) {
    updateConduitLoadingStyles();
  } else {
    if (state.layers.gravityMains) {
      state.layers.gravityMains.eachLayer(layer => {
        state.layers.gravityMains.resetStyle(layer);
      });
    }
  }
}

/**
 * Update Conduit Styles based on Dynamic Loading Status
 */
function updateConduitLoadingStyles() {
  if (!state.layers.gravityMains || !state.m6Data) return;

  const conduits = state.m6Data.conduits;
  const pKey = 'preset_' + state.simActivePreset + 'mm';
  const simStep = state.m6Data.dynamic_simulation_loading?.[pKey]?.timesteps?.[state.simActiveStepIdx];
  const baseInflow = simStep ? simStep.inflow_rate_per_inlet_m3s : 0.0;

  state.layers.gravityMains.eachLayer(layer => {
    const p = layer.feature.properties;
    const cid = String(p.FACILITYID || p.OBJECTID || '');
    const c = conduits[cid] || Object.values(conduits).find(x => String(x.objectid) === cid || String(x.ufid) === cid);

    if (!c) return;

    const isCalculable = c.capacity_status && c.capacity_status.startsWith('CALCULAT') && c.capacity_m3s !== null && c.capacity_m3s > 0;
    if (c.connectivity_type === 'dangling_boundary' && !c.reaches_bayou_outfall) {
      layer.setStyle({ color: '#a855f7', weight: 2.5, opacity: 0.85, dashArray: null });
    } else if (!isCalculable) {
      layer.setStyle({ color: '#64748b', weight: 1.5, opacity: 0.6, dashArray: '4, 4' });
    } else {
      const qCond = (c.contributing_inlet_fraction !== undefined ? c.contributing_inlet_fraction : 0.0) * baseInflow;
      const ratio = qCond / c.capacity_m3s;
      if (ratio > 1.0) {
        layer.setStyle({ color: '#ef4444', weight: 4.5, opacity: 1.0, dashArray: null });
      } else if (ratio >= 0.70) {
        layer.setStyle({ color: '#fbbf24', weight: 3.5, opacity: 0.95, dashArray: null });
      } else {
        layer.setStyle({ color: '#38bdf8', weight: 2.5, opacity: 0.85, dashArray: null });
      }
    }
  });
}

/**
 * ==========================================================================
 * Milestone 7 (M7) — Safest Route Planner Implementation
 * ==========================================================================
 */

/**
 * Load Street Network GeoJSON and Compiled Routing Graph
 */
async function loadStreetNetworkAndGraph() {
  try {
    const [resNet, resGraph, resMeta] = await Promise.all([
      fetch('data/street_network.geojson'),
      fetch('data/m7_routing_graph.json'),
      fetch('data/m7_route_planner_meta.json')
    ]);

    state.streetNetwork = await resNet.json();
    state.routingGraph = await resGraph.json();
    state.m7Meta = await resMeta.json();

    // Initialize Layer Group for Active Route Polylines & Markers
    state.routeLayerGroup = L.layerGroup().addTo(state.map);

    // Render Street Network Overlay (Base Road Grid)
    renderStreetNetworkOverlay();

    // Calculate default route (Bagby to Milam)
    computeRouteAlternatives();

  } catch (err) {
    console.warn("Could not load M7 street network or routing graph:", err);
    const pill = document.getElementById('sidebarM7StatusPill');
    if (pill) {
      pill.textContent = 'DATA UNAVAILABLE';
      pill.style.background = 'rgba(239,68,68,0.15)';
      pill.style.color = '#f87171';
    }
  }
}

/**
 * Render Street Network GeoJSON Layer
 */
function renderStreetNetworkOverlay() {
  if (!state.streetNetwork || !state.map) return;

  state.streetNetworkLayer = L.geoJSON(state.streetNetwork, {
    style: (feature) => {
      const rc = feature.properties.road_class;
      let weight = 2.0;
      let color = '#475569';
      if (rc === 'MAJOR' || rc === 'HIGHWAY') {
        weight = 3.0;
        color = '#64748b';
      }
      return {
        color: color,
        weight: weight,
        opacity: 0.65,
        lineCap: 'round',
        lineJoin: 'round'
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindTooltip(`
        <div style="font-weight:600; color:#34d399;">${p.name || 'Unnamed Street'}</div>
        <div style="font-size:0.7rem; color:#94a3b8;">Class: ${p.road_class} · Speed: ${p.speed_limit_mph} mph · Length: ${p.length_m} m</div>
      `, { className: 'custom-tooltip', sticky: true });
    }
  }).addTo(state.map);
}

/**
 * Setup Safest Route Planner UI Event Listeners
 */
function setupRoutePlannerEventListeners() {
  // Street layer toggle
  const toggleStreet = document.getElementById('toggleStreetNetwork');
  if (toggleStreet) {
    toggleStreet.addEventListener('change', (e) => {
      if (!state.streetNetworkLayer) return;
      if (e.target.checked) {
        state.map.addLayer(state.streetNetworkLayer);
      } else {
        state.map.removeLayer(state.streetNetworkLayer);
      }
    });
  }

  // Route Mode Selector (Pedestrian vs Vehicle)
  const btnPed = document.getElementById('btnModePedestrian');
  const btnVeh = document.getElementById('btnModeVehicle');
  if (btnPed && btnVeh) {
    btnPed.addEventListener('click', () => {
      state.routeMode = 'pedestrian';
      btnPed.classList.add('active');
      btnVeh.classList.remove('active');
      updateVehicleDestinationRestrictions('pedestrian');
      computeRouteAlternatives();
    });
    btnVeh.addEventListener('click', () => {
      state.routeMode = 'vehicle';
      btnVeh.classList.add('active');
      btnPed.classList.remove('active');
      updateVehicleDestinationRestrictions('vehicle');
      computeRouteAlternatives();
    });
  }

  // Landmark Selection Dropdowns
  const selStart = document.getElementById('selectStartLandmark');
  if (selStart) {
    selStart.addEventListener('change', (e) => {
      if (e.target.value && e.target.value !== 'custom') {
        const parts = e.target.value.split(',').map(Number);
        state.routeStartCoords = [parts[0], parts[1]];
        updateCoordsReadout('start', parts[0], parts[1]);
        computeRouteAlternatives();
      }
    });
  }

  const selDest = document.getElementById('selectDestLandmark');
  if (selDest) {
    selDest.addEventListener('change', (e) => {
      updateVehicleDestinationRestrictions(state.routeMode || 'pedestrian');
      if (e.target.value && e.target.value !== 'custom') {
        const parts = e.target.value.split(',').map(Number);
        state.routeDestCoords = [parts[0], parts[1]];
        updateCoordsReadout('dest', parts[0], parts[1]);
        computeRouteAlternatives();
      }
    });
  }

  // Pick on Map Buttons
  const btnPickStart = document.getElementById('btnPickStartMap');
  if (btnPickStart) {
    btnPickStart.addEventListener('click', () => setRoutePickingMode('start'));
  }

  const btnPickDest = document.getElementById('btnPickDestMap');
  if (btnPickDest) {
    btnPickDest.addEventListener('click', () => setRoutePickingMode('dest'));
  }

  // Calculate & Reset Buttons
  const btnCalc = document.getElementById('btnCalculateRoute');
  if (btnCalc) {
    btnCalc.addEventListener('click', () => computeRouteAlternatives());
  }

  const btnReset = document.getElementById('btnResetRoute');
  if (btnReset) {
    btnReset.addEventListener('click', () => resetRoute());
  }

  // Profile Tab Buttons (Drainage-Informed vs Baseline vs Low-Susc)
  const profileBtns = document.querySelectorAll('.profile-tab-btn');
  profileBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      profileBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeRouteProfile = btn.dataset.profile;
      renderActiveRouteOnMap();
      updateRouteUI();
    });
  });

  // Modal Open Buttons
  const btnOpenModal = document.getElementById('btnRoutePlannerModal');
  if (btnOpenModal) {
    btnOpenModal.addEventListener('click', () => openRouteGovernanceModal());
  }

  const btnOpenModalSidebar = document.getElementById('btnOpenRouteModalFromSidebar');
  if (btnOpenModalSidebar) {
    btnOpenModalSidebar.addEventListener('click', () => openRouteGovernanceModal());
  }
}

/**
 * Activate Map Picking Mode (Start or Dest)
 */
function setRoutePickingMode(mode) {
  state.pickingRoutePoint = mode;
  const btnStart = document.getElementById('btnPickStartMap');
  const btnDest = document.getElementById('btnPickDestMap');

  if (btnStart) btnStart.classList.toggle('picking', mode === 'start');
  if (btnDest) btnDest.classList.toggle('picking', mode === 'dest');

  if (mode) {
    state.map.getContainer().style.cursor = 'crosshair';
  } else {
    state.map.getContainer().style.cursor = '';
  }
}

/**
 * Handle Map Click when picking Start or Dest
 */
function onMapClickRouteHandler(e) {
  if (!state.pickingRoutePoint) return;

  const lon = e.latlng.lng;
  const lat = e.latlng.lat;

  // Enforce pilot bounding box
  const b = state.m1Meta?.pilot_boundary || { west: -95.3750, south: 29.7560, east: -95.3650, north: 29.7650 };
  const buf = 0.002; // small tolerance
  if (lon < b.west - buf || lon > b.east + buf || lat < b.south - buf || lat > b.north + buf) {
    alert("Please click within or adjacent to the Downtown Houston pilot boundary [-95.3750, 29.7560 to -95.3650, 29.7650].");
    setRoutePickingMode(null);
    return;
  }

  if (state.pickingRoutePoint === 'start') {
    state.routeStartCoords = [lon, lat];
    updateCoordsReadout('start', lon, lat);
    const sel = document.getElementById('selectStartLandmark');
    if (sel) sel.value = 'custom';
  } else if (state.pickingRoutePoint === 'dest') {
    state.routeDestCoords = [lon, lat];
    updateCoordsReadout('dest', lon, lat);
    const sel = document.getElementById('selectDestLandmark');
    if (sel) sel.value = 'custom';
  }

  setRoutePickingMode(null);
  computeRouteAlternatives();
}

/**
 * Update Coordinate Readout Text
 */
function updateCoordsReadout(type, lon, lat) {
  const el = document.getElementById(type === 'start' ? 'startCoordsText' : 'destCoordsText');
  if (el) {
    el.textContent = `Lon: ${lon.toFixed(6)}, Lat: ${lat.toFixed(6)}`;
  }
}

/**
 * Haversine Distance in meters
 */
function haversineDist(lon1, lat1, lon2, lat2) {
  const R = 6371000;
  const p1 = lat1 * Math.PI / 180;
  const p2 = lat2 * Math.PI / 180;
  const dp = (lat2 - lat1) * Math.PI / 180;
  const dl = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dp / 2) * Math.sin(dp / 2) + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Densify polyline at approximately 10m intervals
 * Preserves segment endpoints, guarantees no duplicate consecutive samples
 */
function densifyPolyline(coords, stepM = 10.0) {
  if (!coords || coords.length < 2) return coords ? [coords[0]] : [];
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

// Landmarks with in-degree 0 for vehicles due to downtown Houston directed one-way street topology
const VEHICLE_RESTRICTED_DESTINATIONS = [
  "-95.3680,29.7645", // Milam & Franklin (node 143: Preston St outbound one-way / self-loop stub)
  "-95.3720,29.7625"  // Preston & Heiner (node 45: outbound ramp one-way)
];

/**
 * Update Vehicle Destination Dropdown and Contextual Notice
 */
function updateVehicleDestinationRestrictions(mode) {
  const selDest = document.getElementById('selectDestLandmark');
  if (!selDest) return;

  const rawLabels = {
    "-95.3680,29.7645": "Milam & Franklin (Bayou NE Channel)",
    "-95.3660,29.7610": "Main & Capitol (East Core)",
    "-95.3670,29.7570": "Travis & Bell (South Core)",
    "-95.3720,29.7625": "Preston & Heiner (Northwest Low)"
  };

  Array.from(selDest.options).forEach(opt => {
    const val = opt.value;
    const baseLabel = rawLabels[val];
    if (!baseLabel) return;
    if (mode === 'vehicle' && VEHICLE_RESTRICTED_DESTINATIONS.includes(val)) {
      opt.textContent = `${baseLabel} — [One-Way Restricted]`;
    } else {
      opt.textContent = baseLabel;
    }
  });

  let noticeEl = document.getElementById('vehicleOnewayNotice');
  if (mode === 'vehicle' && VEHICLE_RESTRICTED_DESTINATIONS.includes(selDest.value)) {
    if (!noticeEl) {
      noticeEl = document.createElement('div');
      noticeEl.id = 'vehicleOnewayNotice';
      noticeEl.style.cssText = 'font-size:0.67rem; color:#f59e0b; margin-top:4px; display:flex; align-items:flex-start; gap:4px; line-height:1.3; background:rgba(245,158,11,0.08); padding:4px 6px; border-radius:3px; border:1px solid rgba(245,158,11,0.25);';
      selDest.parentElement.appendChild(noticeEl);
    }
    noticeEl.innerHTML = `<span>⚠️ <strong>One-Way Network Restriction:</strong> Destination intersection has egress-only one-way approaches in the pilot crop. Pedestrian walkway access remains 100% available.</span>`;
  } else if (noticeEl) {
    noticeEl.remove();
  }
}

/**
 * Snap coordinates to nearest intersection node in routingGraph
 */
function snapToNearestGraphNode(lon, lat, maxDistM = 250) {
  if (!state.routingGraph || !state.routingGraph.nodes) return null;

  let bestNode = null;
  let minDist = Infinity;
  state.routingGraph.nodes.forEach(nd => {
    const d = haversineDist(lon, lat, nd.coords[0], nd.coords[1]);
    if (d < minDist) {
      minDist = d;
      bestNode = nd.id;
    }
  });

  return { nodeId: bestNode, snapDistM: Math.round(minDist) };
}

/**
 * Calculate Edge Cost for Given Scenario & Timestep
 */
// Documented Experimental Screening Thresholds (Prototypes, NOT empirical certifications)
const EXPERIMENTAL_THRESHOLDS = {
  pedestrian: {
    caution_depth_m: 0.10,      // 10 cm (~ankle depth; difficult/unpleasant to wade)
    impassable_depth_m: 0.25,   // 25 cm (~shin/knee depth; hazardous footing/sweeping risk)
    speed_mps: 1.34,            // AASHTO / MUTCD default (4.8 km/h, 3.0 mph)
    label: 'Pedestrian Mode'
  },
  vehicle: {
    caution_depth_m: 0.15,      // 15 cm (~6 inches; curb level / exhaust splash)
    impassable_depth_m: 0.30,   // 30 cm (~12 inches; passenger sedan air intake stall / float limit)
    speed_mph: 30.0,
    label: 'Vehicle Mode'
  }
};

/**
 * Fast M5 Timestep Depth Map Lookup Cache
 */
function getTimestepDepthMap(presetMm, timestepIdx) {
  if (!state.simScenarios) return null;
  const pKey = 'preset_' + presetMm + 'mm';
  const ts = state.simScenarios.presets?.[pKey]?.timesteps?.[timestepIdx];
  if (!ts || !ts.sparse_depths) return null;

  if (!ts._depthMap) {
    ts._depthMap = new Map();
    for (let i = 0; i < ts.sparse_depths.length; i++) {
      const pair = ts.sparse_depths[i];
      ts._depthMap.set(pair[0], pair[1]);
    }
  }
  return ts._depthMap;
}

/**
 * Assess Road Segment Waterlogging Exposure against M5 Simulation Output
 */
function assessEdgeWaterlogging(edge, presetMm, timestepIdx, mode = 'pedestrian') {
  const modeKey = mode === 'vehicle' ? 'vehicle' : 'pedestrian';
  const thresh = EXPERIMENTAL_THRESHOLDS[modeKey];
  const cautionTh = thresh.caution_depth_m;
  const impassableTh = thresh.impassable_depth_m;

  const diag = {
    status: 'VALID_PILOT',
    dataAvailable: true,
    outsideCount: 0,
    sampledCount: 0,
    maxDepthM: 0.0,
    meanDepthM: 0.0,
    affectedLengthM: 0.0,
    affectedPct: 0.0,
    riskTier: 'Dry',
    isCaution: false,
    isImpassable: false,
    uncertaintyPenalty: 0.0
  };

  const depthMap = getTimestepDepthMap(presetMm, timestepIdx);
  if (!depthMap) {
    diag.status = 'UNAVAILABLE';
    diag.dataAvailable = false;
    diag.uncertaintyPenalty = 80.0;
    return diag;
  }

  const b = { west: -95.3750, south: 29.7560, east: -95.3650, north: 29.7650 };
  const samplePts = densifyPolyline(edge.coords, 10.0);
  const nSamples = samplePts.length;
  diag.sampledCount = nSamples;

  if (nSamples === 0) return diag;

  const depths = [];
  let outsideCount = 0;

  for (let i = 0; i < nSamples; i++) {
    const lon = samplePts[i][0];
    const lat = samplePts[i][1];
    if (lon >= b.west && lon <= b.east && lat >= b.south && lat <= b.north) {
      const col = Math.min(Math.max(Math.floor((lon - b.west) / (b.east - b.west) * 100), 0), 99);
      const row = Math.min(Math.max(Math.floor((b.north - lat) / (b.north - b.south) * 100), 0), 99);
      const flatIdx = row * 100 + col;
      const d = depthMap.get(flatIdx) || 0.0;
      depths.push(d);
    } else {
      outsideCount++;
      depths.push(0.0);
    }
  }

  diag.outsideCount = outsideCount;
  if (outsideCount > 0) {
    diag.status = 'BOUNDARY_CROSSING';
    diag.dataAvailable = false;
    diag.uncertaintyPenalty = 80.0;
  }

  let maxD = 0.0;
  let sumD = 0.0;
  let floodedCount = 0;
  for (let i = 0; i < depths.length; i++) {
    const d = depths[i];
    if (d > maxD) maxD = d;
    sumD += d;
    if (d > 0.02) floodedCount++;
  }

  const meanD = depths.length > 0 ? sumD / depths.length : 0.0;
  diag.maxDepthM = Math.round(maxD * 1000) / 1000;
  diag.meanDepthM = Math.round(meanD * 1000) / 1000;

  const floodedRatio = nSamples > 0 ? floodedCount / nSamples : 0.0;
  diag.affectedLengthM = Math.round(edge.length_m * floodedRatio * 10) / 10;
  diag.affectedPct = Math.round(floodedRatio * 1000) / 10;

  if (maxD < 0.01) diag.riskTier = 'Dry';
  else if (maxD < 0.05) diag.riskTier = 'Low';
  else if (maxD < 0.15) diag.riskTier = 'Moderate';
  else if (maxD < 0.30) diag.riskTier = 'Elevated';
  else diag.riskTier = 'High';

  diag.isCaution = (maxD >= cautionTh);
  diag.isImpassable = (maxD >= impassableTh);

  return diag;
}

/**
 * Calculate Edge Cost for Given Scenario, Timestep, and Profile
 */
function calculateEdgeCost(edge, presetMm, timestepIdx, mode = 'pedestrian', profile = 'drainage_informed') {
  const cBase = edge.length_m;

  // 1. Shortest / Baseline
  if (profile === 'baseline' || profile === 'shortest') {
    return {
      totalCost: cBase,
      cBase: cBase,
      mSusc: 1.0,
      pDepth: 0.0,
      pDrain: 0.0,
      pUncert: 0.0,
      maxDepthM: 0.0,
      exceededCount: 0,
      highCount: 0,
      ewsi: edge.susc_mean !== undefined ? edge.susc_mean : 0.25
    };
  }

  // 2. Low-Susceptibility
  if (profile === 'low_susceptibility') {
    const ewsi = edge.susc_mean !== undefined ? edge.susc_mean : 0.25;
    return {
      totalCost: cBase * (1.0 + ewsi),
      cBase: cBase,
      mSusc: 1.0 + ewsi,
      pDepth: 0.0,
      pDrain: 0.0,
      pUncert: 0.0,
      maxDepthM: 0.0,
      exceededCount: 0,
      highCount: 0,
      ewsi: ewsi
    };
  }

  // Water Assessment
  const assessment = assessEdgeWaterlogging(edge, presetMm, timestepIdx, mode);
  const maxDepthM = assessment.maxDepthM;

  // 3. Lowest Exposure Profile
  if (profile === 'lowest_exposure' || profile === 'low_exposure') {
    let pDepth = 0.0;
    if (maxDepthM > 0.0) {
      if (maxDepthM <= 0.01) pDepth = 0.0;
      else if (maxDepthM <= 0.05) pDepth = (maxDepthM / 0.05) * 50.0;
      else if (maxDepthM <= 0.15) pDepth = 150.0 + ((maxDepthM - 0.05) / 0.10) * 800.0;
      else if (maxDepthM <= 0.25) pDepth = 1000.0 + ((maxDepthM - 0.15) / 0.10) * 3000.0;
      else pDepth = 4000.0 + (maxDepthM - 0.25) * 10000.0;
    }

    let pThreshold = 0.0;
    if (assessment.isImpassable) pThreshold += 20000.0;
    else if (assessment.isCaution) pThreshold += 500.0;

    const pLength = assessment.affectedLengthM * 2.0;
    const pUncert = assessment.uncertaintyPenalty;

    const totalCost = cBase + pDepth + pThreshold + pLength + pUncert;
    return {
      totalCost: Math.round(totalCost * 10) / 10,
      cBase: cBase,
      mSusc: 1.0,
      pDepth: Math.round((pDepth + pThreshold + pLength) * 10) / 10,
      pDrain: 0.0,
      pUncert: pUncert,
      maxDepthM: maxDepthM,
      exceededCount: 0,
      highCount: 0,
      ewsi: edge.susc_mean !== undefined ? edge.susc_mean : 0.25,
      assessment: assessment
    };
  }

  // 4. Drainage-Informed Profile
  const ewsi = edge.susc_mean !== undefined ? edge.susc_mean : 0.25;
  const mSusc = 1.0 + (1.0 * ewsi);

  let pDepth = 0.0;
  if (maxDepthM > 0.0) {
    if (maxDepthM <= 0.05) pDepth = (maxDepthM / 0.05) * 50.0;
    else if (maxDepthM <= 0.20) pDepth = 150.0 + ((maxDepthM - 0.05) / 0.15) * 350.0;
    else if (maxDepthM <= 0.50) pDepth = 500.0 + ((maxDepthM - 0.20) / 0.30) * 1500.0;
    else pDepth = 2000.0 + (maxDepthM - 0.50) * 5000.0;
  }

  let pDrain = 0.0;
  let exceededCount = 0;
  let highCount = 0;
  let insufficientCount = 0;
  if (state.m6Data && edge.nearby_conduit_ids && edge.nearby_conduit_ids.length > 0) {
    const pKey = 'preset_' + presetMm + 'mm';
    const m6Step = state.m6Data.dynamic_simulation_loading?.[pKey]?.timesteps?.[timestepIdx];
    const baseInflow = m6Step ? m6Step.inflow_rate_per_inlet_m3s : 0.0;

    edge.nearby_conduit_ids.forEach(cid => {
      const c = state.m6Data.conduits?.[cid];
      if (c && c.capacity_status?.startsWith('CALCULAT') && c.capacity_m3s > 0) {
        const q = (c.contributing_inlet_fraction || 0.0) * baseInflow;
        const ratio = q / c.capacity_m3s;
        if (ratio > 1.0) exceededCount++;
        else if (ratio >= 0.70) highCount++;
      } else if (c) {
        insufficientCount++;
      }
    });

    pDrain = (exceededCount * 100.0) + (highCount * 30.0);
  }

  let pUncert = assessment.uncertaintyPenalty;
  if (insufficientCount > 0) pUncert += 25.0;

  const totalCost = (cBase * mSusc) + pDepth + pDrain + pUncert;

  return {
    totalCost: Math.round(totalCost * 10) / 10,
    cBase: cBase,
    mSusc: mSusc,
    pDepth: Math.round(pDepth * 10) / 10,
    pDrain: Math.round(pDrain * 10) / 10,
    pUncert: Math.round(pUncert * 10) / 10,
    maxDepthM: maxDepthM,
    exceededCount: exceededCount,
    highCount: highCount,
    ewsi: ewsi,
    assessment: assessment
  };
}

/**
 * Dijkstra Pathfinding Algorithm in Client
 */
function runDijkstra(startNodeId, destNodeId, profile, mode = 'pedestrian') {
  if (!state.routingGraph) return null;

  const nodes = state.routingGraph.nodes;
  const edges = state.routingGraph.edges;
  const preset = state.simActivePreset || 50;
  const stepIdx = state.simActiveStepIdx || 0;

  // Build adjacency
  const adj = {};
  for (let i = 0; i < nodes.length; i++) adj[i] = [];
  edges.forEach((e, idx) => {
    adj[e.from_node].push({ to: e.to_node, edgeIdx: idx, dir: 'forward' });
    adj[e.to_node].push({ to: e.from_node, edgeIdx: idx, dir: 'backward' });
  });

  // Dijkstra search with configurable strict impassable exclusion
  function dijkstraSearch(strictImpassableExclusion = false) {
    const dist = {};
    const prev = {};
    const prevEdge = {};
    for (let i = 0; i < nodes.length; i++) dist[i] = Infinity;
    dist[startNodeId] = 0;

    const q = new Set();
    for (let i = 0; i < nodes.length; i++) q.add(i);

    while (q.size > 0) {
      let u = null;
      let minDist = Infinity;
      q.forEach(node => {
        if (dist[node] < minDist) {
          minDist = dist[node];
          u = node;
        }
      });

      if (u === null || dist[u] === Infinity) break;
      if (u === destNodeId) break;

      q.delete(u);

      (adj[u] || []).forEach(edgeObj => {
        const v = edgeObj.to;
        if (!q.has(v)) return;

        const edge = edges[edgeObj.edgeIdx];

        // Vehicle one-way constraint
        if (mode === 'vehicle') {
          if (edgeObj.dir === 'forward' && edge.one_way === 'TF') return;
          if (edgeObj.dir === 'backward' && edge.one_way === 'FT') return;
        }

        const assessment = assessEdgeWaterlogging(edge, preset, stepIdx, mode);
        if (strictImpassableExclusion && assessment.isImpassable) {
          return; // Strict hard exclusion
        }

        const costData = calculateEdgeCost(edge, preset, stepIdx, mode, profile);
        let eWeight = costData.totalCost;

        // Lexicographic fallback tier when not strict
        if (!strictImpassableExclusion && (profile === 'lowest_exposure' || profile === 'low_exposure')) {
          if (assessment.isImpassable) {
            eWeight += 10000000.0;
          }
        }

        const alt = dist[u] + eWeight;
        if (alt < dist[v]) {
          dist[v] = alt;
          prev[v] = u;
          prevEdge[v] = edgeObj.edgeIdx;
        }
      });
    }

    if (dist[destNodeId] === Infinity) return null;

    const pathEdges = [];
    let curr = destNodeId;
    while (curr !== startNodeId && prev[curr] !== undefined) {
      pathEdges.unshift(prevEdge[curr]);
      curr = prev[curr];
    }
    return pathEdges;
  }

  let passableFound = true;
  let pathEdges = null;

  if (profile === 'lowest_exposure' || profile === 'low_exposure') {
    // Pass 1: Strict hard exclusion of impassable segments
    pathEdges = dijkstraSearch(true);
    if (!pathEdges) {
      // Pass 2: No 100% passable path exists in network. Run lexicographic minimal-impassable fallback.
      passableFound = false;
      pathEdges = dijkstraSearch(false);
    }
  } else {
    pathEdges = dijkstraSearch(false);
  }

  if (!pathEdges) {
    return {
      status: 'NO_ROUTE_FOUND',
      message: `No connected street path exists between intersection #${startNodeId} and #${destNodeId}.`
    };
  }

  let totalDistM = 0;
  let totalCost = 0;
  let maxDepthM = 0;
  let submergedLengthM = 0;
  let suscWeightedSum = 0;
  let exceededDrains = 0;
  let impassableCount = 0;
  let cautionCount = 0;
  let hasMissingData = false;
  let allDataAvailable = true;
  const streetNames = new Set();
  const routeCoords = [];
  const floodExposedSegments = [];

  pathEdges.forEach(eIdx => {
    const e = edges[eIdx];
    totalDistM += e.length_m;
    const costData = calculateEdgeCost(e, preset, stepIdx, mode, profile);
    const assessment = costData.assessment || assessEdgeWaterlogging(e, preset, stepIdx, mode);

    totalCost += costData.totalCost;
    if (assessment.maxDepthM > maxDepthM) maxDepthM = assessment.maxDepthM;

    if (!assessment.dataAvailable || assessment.status !== 'VALID_PILOT') {
      hasMissingData = true;
      allDataAvailable = false;
    }

    if (assessment.affectedLengthM > 0) {
      submergedLengthM += assessment.affectedLengthM;
    } else if (assessment.maxDepthM > 0.02) {
      submergedLengthM += e.length_m;
    }

    if (assessment.isImpassable) impassableCount++;
    else if (assessment.isCaution) cautionCount++;

    if (assessment.maxDepthM > 0.02) {
      floodExposedSegments.push({
        edgeId: eIdx,
        name: e.name,
        lengthM: e.length_m,
        maxDepthM: assessment.maxDepthM,
        meanDepthM: assessment.meanDepthM,
        affectedLengthM: assessment.affectedLengthM,
        affectedPct: assessment.affectedPct,
        riskTier: assessment.riskTier,
        isCaution: assessment.isCaution,
        isImpassable: assessment.isImpassable,
        coords: e.coords
      });
    }

    suscWeightedSum += (e.susc_mean || 0.25) * e.length_m;
    exceededDrains += costData.exceededCount;
    if (e.name) streetNames.add(e.name);
  });

  // Assemble route coordinates with strict traversal orientation anchored on startNodeId
  let currNode = startNodeId;
  pathEdges.forEach(eIdx => {
    const e = edges[eIdx];
    let pts;
    if (e.from_node === currNode) {
      pts = e.coords;
      currNode = e.to_node;
    } else if (e.to_node === currNode) {
      pts = [...e.coords].reverse();
      currNode = e.from_node;
    } else {
      const d0 = haversineDist(e.coords[0][0], e.coords[0][1], nodes[currNode].coords[0], nodes[currNode].coords[1]);
      const d1 = haversineDist(e.coords[e.coords.length - 1][0], e.coords[e.coords.length - 1][1], nodes[currNode].coords[0], nodes[currNode].coords[1]);
      pts = d0 <= d1 ? e.coords : [...e.coords].reverse();
      currNode = d0 <= d1 ? e.to_node : e.from_node;
    }

    if (routeCoords.length === 0) {
      routeCoords.push(...pts);
    } else {
      routeCoords.push(...pts.slice(1));
    }
  });

  const meanEwsi = totalDistM > 0 ? Math.round((suscWeightedSum / totalDistM) * 100) / 100 : 0.25;
  let tier = 'Low';
  if (meanEwsi >= 0.80) tier = 'High';
  else if (meanEwsi >= 0.60) tier = 'Elevated';
  else if (meanEwsi >= 0.35) tier = 'Moderate';

  let exposureCat = 'Minimal (Dry)';
  if (maxDepthM >= 0.30) exposureCat = 'High / Severe';
  else if (maxDepthM >= 0.15) exposureCat = 'Elevated';
  else if (maxDepthM >= 0.05) exposureCat = 'Moderate';
  else if (maxDepthM >= 0.01) exposureCat = 'Low';

  return {
    status: 'SUCCESS',
    profile: profile,
    mode: mode,
    passableRouteFound: passableFound,
    routingType: 'STATIC_SCENARIO_SNAPSHOT',
    simulationTimeMin: stepIdx * 5,
    snapshotDescription: `Static scenario snapshot at Minute ${stepIdx * 5} of ${preset}mm rainfall event (uncalibrated M5 aggregate depression drawdown model; not dynamic time-dependent routing)`,
    dataAvailable: allDataAvailable,
    hasMissingData: hasMissingData,
    distanceM: Math.round(totalDistM),
    distanceFt: Math.round(totalDistM * 3.28084),
    walkTimeMin: Math.round((totalDistM / (1.34 * 60)) * 10) / 10,
    vehicleTimeMin: Math.round((totalDistM / ((30 * 1609.34 / 3600) * 60)) * 10) / 10,
    hazardScore: Math.round(totalCost),
    maxDepthM: maxDepthM,
    submergedLengthM: Math.round(submergedLengthM),
    submergedPct: totalDistM > 0 ? Math.round((submergedLengthM / totalDistM) * 100) : 0,
    exposureCategory: exposureCat,
    floodExposedSegments: floodExposedSegments,
    floodExposedCount: floodExposedSegments.length,
    impassableSegmentsCount: impassableCount,
    cautionSegmentsCount: cautionCount,
    meanEwsi: meanEwsi,
    suscTier: tier,
    exceededDrains: exceededDrains,
    streetNames: Array.from(streetNames),
    coordinates: routeCoords,
    edgeCount: pathEdges.length
  };
}

/**
 * Determine Recommended Route & Generate Decision Support Justification
 */
function determineRecommendation(alts, mode = 'pedestrian') {
  const modeKey = mode === 'vehicle' ? 'vehicle' : 'pedestrian';
  const thresh = EXPERIMENTAL_THRESHOLDS[modeKey];
  const cautionD = thresh.caution_depth_m;
  const impassableD = thresh.impassable_depth_m;

  const shortest = alts.shortest || alts.baseline;
  const lowestExp = alts.lowest_exposure;

  if (!shortest || shortest.status !== 'SUCCESS') {
    if (lowestExp && lowestExp.status === 'SUCCESS') {
      return {
        recommendedKey: 'lowest_exposure',
        reason: 'Lowest Waterlogging Exposure route is the only viable path found.',
        alerts: ['Shortest path unavailable or blocked by network restrictions.']
      };
    }
    return {
      recommendedKey: null,
      reason: 'No continuous street route found between origin and destination.',
      alerts: ['No route available.']
    };
  }

  const sDepth = shortest.maxDepthM || 0.0;
  const sSubM = shortest.submergedLengthM || 0.0;
  const sDist = shortest.distanceM || 0;

  const lDepth = (lowestExp && lowestExp.status === 'SUCCESS') ? lowestExp.maxDepthM : sDepth;
  const lSubM = (lowestExp && lowestExp.status === 'SUCCESS') ? lowestExp.submergedLengthM : sSubM;
  const lDist = (lowestExp && lowestExp.status === 'SUCCESS') ? lowestExp.distanceM : sDist;

  const alerts = [];
  const hasMissingData = shortest.hasMissingData || (lowestExp && lowestExp.hasMissingData);
  const passableFound = lowestExp ? lowestExp.passableRouteFound : true;

  // Network impassability guardrail
  if (passableFound === false) {
    alerts.push(`CRITICAL WARNING: No fully passable route exists across the network. All available paths traverse water exceeding the ${modeKey} threshold (${impassableD.toFixed(2)}m).`);
  }

  if (sDepth >= impassableD) {
    alerts.push(`Shortest route encounters potentially impassable water (${sDepth.toFixed(2)}m >= ${impassableD.toFixed(2)}m ${modeKey} threshold).`);
  } else if (sDepth >= cautionD) {
    alerts.push(`Shortest route encounters cautionary waterlogging (${sDepth.toFixed(2)}m >= ${cautionD.toFixed(2)}m ${modeKey} threshold).`);
  }

  // Dry conditions everywhere AND all data available
  if (!hasMissingData && sDepth <= 0.01 && sSubM <= 1.0) {
    return {
      recommendedKey: 'shortest',
      reason: 'Shortest Route is recommended: dry conditions (0.00m water depth) modelled across all candidate paths.',
      alerts: alerts
    };
  }

  // Zero depth recorded but missing data present
  if (hasMissingData && sDepth <= 0.01) {
    return {
      recommendedKey: 'shortest',
      reason: 'Shortest Route is recommended: minimal travel distance under current scenario.',
      alerts: alerts
    };
  }

  // Flood avoidance
  if (lowestExp && lowestExp.status === 'SUCCESS') {
    const extraDist = lDist - sDist;

    if (sDepth >= cautionD && lDepth < sDepth) {
      if (lDepth < impassableD && sDepth >= impassableD) {
        return {
          recommendedKey: 'lowest_exposure',
          reason: `Lowest Waterlogging Exposure route is recommended: diverts around impassable inundation (${sDepth.toFixed(2)}m on shortest path), reducing maximum depth to ${lDepth.toFixed(2)}m (${extraDist >= 0 ? '+' : ''}${Math.round(extraDist)}m detour).`,
          alerts: alerts
        };
      }
      return {
        recommendedKey: 'lowest_exposure',
        reason: `Lowest Waterlogging Exposure route is recommended: reduces maximum water depth from ${sDepth.toFixed(2)}m to ${lDepth.toFixed(2)}m (${extraDist >= 0 ? '+' : ''}${Math.round(extraDist)}m detour, ${lSubM}m submerged vs ${sSubM}m).`,
        alerts: alerts
      };
    }

    if (sSubM > 50 && lSubM < sSubM * 0.5) {
      return {
        recommendedKey: 'lowest_exposure',
        reason: `Lowest Waterlogging Exposure route is recommended: cuts submerged road length from ${sSubM}m to ${lSubM}m (${extraDist >= 0 ? '+' : ''}${Math.round(extraDist)}m detour).`,
        alerts: alerts
      };
    }
  }

  if (sDepth < cautionD) {
    return {
      recommendedKey: 'shortest',
      reason: `Shortest Route is recommended: modelled water depth (${sDepth.toFixed(2)}m) remains below ${modeKey} caution threshold (${cautionD.toFixed(2)}m).`,
      alerts: alerts
    };
  }

  if (lDepth >= impassableD) {
    alerts.push(`WARNING: All evaluated candidate route profiles encounter water exceeding the ${modeKey} impassable threshold (${impassableD.toFixed(2)}m).`);
    return {
      recommendedKey: 'lowest_exposure',
      reason: `Lowest Exposure route has lowest relative water exposure (${lDepth.toFixed(2)}m vs ${sDepth.toFixed(2)}m), but exceeds ${modeKey} threshold (${impassableD.toFixed(2)}m). Exercise extreme caution.`,
      alerts: alerts
    };
  }

  return {
    recommendedKey: lDepth < sDepth ? 'lowest_exposure' : 'shortest',
    reason: `Lowest Waterlogging Exposure route provides lower modelled water exposure (${lDepth.toFixed(2)}m vs ${sDepth.toFixed(2)}m).`,
    alerts: alerts
  };
}
function computeRouteAlternatives() {
  if (!state.routingGraph) return;

  const startSnap = snapToNearestGraphNode(state.routeStartCoords[0], state.routeStartCoords[1]);
  const destSnap = snapToNearestGraphNode(state.routeDestCoords[0], state.routeDestCoords[1]);

  if (!startSnap || !destSnap) {
    alert("Could not snap start or destination to the road network. Ensure points are within the pilot boundary.");
    return;
  }

  const mode = state.routeMode || 'pedestrian';
  const shortest = runDijkstra(startSnap.nodeId, destSnap.nodeId, 'shortest', mode);
  const lowestExp = runDijkstra(startSnap.nodeId, destSnap.nodeId, 'lowest_exposure', mode);
  const drainage = runDijkstra(startSnap.nodeId, destSnap.nodeId, 'drainage_informed', mode);

  const alts = {
    shortest: shortest,
    baseline: shortest, // backward compatibility alias
    lowest_exposure: lowestExp,
    drainage_informed: drainage,
    low_susceptibility: lowestExp, // backward compatibility alias
    startSnap: startSnap,
    destSnap: destSnap
  };

  const rec = determineRecommendation(alts, mode);
  alts.recommendation = rec;
  state.routeAlternatives = alts;

  // Set default active route to recommended profile unless user already picked
  if (!state.userSelectedRouteProfile && rec.recommendedKey) {
    state.activeRouteProfile = rec.recommendedKey;
  } else if (!state.activeRouteProfile) {
    state.activeRouteProfile = rec.recommendedKey || 'lowest_exposure';
  }

  renderActiveRouteOnMap();
  updateRouteUI();
}

/**
 * Render Route Polylines, Flood-Exposed Segments, and Markers on Leaflet Map
 */
function renderActiveRouteOnMap() {
  if (!state.routeLayerGroup || !state.routeAlternatives) return;

  state.routeLayerGroup.clearLayers();

  const alts = state.routeAlternatives;
  const activeProfile = state.activeRouteProfile || 'lowest_exposure';
  const activeRoute = alts[activeProfile];

  // 1. Draw Inactive Alternative Routes with Dashed Styling
  const altProfiles = [
    { key: 'lowest_exposure', label: 'Lowest Exposure Alternative', color: '#10b981' },
    { key: 'shortest', label: 'Shortest Distance Alternative', color: '#0284c7' },
    { key: 'drainage_informed', label: 'Drainage-Informed Alternative', color: '#06b6d4' }
  ];

  altProfiles.forEach(alt => {
    if (alt.key !== activeProfile && alts[alt.key]?.coordinates) {
      const poly = L.polyline(alts[alt.key].coordinates.map(p => [p[1], p[0]]), {
        color: alt.color,
        weight: 3.5,
        opacity: 0.6,
        dashArray: '5, 6'
      }).addTo(state.routeLayerGroup);

      poly.bindTooltip(`
        <div style="font-weight:700; color:${alt.color};">${alt.label}</div>
        <div>Dist: ${alts[alt.key].distanceM}m · Max Depth: ${alts[alt.key].maxDepthM.toFixed(2)}m</div>
        <div style="font-size:0.68rem; color:#94a3b8;">Click to switch to this route</div>
      `, { sticky: true, className: 'custom-tooltip' });

      poly.on('click', () => switchRouteProfile(alt.key));
    }
  });

  // 2. Draw Active Profile Route Prominently
  if (activeRoute?.coordinates) {
    let mainColor = '#10b981';
    if (activeProfile === 'shortest') mainColor = '#0284c7';
    if (activeProfile === 'drainage_informed') mainColor = '#06b6d4';

    const activePoly = L.polyline(activeRoute.coordinates.map(p => [p[1], p[0]]), {
      color: mainColor,
      weight: 6.5,
      opacity: 0.95
    }).addTo(state.routeLayerGroup);

    activePoly.bindTooltip(`
      <div style="font-weight:700; color:${mainColor}; font-size:0.8rem;">${activeProfile.toUpperCase().replace('_', ' ')} ROUTE</div>
      <div>Distance: ${activeRoute.distanceM} m · Score: ${activeRoute.hazardScore}</div>
      <div>Max Depth: ${activeRoute.maxDepthM.toFixed(2)} m · Submerged: ${activeRoute.submergedLengthM} m (${activeRoute.submergedPct}%)</div>
      <div>Exposure Category: <strong>${activeRoute.exposureCategory}</strong></div>
    `, { sticky: true, className: 'custom-tooltip' });

    // 3. Highlight Flood-Exposed Road Segments along the active route
    if (activeRoute.floodExposedSegments && activeRoute.floodExposedSegments.length > 0) {
      activeRoute.floodExposedSegments.forEach(seg => {
        const isImp = seg.isImpassable;
        const segColor = isImp ? '#ef4444' : '#f59e0b';
        const segWeight = isImp ? 9 : 8;

        const floodPoly = L.polyline(seg.coords.map(p => [p[1], p[0]]), {
          color: segColor,
          weight: segWeight,
          opacity: 0.9,
          lineCap: 'round',
          dashArray: isImp ? '8, 4' : null
        }).addTo(state.routeLayerGroup);

        floodPoly.bindTooltip(`
          <div style="font-weight:700; color:${segColor}; font-size:0.78rem;">
            ${isImp ? '⛔ IMPASSABLE WATERLOGGING' : '⚠️ FLOOD-EXPOSED SEGMENT'}
          </div>
          <div style="font-weight:600;">${seg.name || 'Street Segment'}</div>
          <div>Est. Max Depth: <strong>${seg.maxDepthM.toFixed(2)} m</strong> (${seg.riskTier})</div>
          <div>Affected Road: <strong>${seg.affectedLengthM} m</strong> (${seg.affectedPct}%)</div>
          <div style="font-size:0.68rem; color:#fca5a5;">Mode: ${state.routeMode || 'pedestrian'} threshold screening</div>
        `, { sticky: true, className: 'custom-tooltip' });
      });
    }
  }

  // 4. Custom Pulsed Markers for Start (Point A) and Destination (Point B)
  const iconA = L.divIcon({
    className: 'custom-route-pin pin-start',
    html: 'A',
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  });
  const iconB = L.divIcon({
    className: 'custom-route-pin pin-dest',
    html: 'B',
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  });

  L.marker([state.routeStartCoords[1], state.routeStartCoords[0]], { icon: iconA })
    .bindTooltip(`<strong>Start (Point A)</strong><br>Snapped: ${alts.startSnap.snapDistM}m to intersection`, { sticky: true })
    .addTo(state.routeLayerGroup);

  L.marker([state.routeDestCoords[1], state.routeDestCoords[0]], { icon: iconB })
    .bindTooltip(`<strong>Destination (Point B)</strong><br>Snapped: ${alts.destSnap.snapDistM}m to intersection`, { sticky: true })
    .addTo(state.routeLayerGroup);
}

/**
 * Update Safest Route Planner UI Elements (Recommendation Box, KPIs, Comparison Table)
 */
function updateRouteUI() {
  if (!state.routeAlternatives) return;

  const alts = state.routeAlternatives;
  const activeProfile = state.activeRouteProfile || 'lowest_exposure';
  const r = alts[activeProfile];
  const rec = alts.recommendation;

  const recBox = document.getElementById('routeRecommendationBox');
  const profileTabs = document.getElementById('routeProfileTabs');
  const kpiCard = document.getElementById('routeKpiCard');
  const compareMini = document.getElementById('routeCompareMini');
  const statusRoute = document.getElementById('statusValActiveRoute');

  if (profileTabs) profileTabs.style.display = 'grid';
  if (kpiCard) kpiCard.style.display = 'block';
  if (compareMini) compareMini.style.display = 'block';

  // Update Dynamic Recommendation Box
  if (recBox && rec) {
    recBox.style.display = 'block';
    const isRecommended = (rec.recommendedKey === activeProfile);
    const badgeColorClass = rec.recommendedKey === 'lowest_exposure' ? 'rec-badge-emerald' : 'rec-badge-blue';
    const titleText = rec.recommendedKey === 'lowest_exposure' ? '🏆 Recommended: Lowest Exposure' : (rec.recommendedKey === 'shortest' ? '⚡ Recommended: Shortest Path' : '✦ Recommended: Drainage-Informed');

    const activeAlerts = (rec.alerts || []).filter(a => !a.includes('DATA UNCERTAINTY'));
    recBox.className = 'route-recommendation-box' + (activeAlerts.length > 0 ? (r?.impassableSegmentsCount > 0 ? ' has-danger' : ' has-warning') : '');

    let alertsHtml = '';
    if (activeAlerts.length > 0) {
      alertsHtml = activeAlerts.map(a => `<div class="rec-alert-item"><span>⚠️</span> <span>${a}</span></div>`).join('');
    }

    let cleanReason = rec.reason;
    if (cleanReason && cleanReason.includes('unmeasured/missing data penalties')) {
      cleanReason = 'Shortest Route is recommended: minimal travel distance under current scenario.';
    }

    recBox.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="rec-badge ${badgeColorClass}">${titleText}</span>
        ${isRecommended ? '<span style="font-size:0.67rem; color:#059669; font-weight:700;">● ACTIVE</span>' : `<span style="font-size:0.67rem; color:#64748b; cursor:pointer;" onclick="switchRouteProfile('${rec.recommendedKey}')">Switch to recommended →</span>`}
      </div>
      <div class="rec-reason">${cleanReason}</div>
      ${alertsHtml}
    `;
  }

  // Handle No Route Found
  if (!r || r.status !== 'SUCCESS') {
    const isVehRestricted = state.routeMode === 'vehicle' &&
      VEHICLE_RESTRICTED_DESTINATIONS.some(c => {
        const pts = c.split(',').map(Number);
        return Math.abs(pts[0] - state.routeDestCoords[0]) < 0.0008 &&
               Math.abs(pts[1] - state.routeDestCoords[1]) < 0.0008;
      });
    const msg = isVehRestricted
      ? "No vehicle path exists: destination intersection has outbound one-way restrictions in the pilot domain. Switch to 🚶 Pedestrian mode for accessible path."
      : (r?.message || "No continuous street route found between selected points.");
    if (kpiCard) kpiCard.innerHTML = `<div style="color:#f87171; font-weight:600; font-size:0.75rem; line-height:1.4;">${msg}</div>`;
    return;
  }

  // Update Profile Tabs Active State
  const profileBtns = document.querySelectorAll('.profile-tab-btn');
  profileBtns.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.profile === activeProfile);
  });

  // Update Title & Status Pill
  const titleMap = {
    lowest_exposure: 'Lowest Waterlogging Exposure Path',
    shortest: 'Shortest Geometric Path',
    baseline: 'Shortest Geometric Path',
    drainage_informed: 'Drainage-Informed Path',
    low_susceptibility: 'Lowest Waterlogging Exposure Path'
  };
  const titleEl = document.getElementById('kpiProfileTitle');
  if (titleEl) titleEl.textContent = titleMap[activeProfile] || activeProfile;

  const hazardPill = document.getElementById('kpiHazardPill');
  if (hazardPill) hazardPill.textContent = `Score: ${r.hazardScore}`;

  // Update KPIs
  const distEl = document.getElementById('kpiDistVal');
  if (distEl) distEl.textContent = `${r.distanceM} m (${r.distanceFt.toLocaleString()} ft)`;

  const timeEl = document.getElementById('kpiTimeVal');
  if (timeEl) {
    timeEl.textContent = state.routeMode === 'vehicle'
      ? `${r.vehicleTimeMin} min drive`
      : `${r.walkTimeMin} min walk`;
  }

  const depthEl = document.getElementById('kpiDepthVal');
  if (depthEl) {
    depthEl.textContent = r.maxDepthM > 0 ? `${r.maxDepthM.toFixed(2)} m (${r.exposureCategory})` : '0.00 m (Dry)';
    depthEl.style.color = r.maxDepthM >= 0.25 ? '#f43f5e' : (r.maxDepthM >= 0.10 ? '#fbbf24' : '#38bdf8');
  }

  const submergedEl = document.getElementById('kpiSubmergedVal');
  if (submergedEl) {
    submergedEl.textContent = `${r.submergedLengthM} m (${r.submergedPct}%)`;
    submergedEl.style.color = r.submergedLengthM > 0 ? '#f43f5e' : '#10b981';
  }

  const suscEl = document.getElementById('kpiSuscVal');
  if (suscEl) suscEl.textContent = `${r.suscTier} (${r.meanEwsi})`;

  const drainsEl = document.getElementById('kpiDrainsVal');
  if (drainsEl) {
    drainsEl.textContent = `${r.exceededDrains} Surcharged`;
    drainsEl.style.color = r.exceededDrains > 0 ? '#f43f5e' : '#34d399';
  }

  const streetsEl = document.getElementById('kpiStreetsVal');
  if (streetsEl) {
    streetsEl.textContent = `Via: ${r.streetNames.slice(0, 4).join(', ')}${r.streetNames.length > 4 ? '...' : ''}`;
  }

  // Update Mini Comparison Table
  const tbody = document.getElementById('routeCompareMiniBody');
  if (tbody) {
    const rows = [
      { id: 'lowest_exposure', name: 'Lowest Exposure', color: '#10b981', data: alts.lowest_exposure },
      { id: 'shortest', name: 'Shortest Route', color: '#0284c7', data: alts.shortest || alts.baseline },
      { id: 'drainage_informed', name: 'Drainage-Informed', color: '#06b6d4', data: alts.drainage_informed }
    ];

    tbody.innerHTML = rows.map(row => {
      const d = row.data;
      if (!d || d.status !== 'SUCCESS') return '';
      const isSel = row.id === activeProfile;
      const isRec = rec?.recommendedKey === row.id;
      return `
        <tr style="cursor:pointer; background:${isSel ? 'rgba(56,189,248,0.1)' : 'transparent'}; font-weight:${isSel ? '600' : 'normal'};" onclick="switchRouteProfile('${row.id}')">
          <td style="padding:4px;"><span style="color:${row.color};">■</span> ${row.name} ${isRec ? '<span style="color:#059669; font-weight:700;">★</span>' : ''}</td>
          <td style="padding:4px;">${d.distanceM}m</td>
          <td style="padding:4px; color:${d.maxDepthM >= 0.10 ? '#f43f5e' : '#38bdf8'};">${d.maxDepthM > 0 ? d.maxDepthM.toFixed(2) + 'm' : 'Dry'}</td>
          <td style="padding:4px; font-family:var(--font-mono);">${d.hazardScore}</td>
        </tr>
      `;
    }).join('');
  }

  // Update Footer Bar Status Field
  if (statusRoute) {
    statusRoute.textContent = `${titleMap[activeProfile]} (${r.distanceM}m · Max Depth: ${r.maxDepthM.toFixed(2)}m)`;
  }
}

/**
 * Switch Active Profile from Table or Tabs
 */
window.switchRouteProfile = function(profileKey) {
  state.userSelectedRouteProfile = true;
  state.activeRouteProfile = profileKey;
  const profileBtns = document.querySelectorAll('.profile-tab-btn');
  profileBtns.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.profile === profileKey);
  });
  renderActiveRouteOnMap();
  updateRouteUI();
};

/**
 * Re-evaluate Route KPIs when M5 simulation slider moves or preset changes
 */
function updateActiveRouteKPIs() {
  if (!state.routeAlternatives) return;
  computeRouteAlternatives();
}

function resetRoute() {
  if (state.routeLayerGroup) state.routeLayerGroup.clearLayers();
  state.routeAlternatives = null;
  state.userSelectedRouteProfile = false;

  const recBox = document.getElementById('routeRecommendationBox');
  const profileTabs = document.getElementById('routeProfileTabs');
  const kpiCard = document.getElementById('routeKpiCard');
  const compareMini = document.getElementById('routeCompareMini');
  const statusRoute = document.getElementById('statusValActiveRoute');

  if (recBox) recBox.style.display = 'none';
  if (profileTabs) profileTabs.style.display = 'none';
  if (kpiCard) kpiCard.style.display = 'none';
  if (compareMini) compareMini.style.display = 'none';
  if (statusRoute) statusRoute.textContent = 'None Selected';

  setRoutePickingMode(null);
}

/**
 * Open Safest Route Governance & Comparison Modal
 */
function openRouteGovernanceModal() {
  const modal = document.getElementById('qualityModalBackdrop');
  if (modal) {
    modal.style.display = 'flex';
    // Switch to tab-m7-routing
    const tabBtns = document.querySelectorAll('#qualityModalBackdrop .modal-tabs .tab-btn');
    tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === 'tab-m7-routing'));

    const panels = document.querySelectorAll('#qualityModalBackdrop .tab-panel');
    panels.forEach(p => p.classList.toggle('active', p.id === 'tab-m7-routing'));
  }
}

/**
 * ==========================================================================
 * Guided Presentation Mode (8-Stage Step-by-Step Walkthrough)
 * Reuses existing functionality without fabricating outputs or breaking nav.
 * ==========================================================================
 */

const GUIDED_DEMO_STAGES = [
  {
    num: '01',
    titleKey: 'guided_demo.s1_title',
    fallbackTitle: 'Houston Map & GIS Layers',
    descKey: 'guided_demo.s1_desc',
    fallbackDesc: 'Explore the 0.97 km² Downtown Houston / Buffalo Bayou pilot study area. Inspect the verified 1m LiDAR bare-earth DEM elevation raster, topographic hillshade, and City of Houston storm sewer infrastructure layers in the left sidebar.',
    provenance: 'VERIFIED 1M DEM · COH GIS',
    actionKey: 'sidebar_extra.fit_extent',
    fallbackAction: 'Fit to Pilot Extent',
    highlightIds: ['sectionM0Dem', 'sectionM3Drainage'],
    scrollId: 'sectionM0Dem',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
      const demToggle = document.getElementById('toggleDemTerrain');
      if (demToggle && !demToggle.checked) {
        demToggle.checked = true;
        demToggle.dispatchEvent(new Event('change'));
      }
      const mainsToggle = document.getElementById('toggleGravityMains');
      if (mainsToggle && !mainsToggle.checked) {
        mainsToggle.checked = true;
        mainsToggle.dispatchEvent(new Event('change'));
      }
      if (state.map) {
        state.map.fitBounds(PILOT_BOUNDS, { padding: [30, 30] });
      }
    },
    onAction: function () {
      if (state.map) {
        state.map.fitBounds(PILOT_BOUNDS, { padding: [30, 30] });
      }
    }
  },
  {
    num: '02',
    titleKey: 'guided_demo.s2_title',
    fallbackTitle: 'Rainfall Scenario',
    descKey: 'guided_demo.s2_desc',
    fallbackDesc: 'Review the rainfall forcing inputs. Select synthetic design storm presets (10mm to 100mm/hr) in the sidebar or inspect the M2 gauge ingestion pipeline (highlighting live feed UNAVAILABLE vs. synthetic test fixture UNVERIFIED).',
    provenance: 'SYNTHETIC PRESETS · LIVE GAUGE UNAVAILABLE',
    actionKey: 'guided_demo.action_open_rainfall',
    fallbackAction: 'Open Rainfall Hyetograph',
    highlightIds: ['sectionM2Rainfall', 'simPresetsGroup'],
    scrollId: 'sectionM2Rainfall',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
    },
    onAction: function () {
      const btnRain = document.getElementById('btnRainfallModal');
      if (btnRain) btnRain.click();
    }
  },
  {
    num: '03',
    titleKey: 'guided_demo.s3_title',
    fallbackTitle: 'Flood Detection',
    descKey: 'guided_demo.s3_desc',
    fallbackDesc: 'Run the M5 2D hydrodynamic screening model across a 180-minute storm timeline. Observe ponding depths (SIM-01 5-class ramp) accumulating in low-lying topographic depressions.',
    provenance: 'MODELLED SCREENING (M5)',
    actionKey: 'guided_demo.action_jump_peak',
    fallbackAction: 'Jump to Peak Flood (60m)',
    highlightIds: ['sectionM5Simulation'],
    scrollId: 'sectionM5Simulation',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
      setSimulationEngine('original');
      const simToggle = document.getElementById('toggleSimulationLayer');
      if (simToggle && !simToggle.checked) {
        simToggle.checked = true;
        toggleSimLayer(true);
      }
      selectSimPreset(50);
      jumpToSimPeak();
    },
    onAction: function () {
      const simToggle = document.getElementById('toggleSimulationLayer');
      if (simToggle && !simToggle.checked) {
        simToggle.checked = true;
        toggleSimLayer(true);
      }
      jumpToSimPeak();
    }
  },
  {
    num: '04',
    titleKey: 'guided_demo.s4_title',
    fallbackTitle: 'Drainage Analysis',
    descKey: 'guided_demo.s4_desc',
    fallbackDesc: 'Activate M6 Dynamic Hydraulic Loading to evaluate storm sewer capacity under active runoff. Color-coded conduits reveal Normal, High Loading, and Capacity Exceeded pipes, plus upstream/downstream network trace.',
    provenance: 'MANNING\'S CAPACITY · MODELLED / ASSUMED (M6)',
    actionKey: 'guided_demo.action_open_drainage',
    fallbackAction: 'Open Drainage Capacity Report',
    highlightIds: ['drainageM6Box', 'sectionM3Drainage'],
    scrollId: 'drainageM6Box',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
      const simToggle = document.getElementById('toggleSimulationLayer');
      if (simToggle && !simToggle.checked) {
        simToggle.checked = true;
        toggleSimLayer(true);
      }
      jumpToSimPeak();
      const m6Toggle = document.getElementById('toggleDrainageLoadingMode');
      if (m6Toggle && !m6Toggle.checked) {
        m6Toggle.checked = true;
        m6Toggle.dispatchEvent(new Event('change'));
      }
    },
    onAction: function () {
      const btnDrain = document.getElementById('btnDrainageModal');
      if (btnDrain) btnDrain.click();
    }
  },
  {
    num: '05',
    titleKey: 'guided_demo.s5_title',
    fallbackTitle: 'Safest Route Analysis',
    descKey: 'guided_demo.s5_desc',
    fallbackDesc: 'Compare M7 safest route navigation profiles between Origin (A) and Destination (B): Lowest Exposure, Shortest Distance, and Drainage-Informed routes, evaluating water depth exposure and impassable (>0.30m) road segments.',
    provenance: 'SAFEST ROUTE SCREENING · EXPERIMENTAL (M7)',
    actionKey: 'guided_demo.action_compare_routes',
    fallbackAction: 'Re-Compute Route Comparison',
    highlightIds: ['sectionM7RoutePlanner'],
    scrollId: 'sectionM7RoutePlanner',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
      const streetToggle = document.getElementById('toggleStreetNetwork');
      if (streetToggle && !streetToggle.checked) {
        streetToggle.checked = true;
        streetToggle.dispatchEvent(new Event('change'));
      }
      computeRouteAlternatives();
    },
    onAction: function () {
      computeRouteAlternatives();
    }
  },
  {
    num: '06',
    titleKey: 'guided_demo.s6_title',
    fallbackTitle: '3D Visualization',
    descKey: 'guided_demo.s6_desc',
    fallbackDesc: 'Switch to the M8 interactive WebGL 3D Terrain & Flood Viewer. Orbit and zoom across the vertically exaggerated Buffalo Bayou relief with draped M5 water surfaces and 3D stormwater conduit overlays.',
    provenance: '3D TERRAIN & DRAPED FLOOD · MODELLED (M8)',
    actionKey: 'guided_demo.action_reset_3d_cam',
    fallbackAction: 'Reset 3D Camera Orbit',
    highlightIds: ['hud3DControls'],
    scrollId: null,
    onEnter: function () {
      closeAllDemoModals();
      const tab3D = document.getElementById('tabView3D');
      if (tab3D) tab3D.click();
    },
    onAction: function () {
      const btnResetCam = document.getElementById('btnResetCamera3D');
      if (btnResetCam) btnResetCam.click();
    }
  },
  {
    num: '07',
    titleKey: 'guided_demo.s7_title',
    fallbackTitle: 'AI Surrogate',
    descKey: 'guided_demo.s7_desc',
    fallbackDesc: 'Toggle the M9 ML Surrogate Engine (HistGradientBoosting trained on synthetic M5 grids) for sub-second flood depth inference. Notice the mandatory SYNTHETIC SURROGATE warning banner and scientific provenance badges.',
    provenance: 'SYNTHETIC SURROGATE · UNVALIDATED (M9)',
    actionKey: 'guided_demo.action_switch_physics',
    fallbackAction: 'Toggle Screening / Surrogate',
    highlightIds: ['simEngineToggleRow', 'surrogateWarningBanner', 'sectionM5Simulation'],
    scrollId: 'sectionM5Simulation',
    onEnter: function () {
      closeAllDemoModals();
      ensure2DMapView();
      ensureSidebarExpanded();
      const simToggle = document.getElementById('toggleSimulationLayer');
      if (simToggle && !simToggle.checked) {
        simToggle.checked = true;
        toggleSimLayer(true);
      }
      jumpToSimPeak();
      setSimulationEngine('surrogate');
    },
    onAction: function () {
      const nextEngine = state.simEngine === 'surrogate' ? 'original' : 'surrogate';
      setSimulationEngine(nextEngine);
    }
  },
  {
    num: '08',
    titleKey: 'guided_demo.s8_title',
    fallbackTitle: 'Risk Information & Disclaimers',
    descKey: 'guided_demo.s8_desc',
    fallbackDesc: 'Review the Data Source & Quality Governance registry and M3 Validation Readiness ledger. Every dataset and model output preserves strict SYNTHETIC, MODELLED, ASSUMED, and UNVALIDATED guardrails.',
    provenance: 'SYNTHETIC · MODELLED · ASSUMED · UNVALIDATED',
    actionKey: 'guided_demo.action_open_governance',
    fallbackAction: 'Open Governance & Disclaimers Modal',
    highlightIds: ['statusBarContainer'],
    scrollId: null,
    onEnter: function () {
      ensure2DMapView();
      openQualityDisclaimersTab();
    },
    onAction: function () {
      openQualityDisclaimersTab();
    }
  }
];

let guidedDemoActive = false;
let guidedDemoStepIdx = 0;

function closeAllDemoModals() {
  ['qualityModalBackdrop', 'rainfallModalBackdrop', 'validationModalBackdrop', 'drainageModalBackdrop'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}

function ensure2DMapView() {
  const tab2D = document.getElementById('tabView2D');
  if (tab2D && !tab2D.classList.contains('active')) {
    tab2D.click();
  }
}

function ensureSidebarExpanded() {
  const sidebar = document.getElementById('mapSidebar');
  const openBtn = document.getElementById('btnOpenSidebar');
  if (sidebar && sidebar.classList.contains('collapsed')) {
    sidebar.classList.remove('collapsed');
    if (openBtn) openBtn.classList.remove('visible');
  }
}

function openQualityDisclaimersTab() {
  closeAllDemoModals();
  const modal = document.getElementById('qualityModalBackdrop');
  if (modal) {
    modal.style.display = 'flex';
    const tabBtns = document.querySelectorAll('#qualityModalBackdrop .modal-tabs .tab-btn');
    tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === 'tab-guardrails'));
    const panels = document.querySelectorAll('#qualityModalBackdrop .tab-panel');
    panels.forEach(p => p.classList.toggle('active', p.id === 'tab-guardrails'));
  }
}

function clearDemoHighlights() {
  document.querySelectorAll('.demo-focus-highlight').forEach(el => {
    el.classList.remove('demo-focus-highlight');
  });
}

function getDemoTranslation(key, fallback) {
  const dict = state.i18nDict && state.i18nDict[state.currentLang];
  if (dict) {
    const val = getNestedTranslation(dict, key);
    if (val) return val;
  }
  return fallback;
}

function renderGuidedDemoStep(executeStageEffects = true) {
  const stage = GUIDED_DEMO_STAGES[guidedDemoStepIdx];
  if (!stage) return;

  const numEl = document.getElementById('demoStepNum');
  const fracEl = document.getElementById('demoStepFraction');
  const titleEl = document.getElementById('demoStepTitle');
  const descEl = document.getElementById('demoStepDesc');
  const provEl = document.getElementById('demoProvenancePill');
  const fillEl = document.getElementById('demoProgressFill');
  const actionBtn = document.getElementById('btnDemoContextAction');
  const prevBtn = document.getElementById('btnDemoPrev');
  const nextBtn = document.getElementById('btnDemoNext');

  if (numEl) numEl.textContent = stage.num;
  if (fracEl) {
    const stepWord = getDemoTranslation('guided_demo.step_of', 'Step');
    fracEl.textContent = `${stepWord} ${guidedDemoStepIdx + 1} / ${GUIDED_DEMO_STAGES.length}`;
  }

  const translatedTitle = getDemoTranslation(stage.titleKey, stage.fallbackTitle);
  if (titleEl) titleEl.textContent = `${stage.num} — ${translatedTitle}`;

  const translatedDesc = getDemoTranslation(stage.descKey, stage.fallbackDesc);
  if (descEl) descEl.textContent = translatedDesc;

  if (provEl) provEl.textContent = stage.provenance;
  if (fillEl) {
    const pct = ((guidedDemoStepIdx + 1) / GUIDED_DEMO_STAGES.length) * 100;
    fillEl.style.width = `${pct}%`;
  }

  if (actionBtn) {
    actionBtn.textContent = getDemoTranslation(stage.actionKey, stage.fallbackAction);
  }

  if (prevBtn) prevBtn.disabled = guidedDemoStepIdx === 0;
  if (nextBtn) nextBtn.disabled = guidedDemoStepIdx === GUIDED_DEMO_STAGES.length - 1;

  // Update stage track dots
  const dots = document.querySelectorAll('#demoStageTrack .stage-step-dot');
  dots.forEach((dot, idx) => {
    dot.classList.toggle('active', idx === guidedDemoStepIdx);
    dot.classList.toggle('completed', idx < guidedDemoStepIdx);
    dot.setAttribute('aria-selected', idx === guidedDemoStepIdx ? 'true' : 'false');
  });

  if (executeStageEffects) {
    clearDemoHighlights();
    if (typeof stage.onEnter === 'function') {
      stage.onEnter();
    }
    if (Array.isArray(stage.highlightIds)) {
      stage.highlightIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('demo-focus-highlight');
      });
    }
    if (stage.scrollId) {
      const targetEl = document.getElementById(stage.scrollId);
      if (targetEl && typeof targetEl.scrollIntoView === 'function') {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }
}

function startGuidedDemoMode(startStep = 0) {
  guidedDemoActive = true;
  guidedDemoStepIdx = Math.max(0, Math.min(GUIDED_DEMO_STAGES.length - 1, startStep));
  document.body.classList.add('demo-mode-active');

  const bar = document.getElementById('guidedDemoBar');
  if (bar) bar.style.display = 'block';

  const launchBtn = document.getElementById('btnGuidedDemo');
  if (launchBtn) launchBtn.classList.add('active-demo');

  renderGuidedDemoStep(true);
}

function exitGuidedDemoMode() {
  guidedDemoActive = false;
  document.body.classList.remove('demo-mode-active');
  clearDemoHighlights();

  const bar = document.getElementById('guidedDemoBar');
  if (bar) bar.style.display = 'none';

  const launchBtn = document.getElementById('btnGuidedDemo');
  if (launchBtn) launchBtn.classList.remove('active-demo');
}

function initGuidedDemoControls() {
  const launchBtn = document.getElementById('btnGuidedDemo');
  const prevBtn = document.getElementById('btnDemoPrev');
  const nextBtn = document.getElementById('btnDemoNext');
  const exitBtn = document.getElementById('btnDemoExit');
  const actionBtn = document.getElementById('btnDemoContextAction');
  const dots = document.querySelectorAll('#demoStageTrack .stage-step-dot');

  if (launchBtn) {
    launchBtn.addEventListener('click', () => {
      if (guidedDemoActive) {
        exitGuidedDemoMode();
      } else {
        startGuidedDemoMode(0);
      }
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (guidedDemoStepIdx > 0) {
        guidedDemoStepIdx--;
        renderGuidedDemoStep(true);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (guidedDemoStepIdx < GUIDED_DEMO_STAGES.length - 1) {
        guidedDemoStepIdx++;
        renderGuidedDemoStep(true);
      }
    });
  }

  if (exitBtn) {
    exitBtn.addEventListener('click', () => {
      exitGuidedDemoMode();
    });
  }

  if (actionBtn) {
    actionBtn.addEventListener('click', () => {
      const stage = GUIDED_DEMO_STAGES[guidedDemoStepIdx];
      if (stage && typeof stage.onAction === 'function') {
        stage.onAction();
      }
    });
  }

  dots.forEach(dot => {
    dot.addEventListener('click', () => {
      const idx = parseInt(dot.dataset.step, 10);
      if (!Number.isNaN(idx)) {
        guidedDemoStepIdx = idx;
        renderGuidedDemoStep(true);
      }
    });
  });

  // Refresh Guided Demo text when language changes
  const langBtn = document.getElementById('btnLangToggle');
  if (langBtn) {
    langBtn.addEventListener('click', () => {
      setTimeout(() => {
        if (guidedDemoActive) {
          renderGuidedDemoStep(false);
        }
      }, 60);
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initGuidedDemoControls();
});





