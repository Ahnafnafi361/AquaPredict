const fs = require('fs');
const http = require('http');

async function main() {
  // 1. Get websocket URL for the AquaPredict page
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const pageTarget = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  
  if (!pageTarget) {
    console.error('Could not find AquaPredict page target in Chrome!');
    process.exit(1);
  }
  
  console.log(`Connecting to: ${pageTarget.title} (${pageTarget.webSocketDebuggerUrl})`);
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
  
  let msgId = 1;
  const pending = new Map();
  const consoleLogs = [];
  
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.consoleAPICalled') {
      const type = data.params.type;
      const text = data.params.args.map(a => a.value || JSON.stringify(a)).join(' ');
      consoleLogs.push({ type, text });
      console.log(`[Browser Console ${type.toUpperCase()}]: ${text}`);
    } else if (data.method === 'Log.entryAdded') {
      const entry = data.params.entry;
      consoleLogs.push({ type: entry.level, text: entry.text });
      console.log(`[Browser Log ${entry.level.toUpperCase()}]: ${entry.text}`);
    } else if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    }
  };
  
  ws.onopen = async () => {
    console.log('CDP connection established.');
    
    // Enable Runtime and Log
    await send('Runtime.enable');
    await send('Log.enable');
    await send('DOM.enable');
    
    // Evaluate page inspection
    const evalScript = `
      (() => {
        // 1. Basic Title & Header
        const title = document.title;
        const brandTitle = document.querySelector('.brand-title')?.textContent?.trim();
        
        // 2. Leaflet Map status
        const mapContainer = document.getElementById('map');
        const hasLeaflet = typeof L !== 'undefined';
        
        // Check Leaflet DOM layers
        const overlayImages = Array.from(document.querySelectorAll('.leaflet-image-layer')).map(img => ({
          src: img.src,
          display: img.style.display,
          opacity: img.style.opacity,
          bounds: [img.getBoundingClientRect().width, img.getBoundingClientRect().height]
        }));
        
        // Count rendered vector elements (SVG paths and circles)
        const svgPaths = document.querySelectorAll('.leaflet-overlay-pane svg path').length;
        const svgCircles = document.querySelectorAll('.leaflet-overlay-pane svg circle, .leaflet-overlay-pane svg path[d*="A"]').length;
        
        // 3. Layer Count Badges
        const countPipes = document.getElementById('countGravityMains')?.textContent?.trim();
        const countInlets = document.getElementById('countInlets')?.textContent?.trim();
        const countManholes = document.getElementById('countManholes')?.textContent?.trim();
        const countDischarge = document.getElementById('countDischarge')?.textContent?.trim();
        
        // 4. Data Quality Modal Elements
        const modal = document.getElementById('qualityModalBackdrop');
        const modalInitialDisplay = modal ? window.getComputedStyle(modal).display : 'missing';
        
        // 5. Test DEM Elevation Cursor Logic on Map center
        const bottomHud = document.getElementById('bottomHud');
        const elevationChipText = document.getElementById('cursorElevationText')?.textContent?.trim();
        const coordsText = document.getElementById('cursorCoordsText')?.textContent?.trim();
        
        // Check if state is accessible or window
        const stateExists = typeof state !== 'undefined';
        let stateSummary = null;
        if (stateExists) {
          stateSummary = {
            hasMap: !!state.map,
            layers: {
              pilotBoundary: !!state.layers.pilotBoundary,
              demTerrain: !!state.layers.demTerrain,
              demHillshade: !!state.layers.demHillshade,
              gravityMains: !!state.layers.gravityMains,
              inlets: !!state.layers.inlets,
              manholes: !!state.layers.manholes,
              discharge: !!state.layers.discharge
            },
            demMode: state.demMode,
            demOpacity: state.demOpacity,
            hasGrid: !!state.demGrid,
            hasQualityData: !!state.qualityData
          };
        }
        
        return {
          title,
          brandTitle,
          hasLeaflet,
          overlayImages,
          svgPaths,
          svgCircles,
          counts: {
            pipes: countPipes,
            inlets: countInlets,
            manholes: countManholes,
            discharge: countDischarge
          },
          modalInitialDisplay,
          elevationChipText,
          coordsText,
          stateSummary
        };
      })()
    `;
    
    const result = await send('Runtime.evaluate', { expression: evalScript, returnByValue: true });
    console.log('\n--- LIVE PAGE EVALUATION RESULT ---');
    console.log(JSON.stringify(result.value, null, 2));
    
    // Test Layer Toggling via DOM events
    console.log('\n--- TESTING TOGGLE CONTROLS ---');
    const toggleTestScript = `
      (() => {
        const togglePipes = document.getElementById('toggleGravityMains');
        const toggleDem = document.getElementById('toggleDemTerrain');
        const btnHillshade = document.getElementById('btnModeHillshade');
        const btnModal = document.getElementById('btnQualityModal');
        const modal = document.getElementById('qualityModalBackdrop');
        const closeModal = document.getElementById('closeQualityModalBtn');
        
        const results = {};
        
        // 1. Toggle Pipes off
        togglePipes.click();
        results.pipesAfterToggleOff = togglePipes.checked;
        
        // Toggle Pipes back on
        togglePipes.click();
        results.pipesAfterToggleOn = togglePipes.checked;
        
        // 2. Switch to Hillshade
        btnHillshade.click();
        results.demModeAfterHillshade = typeof state !== 'undefined' ? state.demMode : null;
        
        // 3. Open Modal
        btnModal.click();
        results.modalDisplayAfterClick = window.getComputedStyle(modal).display;
        
        // Check completeness cards in modal
        const compCards = document.querySelectorAll('.comp-card').length;
        results.completenessCardsRendered = compCards;
        
        // Close modal
        closeModal.click();
        results.modalDisplayAfterClose = window.getComputedStyle(modal).display;
        
        return results;
      })()
    `;
    
    const toggleResult = await send('Runtime.evaluate', { expression: toggleTestScript, returnByValue: true });
    console.log(JSON.stringify(toggleResult.value, null, 2));
    
    // Capture Screenshot to verify visual quality
    const screenshot = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(screenshot.data, 'base64');
    fs.writeFileSync('c:\\Users\\ASUS\\Desktop\\AquaPredict\\scripts\\live_verification_screenshot.png', buffer);
    console.log('\nSaved live verification screenshot to scripts/live_verification_screenshot.png');
    
    ws.close();
    process.exit(0);
  };
  
  ws.onerror = (err) => {
    console.error('CDP WebSocket error:', err);
    process.exit(1);
  };
}

main().catch(err => {
  console.error('Test script failure:', err);
  process.exit(1);
});
