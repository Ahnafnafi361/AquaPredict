/**
 * AquaPredict M8 - 3D Terrain & Flood Simulation Viewer
 * Implements interactive 3D topography mesh, M5 water surface draping,
 * M6 drainage network lines, vertical exaggeration control, FPS performance
 * tracking with fallback, and camera orbit/zoom/pan controls.
 */

(function () {
  'use strict';

  // Strict Pilot Bounding Box (NOAA DEM Verified Extent)
  const PILOT_BBOX = {
    west: -95.3750,
    south: 29.7560,
    east: -95.3650,
    north: 29.7650
  };

  // 3D Scene Dimensions (Aspect ratio matching 0.0100 lon x 0.0090 lat ~ 100 x 90 units)
  const PLANE_WIDTH = 100;
  const PLANE_DEPTH = 90;
  const ELEV_BASE_SCALE = 0.5; // Scale factor from real meters to 3D world units

  // Performance Monitoring Constants
  const FPS_WARNING_THRESHOLD = 20; // Framerate warning threshold in FPS
  const FPS_SAMPLE_WINDOW = 60;     // Number of frames to average

  // Color Stops for Hypsometric Elevation Ramp (matching prepare_m0_data.py)
  // 0.00 -> Deep Bayou Cyan/Teal (12, 74, 110)
  // 0.25 -> Riparian Floodplain (22, 101, 52)
  // 0.50 -> Transition Plain (161, 138, 28)
  // 0.75 -> Urban Terrace (202, 108, 22)
  // 1.00 -> Downtown Crest (185, 28, 28)
  const ELEV_COLOR_STOPS = [
    { stop: 0.00, r: 12 / 255, g: 74 / 255, b: 110 / 255 },
    { stop: 0.25, r: 22 / 255, g: 101 / 255, b: 52 / 255 },
    { stop: 0.50, r: 161 / 255, g: 138 / 255, b: 28 / 255 },
    { stop: 0.75, r: 202 / 255, g: 108 / 255, b: 22 / 255 },
    { stop: 1.00, r: 185 / 255, g: 28 / 255, b: 28 / 255 }
  ];

  // Flood Depth Legend Colors (matching 2D SIM-01 5-class legend)
  const FLOOD_COLORS = {
    shallow: { r: 147 / 255, g: 197 / 255, b: 253 / 255 }, // <= 0.05m (#93c5fd)
    moderate: { r: 59 / 255, g: 130 / 255, b: 246 / 255 }, // 0.05-0.20m (#3b82f6)
    deep: { r: 29 / 255, g: 78 / 255, b: 216 / 255 },     // 0.20-0.50m (#1d4ed8)
    veryDeep: { r: 30 / 255, g: 27 / 255, b: 75 / 255 }   // > 0.50m (#1e1b4b)
  };

  // Drainage Loading Status Colors (matching M6)
  const DRAINAGE_COLORS = {
    NORMAL: 0x38bdf8,            // Sky blue
    HIGH_LOADING: 0xfbbf24,      // Amber
    CAPACITY_EXCEEDED: 0xef4444, // Red
    DISCONNECTED: 0xa855f7,      // Purple
    INSUFFICIENT_DATA: 0x64748b  // Slate
  };

  // 3D Viewer Singleton
  const viewer3D = {
    isInitialized: false,
    isActive: false,
    webglSupported: false,
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    container: null,
    
    // Meshes and Groups
    terrainMesh: null,
    floodMesh: null,
    drainageGroup: null,
    lightsGroup: null,

    // Heightmap Data
    heightmap: null,
    gridRows: 0,
    gridCols: 0,
    minElev: 0,
    maxElev: 0,
    
    // Viewer Settings
    verticalExaggeration: 3.0,
    showTerrain: true,
    showFlood: true,
    showDrainage: true,

    // Performance & FPS Tracking
    fps: 60,
    fpsHistory: [],
    lastFrameTime: performance.now(),
    frameCount: 0,
    fpsLowConsecutiveCount: 0,
    fpsWarnDismissed: false,
    animFrameId: null,

    /**
     * Check if WebGL is available in the browser
     */
    checkWebGL: function () {
      try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        this.webglSupported = !!(window.WebGLRenderingContext && gl);
        return this.webglSupported;
      } catch (e) {
        this.webglSupported = false;
        return false;
      }
    },

    /**
     * Initialize Three.js Scene, Camera, Controls, Lights
     */
    init: async function (containerId) {
      if (this.isInitialized) return true;

      this.container = document.getElementById(containerId);
      if (!this.container) {
        console.error('3D Viewer: Container #' + containerId + ' not found');
        return false;
      }

      // 1. Verify WebGL Availability
      if (!this.checkWebGL() || typeof THREE === 'undefined') {
        console.warn('3D Viewer: WebGL or Three.js is not available. Displaying fallback.');
        this.showWebGLFallback(true);
        return false;
      }

      const width = this.container.clientWidth || window.innerWidth;
      const height = this.container.clientHeight || (window.innerHeight - 70);

      // 2. Setup Three.js Scene
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0x0b1120); // Dark theme slate background
      this.scene.fog = new THREE.FogExp2(0x0b1120, 0.0035);

      // 3. Setup Camera
      this.camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 2000);
      this.setDefaultCameraPosition();

      // 4. Setup Renderer
      try {
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.renderer.shadowMap.enabled = false; // Disable heavy shadows for FPS
        this.container.appendChild(this.renderer.domElement);
      } catch (e) {
        console.error('3D Viewer: Failed to create WebGL context:', e);
        this.showWebGLFallback(true);
        return false;
      }

      // 5. Setup OrbitControls
      if (THREE.OrbitControls) {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.screenSpacePanning = false;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.05; // Prevent camera from going beneath terrain
        this.controls.minDistance = 15;
        this.controls.maxDistance = 350;
        this.controls.target.set(0, 0, 0);
      }

      // 6. Setup Lighting (matching 2D hillshade light: NW 315 deg, 45 deg altitude)
      this.setupLighting();

      // 7. Bind Window Resize
      window.addEventListener('resize', () => this.onWindowResize());

      // 8. Load Terrain Heightmap
      await this.loadTerrainHeightmap();

      // 9. Initial Build of Flood and Drainage
      this.buildDrainageLines();
      this.updateFloodSurface();

      this.isInitialized = true;
      console.log('3D Viewer: Initialized successfully with resolution ' + this.gridCols + 'x' + this.gridRows);
      return true;
    },

    /**
     * Set default angled isometric camera position overlooking Buffalo Bayou
     */
    setDefaultCameraPosition: function () {
      if (!this.camera) return;
      // Position looking from South-West towards North-East
      this.camera.position.set(0, -95, 75);
      this.camera.lookAt(0, 0, 0);
      if (this.controls) {
        this.controls.target.set(0, 0, 0);
        this.controls.update();
      }
    },

    /**
     * Setup directional and ambient lighting
     */
    setupLighting: function () {
      this.lightsGroup = new THREE.Group();

      // Ambient light for base visibility
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.70);
      this.lightsGroup.add(ambientLight);

      // Main directional light (NW 315 deg, 45 deg elevation matching DEM hillshade)
      const dirLight = new THREE.DirectionalLight(0xffffff, 0.75);
      const azimuthRad = (315 - 90) * (Math.PI / 180);
      const dist = 150;
      dirLight.position.set(
        Math.cos(azimuthRad) * dist,
        Math.sin(azimuthRad) * dist,
        dist
      );
      this.lightsGroup.add(dirLight);

      // Subtle fill light from South
      const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.25);
      fillLight.position.set(0, -100, 40);
      this.lightsGroup.add(fillLight);

      this.scene.add(this.lightsGroup);
    },

    /**
     * Fetch downsampled heightmap from backend endpoint
     */
    loadTerrainHeightmap: async function () {
      try {
        let res = await fetch('/api/terrain/heightmap?res=256');
        if (!res.ok) {
          console.warn('3D Viewer: /api/terrain/heightmap returned ' + res.status + ', trying cached static JSON');
          res = await fetch('/data/terrain_heightmap_256.json');
        }
        const data = await res.json();
        
        if (data.status === 'UNAVAILABLE' || !data.elevations) {
          console.warn('3D Viewer: Heightmap data is UNAVAILABLE:', data.error);
          this.setFrameStatus('DEM UNAVAILABLE', false);
          return;
        }

        this.heightmap = data;
        this.gridRows = data.dimensions.rows;
        this.gridCols = data.dimensions.cols;
        this.minElev = data.min_elev_m;
        this.maxElev = data.max_elev_m;

        this.buildTerrainMesh();
      } catch (e) {
        console.error('3D Viewer: Failed to load heightmap:', e);
        this.setFrameStatus('LOAD ERROR', false);
      }
    },

    /**
     * Interpolate color along hypsometric elevation stops
     */
    getElevationColor: function (normElev) {
      const t = Math.max(0, Math.min(1, normElev));
      let c0 = ELEV_COLOR_STOPS[0];
      let c1 = ELEV_COLOR_STOPS[ELEV_COLOR_STOPS.length - 1];

      for (let i = 0; i < ELEV_COLOR_STOPS.length - 1; i++) {
        if (t >= ELEV_COLOR_STOPS[i].stop && t <= ELEV_COLOR_STOPS[i + 1].stop) {
          c0 = ELEV_COLOR_STOPS[i];
          c1 = ELEV_COLOR_STOPS[i + 1];
          break;
        }
      }

      const span = (c1.stop - c0.stop) || 1e-6;
      const frac = (t - c0.stop) / span;

      return {
        r: c0.r + frac * (c1.r - c0.r),
        g: c0.g + frac * (c1.g - c0.g),
        b: c0.b + frac * (c1.b - c0.b)
      };
    },

    /**
     * Build interactive 3D terrain mesh from heightmap
     */
    buildTerrainMesh: function () {
      if (!this.heightmap || !this.heightmap.elevations) return;

      if (this.terrainMesh) {
        this.scene.remove(this.terrainMesh);
        if (this.terrainMesh.geometry) this.terrainMesh.geometry.dispose();
        if (this.terrainMesh.material) this.terrainMesh.material.dispose();
      }

      const cols = this.gridCols;
      const rows = this.gridRows;
      const elevations = this.heightmap.elevations;
      const elevSpan = (this.maxElev - this.minElev) || 1;

      // Plane geometry with (cols, rows) vertices
      const geometry = new THREE.PlaneGeometry(PLANE_WIDTH, PLANE_DEPTH, cols - 1, rows - 1);
      const pos = geometry.attributes.position;
      const count = pos.count;

      // Create vertex color attribute
      const colors = new Float32Array(count * 3);

      // In Three.js PlaneGeometry, vertices run left-to-right (cols), top-to-bottom (rows)
      for (let i = 0; i < count; i++) {
        const c = i % cols;
        const r = Math.floor(i / cols);

        // Heightmap is indexed row 0 at North (top), row N at South (bottom)
        const elevVal = (elevations[r] && elevations[r][c] !== null && elevations[r][c] !== undefined)
          ? elevations[r][c]
          : this.minElev;

        // Displace Z along elevation
        pos.setZ(i, (elevVal - this.minElev) * ELEV_BASE_SCALE * this.verticalExaggeration);

        // Color based on elevation stop
        const norm = (elevVal - this.minElev) / elevSpan;
        const rgb = this.getElevationColor(norm);

        colors[i * 3 + 0] = rgb.r;
        colors[i * 3 + 1] = rgb.g;
        colors[i * 3 + 2] = rgb.b;
      }

      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geometry.computeVertexNormals();

      const material = new THREE.MeshLambertMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        wireframe: false
      });

      this.terrainMesh = new THREE.Mesh(geometry, material);
      this.terrainMesh.visible = this.showTerrain;
      this.scene.add(this.terrainMesh);

      // Also rebuild flood mesh to match newly updated terrain geometry
      this.buildFloodMesh();
    },

    /**
     * Build 3D Flood Surface Mesh (Plane overlaid over terrain)
     */
    buildFloodMesh: function () {
      if (!this.heightmap || !this.heightmap.elevations) return;

      if (this.floodMesh) {
        this.scene.remove(this.floodMesh);
        if (this.floodMesh.geometry) this.floodMesh.geometry.dispose();
        if (this.floodMesh.material) this.floodMesh.material.dispose();
      }

      const cols = this.gridCols;
      const rows = this.gridRows;

      const geometry = new THREE.PlaneGeometry(PLANE_WIDTH, PLANE_DEPTH, cols - 1, rows - 1);
      const pos = geometry.attributes.position;
      const colors = new Float32Array(pos.count * 3);

      // Initialize all colors to transparent blue
      for (let i = 0; i < pos.count; i++) {
        colors[i * 3 + 0] = FLOOD_COLORS.shallow.r;
        colors[i * 3 + 1] = FLOOD_COLORS.shallow.g;
        colors[i * 3 + 2] = FLOOD_COLORS.shallow.b;
      }

      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

      const material = new THREE.MeshPhongMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.88,
        shininess: 90,
        specular: 0x60a5fa,
        side: THREE.DoubleSide,
        depthWrite: false
      });

      this.floodMesh = new THREE.Mesh(geometry, material);
      this.floodMesh.visible = this.showFlood;
      this.scene.add(this.floodMesh);

      this.updateFloodSurface();
    },

    /**
     * Update 3D flood surface from current M5 simulation frame
     */
    updateFloodSurface: function () {
      if (!this.floodMesh || !this.heightmap) return;

      const state = window.state || {};
      const scenarios = state.simScenarios;
      const presetKey = 'preset_' + (state.simActivePreset || 50) + 'mm';
      const stepIdx = state.simActiveStepIdx || 0;

      // Update HUD frame readout
      const frameReadout = document.getElementById('hud3DFrameReadout');
      if (frameReadout) {
        frameReadout.textContent = (state.simActivePreset || 50) + 'mm Preset · Step ' + stepIdx;
      }

      if (!scenarios || !scenarios.presets || !scenarios.presets[presetKey]) {
        this.setFrameStatus('SIM UNAVAILABLE', false);
        this.floodMesh.visible = false;
        return;
      }

      const presetData = scenarios.presets[presetKey];
      const ts = (state.simEngine === 'surrogate' && state.surrogateActiveFrame) 
        ? state.surrogateActiveFrame 
        : (presetData.timesteps ? presetData.timesteps[stepIdx] : null);

      if (!ts || !ts.sparse_depths) {
        this.setFrameStatus('FRAME UNAVAILABLE', false);
        this.floodMesh.visible = false;
        return;
      }

      // Update HUD minute readout if available
      const minVal = ts.time_minutes !== undefined ? ts.time_minutes : (ts.minute !== undefined ? ts.minute : stepIdx * 5);
      if (frameReadout) {
        const engineTag = (state.simEngine === 'surrogate') ? ' [SURROGATE]' : '';
        frameReadout.textContent = (state.simActivePreset || 50) + 'mm · Minute ' + minVal + engineTag;
      }
      this.setFrameStatus('SYNCHRONIZED', true);

      // Build depth lookup from sparse_depths (100x100 simulation grid)
      // M5 simulation grid is 100x100. Heightmap default is 256x256.
      // We map 3D terrain (r, c) to 100x100 simulation grid coordinates.
      const simCols = 100;
      const simRows = 100;
      const depthMap = new Map();

      if (Array.isArray(ts.sparse_depths)) {
        for (let i = 0; i < ts.sparse_depths.length; i++) {
          const item = ts.sparse_depths[i];
          if (item && item.length >= 2) {
            depthMap.set(item[0], item[1]);
          }
        }
      }

      const cols = this.gridCols;
      const rows = this.gridRows;
      const elevations = this.heightmap.elevations;
      const pos = this.floodMesh.geometry.attributes.position;
      const colors = this.floodMesh.geometry.attributes.color;
      const count = pos.count;

      const Z_OFFSET = 0.05; // Slight elevation offset above terrain surface to eliminate z-fighting

      let wetCount = 0;

      for (let i = 0; i < count; i++) {
        const c = i % cols;
        const r = Math.floor(i / cols);

        // Map heightmap coordinate (r, c) to 100x100 simulation cell
        const simC = Math.floor((c / (cols - 1)) * (simCols - 1));
        const simR = Math.floor((r / (rows - 1)) * (simRows - 1));
        const simFlatIdx = simR * simCols + simC;

        const depth = depthMap.get(simFlatIdx) || 0.0;
        const baseElev = (elevations[r] && elevations[r][c] !== null) ? elevations[r][c] : this.minElev;

        if (depth > 0.0) {
          wetCount++;
          // Water surface is terrain elevation + water depth
          const waterZ = (baseElev - this.minElev + depth) * ELEV_BASE_SCALE * this.verticalExaggeration + Z_OFFSET;
          pos.setZ(i, waterZ);

          // Assign depth color based on SIM-01 classes
          let color = FLOOD_COLORS.shallow;
          if (depth <= 0.05) {
            color = FLOOD_COLORS.shallow;
          } else if (depth <= 0.20) {
            color = FLOOD_COLORS.moderate;
          } else if (depth <= 0.50) {
            color = FLOOD_COLORS.deep;
          } else {
            color = FLOOD_COLORS.veryDeep;
          }

          colors.setXYZ(i, color.r, color.g, color.b);
        } else {
          // Dry cell: Hide by pushing slightly below the terrain surface
          const dryZ = (baseElev - this.minElev) * ELEV_BASE_SCALE * this.verticalExaggeration - 0.2;
          pos.setZ(i, dryZ);
          colors.setXYZ(i, FLOOD_COLORS.shallow.r, FLOOD_COLORS.shallow.g, FLOOD_COLORS.shallow.b);
        }
      }

      pos.needsUpdate = true;
      colors.needsUpdate = true;
      this.floodMesh.geometry.computeVertexNormals();
      this.floodMesh.visible = this.showFlood && (wetCount > 0);
    },

    /**
     * Convert WGS84 geographic coordinates [lon, lat] to 3D world space [x, y]
     */
    geoTo3D: function (lon, lat) {
      const west = PILOT_BBOX.west;
      const east = PILOT_BBOX.east;
      const south = PILOT_BBOX.south;
      const north = PILOT_BBOX.north;

      const normX = (lon - west) / (east - west);
      const normY = (lat - south) / (north - south);

      const x = (normX - 0.5) * PLANE_WIDTH;
      // In Three.js plane, Y is South -> North
      const y = (normY - 0.5) * PLANE_DEPTH;

      return { x: x, y: y, normX: normX, normY: normY };
    },

    /**
     * Sample ground elevation at normalized coordinate
     */
    sampleElevationAt: function (normX, normY) {
      if (!this.heightmap || !this.heightmap.elevations) return this.minElev;
      const c = Math.max(0, Math.min(this.gridCols - 1, Math.round(normX * (this.gridCols - 1))));
      // Heightmap row 0 is North (top), so invert normY
      const r = Math.max(0, Math.min(this.gridRows - 1, Math.round((1 - normY) * (this.gridRows - 1))));
      const val = this.heightmap.elevations[r]?.[c];
      return val !== null && val !== undefined ? val : this.minElev;
    },

    /**
     * Build 3D Drainage Network Lines
     */
    buildDrainageLines: function () {
      if (!this.scene) return;
      if (this.drainageGroup) {
        this.scene.remove(this.drainageGroup);
      }
      this.drainageGroup = new THREE.Group();

      const state = window.state || {};
      const m6Data = state.m6Data;
      if (!m6Data || !m6Data.conduits) {
        this.scene.add(this.drainageGroup);
        return;
      }

      const conduits = Array.isArray(m6Data.conduits)
        ? m6Data.conduits
        : Object.values(m6Data.conduits || {});
      const simStep = (state.simScenarios && state.simScenarios.presets?.['preset_' + (state.simActivePreset || 50) + 'mm']?.timesteps?.[state.simActiveStepIdx || 0]) || null;

      for (let i = 0; i < conduits.length; i++) {
        const c = conduits[i];
        if (!c.coordinates || c.coordinates.length < 2) continue;

        // Determine loading status color
        let statusColor = DRAINAGE_COLORS.NORMAL;
        if (c.connectivity_type === 'dangling_boundary' && !c.reaches_bayou_outfall) {
          statusColor = DRAINAGE_COLORS.DISCONNECTED;
        } else if (!c.capacity_m3s || c.capacity_m3s <= 0) {
          statusColor = DRAINAGE_COLORS.INSUFFICIENT_DATA;
        } else if (simStep) {
          const qCond = (c.contributing_inlet_fraction !== undefined ? c.contributing_inlet_fraction : 0.0) * (simStep.inflow_rate_per_inlet_m3s || 0.0);
          const ratio = qCond / c.capacity_m3s;
          if (ratio > 1.0) {
            statusColor = DRAINAGE_COLORS.CAPACITY_EXCEEDED;
          } else if (ratio >= 0.70) {
            statusColor = DRAINAGE_COLORS.HIGH_LOADING;
          }
        }

        const points = [];
        const LINE_Z_OFFSET = 0.12; // Draped slightly above terrain surface for high visibility

        for (let j = 0; j < c.coordinates.length; j++) {
          const pt = c.coordinates[j];
          const coord3D = this.geoTo3D(pt[0], pt[1]);
          const groundElev = this.sampleElevationAt(coord3D.normX, coord3D.normY);
          const z = (groundElev - this.minElev) * ELEV_BASE_SCALE * this.verticalExaggeration + LINE_Z_OFFSET;
          points.push(new THREE.Vector3(coord3D.x, coord3D.y, z));
        }

        const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
        const lineMat = new THREE.LineBasicMaterial({
          color: statusColor,
          linewidth: 2,
          transparent: true,
          opacity: 0.90
        });

        const line = new THREE.Line(lineGeom, lineMat);
        this.drainageGroup.add(line);
      }

      this.drainageGroup.visible = this.showDrainage;
      this.scene.add(this.drainageGroup);
    },

    /**
     * Update Vertical Exaggeration factor
     */
    setVerticalExaggeration: function (factor) {
      this.verticalExaggeration = Math.max(1.0, Math.min(10.0, parseFloat(factor) || 3.0));
      
      const valLabel = document.getElementById('valVertExaggeration');
      if (valLabel) {
        valLabel.textContent = this.verticalExaggeration.toFixed(1) + '×';
      }

      // Recompute vertex Z coordinates on terrain and flood meshes
      if (this.terrainMesh && this.heightmap) {
        this.buildTerrainMesh();
      }
      if (this.drainageGroup) {
        this.buildDrainageLines();
      }
    },

    /**
     * Set HUD Frame Status Pill
     */
    setFrameStatus: function (text, isOk) {
      const pill = document.getElementById('hud3DFrameStatus');
      if (pill) {
        pill.textContent = text;
        pill.className = 'badge-status-pill ' + (isOk ? 'pill-ready' : 'pill-unavailable');
      }
    },

    /**
     * Display or hide WebGL Fallback Banner
     */
    showWebGLFallback: function (show) {
      const banner = document.getElementById('webglFallbackBanner');
      const controls = document.getElementById('hud3DControls');
      if (banner) banner.style.display = show ? 'flex' : 'none';
      if (controls) controls.style.display = show ? 'none' : 'block';
    },

    /**
     * Window resize handler
     */
    onWindowResize: function () {
      if (!this.isActive || !this.renderer || !this.camera || !this.container) return;
      const width = this.container.clientWidth;
      const height = this.container.clientHeight;
      if (width === 0 || height === 0) return;

      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(width, height);
    },

    /**
     * Main 3D Render & Animation Loop with FPS calculation
     */
    renderLoop: function (timestamp) {
      if (!this.isActive) return;

      this.animFrameId = requestAnimationFrame((t) => this.renderLoop(t));

      // Calculate Real-Time Rendering Framerate
      const delta = timestamp - this.lastFrameTime;
      this.lastFrameTime = timestamp;

      if (delta > 0) {
        const instantFps = 1000 / delta;
        this.fpsHistory.push(instantFps);
        if (this.fpsHistory.length > FPS_SAMPLE_WINDOW) {
          this.fpsHistory.shift();
        }

        // Rolling average FPS
        const sum = this.fpsHistory.reduce((a, b) => a + b, 0);
        this.fps = Math.round(sum / this.fpsHistory.length);

        // Update FPS Readout every 15 frames to prevent UI thrashing
        this.frameCount++;
        if (this.frameCount % 15 === 0) {
          this.updateFpsReadout(this.fps);
        }

        // Check Performance Threshold (Threshold = 20 FPS)
        if (this.fps < FPS_WARNING_THRESHOLD && this.fpsHistory.length >= 30) {
          this.fpsLowConsecutiveCount++;
          if (this.fpsLowConsecutiveCount > 60 && !this.fpsWarnDismissed) {
            this.showFpsWarning(true, this.fps);
          }
        } else {
          this.fpsLowConsecutiveCount = 0;
        }
      }

      // Update OrbitControls damping
      if (this.controls) {
        this.controls.update();
      }

      // Render Scene
      if (this.renderer && this.scene && this.camera) {
        this.renderer.render(this.scene, this.camera);
      }
    },

    /**
     * Update FPS badge and dot in HUD
     */
    updateFpsReadout: function (fpsVal) {
      const fpsText = document.getElementById('fpsVal');
      const fpsDot = document.getElementById('fpsDot');
      if (fpsText) fpsText.textContent = fpsVal + ' FPS';
      if (fpsDot) {
        if (fpsVal >= 45) {
          fpsDot.style.background = '#10b981'; // Green
        } else if (fpsVal >= 25) {
          fpsDot.style.background = '#fbbf24'; // Amber
        } else {
          fpsDot.style.background = '#ef4444'; // Red
        }
      }
    },

    /**
     * Show low framerate performance advisory card
     */
    showFpsWarning: function (show, fps) {
      const card = document.getElementById('fpsWarningCard');
      const val = document.getElementById('fpsWarnVal');
      if (val) val.textContent = fps;
      if (card) card.style.display = show ? 'block' : 'none';
    },

    /**
     * Activate 3D Viewport (called when 3D tab selected)
     */
    activate: async function () {
      this.isActive = true;
      const view3D = document.getElementById('view3DContainer');
      const mapEl = document.getElementById('map');
      
      if (view3D) view3D.style.display = 'block';
      if (mapEl) mapEl.style.display = 'none';

      // Initialize on first activation if not yet ready
      if (!this.isInitialized) {
        await this.init('threeCanvasContainer');
      } else {
        this.onWindowResize();
        this.updateFloodSurface();
        this.buildDrainageLines();
      }

      // Start animation loop
      this.lastFrameTime = performance.now();
      if (!this.animFrameId) {
        this.animFrameId = requestAnimationFrame((t) => this.renderLoop(t));
      }
    },

    /**
     * Deactivate 3D Viewport (returns to 2D Map)
     */
    deactivate: function () {
      this.isActive = false;
      const view3D = document.getElementById('view3DContainer');
      const mapEl = document.getElementById('map');

      if (view3D) view3D.style.display = 'none';
      if (mapEl) mapEl.style.display = 'block';

      // Stop animation loop to save CPU/GPU resources
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
      }

      // Invalidate 2D map size so Leaflet renders properly
      if (window.state && window.state.map) {
        setTimeout(() => window.state.map.invalidateSize(), 50);
      }
    }
  };

  // Expose to global window
  window.viewer3D = viewer3D;

})();
