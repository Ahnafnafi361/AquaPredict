const fs = require('fs');

async function main() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  
  if (!page) {
    console.error('Page target not found!');
    process.exit(1);
  }
  
  console.log(`Connecting to: ${page.title}`);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  
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
    console.log('CDP connected. Reloading page...');
    await send('Runtime.enable');
    await send('Log.enable');
    await send('Page.reload');
    
    // Wait 2.5s for page reload and layer loading
    await new Promise(r => setTimeout(r, 2500));
    
    // 1. Evaluate M1 initialization and DOM
    const checkScript = `
      (() => {
        const toggleSusc = document.getElementById('toggleSusceptibility');
        const suscSubcontrols = document.getElementById('suscSubcontrols');
        const compositeBtn = document.getElementById('btnModeComposite');
        const depBtn = document.getElementById('btnModeDepressions');
        const proxBtn = document.getElementById('btnModeInletProx');
        
        const hasSuscLayer = !!state.layers.susceptibility;
        const hasDepLayer = !!state.layers.depressions;
        const hasProxLayer = !!state.layers.inletProximity;
        const hasSuscGrid = !!state.suscGrid;
        
        // Count active map layers
        const isSuscOnMap = state.map.hasLayer(state.layers.susceptibility);
        const isPipesOnMap = state.map.hasLayer(state.layers.gravityMains);
        const isInletsOnMap = state.map.hasLayer(state.layers.inlets);
        
        // Test simulation of mousemove over pilot center (lat ~ 29.7605, lng ~ -95.3700)
        onMapMouseMove({ latlng: { lat: 29.7605, lng: -95.3700 } });
        const centerElevText = document.getElementById('cursorElevationText')?.textContent?.trim();
        const centerSuscText = document.getElementById('cursorSuscText')?.textContent?.trim();
        
        // Test simulation of mousemove outside pilot (lat ~ 29.7500, lng ~ -95.3800)
        onMapMouseMove({ latlng: { lat: 29.7500, lng: -95.3800 } });
        const outsideSuscText = document.getElementById('cursorSuscText')?.textContent?.trim();
        
        // Reset to center
        onMapMouseMove({ latlng: { lat: 29.7605, lng: -95.3700 } });
        
        return {
          toggleSuscChecked: toggleSusc ? toggleSusc.checked : null,
          hasSuscLayer,
          hasDepLayer,
          hasProxLayer,
          hasSuscGrid,
          isSuscOnMap,
          isPipesOnMap,
          isInletsOnMap,
          centerElevText,
          centerSuscText,
          outsideSuscText
        };
      })()
    `;
    
    const checkRes = await send('Runtime.evaluate', { expression: checkScript, returnByValue: true });
    console.log('\n--- M1 RUNTIME VERIFICATION ---');
    console.log(JSON.stringify(checkRes.result.value, null, 2));
    
    // 2. Capture screenshot of M1 Susceptibility Map View
    const shot1 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('c:\\Users\\ASUS\\Desktop\\AquaPredict\\scripts\\m1_susceptibility_screenshot.png', Buffer.from(shot1.data, 'base64'));
    console.log('\nSaved map screenshot to scripts/m1_susceptibility_screenshot.png');
    
    // 3. Open Modal and switch to Tab 4 (M1 Susceptibility Model)
    const modalScript = `
      (() => {
        document.getElementById('btnQualityModal').click();
        const tab4Btn = document.querySelector('.modal-tabs .tab-btn[data-tab="tab-m1-methodology"]');
        if (tab4Btn) tab4Btn.click();
        const panel4 = document.getElementById('tab-m1-methodology');
        return {
          modalVisible: window.getComputedStyle(document.getElementById('qualityModalBackdrop')).display,
          panel4Active: panel4.classList.contains('active'),
          panel4CardsCount: panel4.querySelectorAll('.lineage-card').length
        };
      })()
    `;
    const modalRes = await send('Runtime.evaluate', { expression: modalScript, returnByValue: true });
    console.log('\n--- MODAL TAB 4 VERIFICATION ---');
    console.log(JSON.stringify(modalRes.result.value, null, 2));
    
    // 4. Capture screenshot of Modal Tab 4
    await new Promise(r => setTimeout(r, 600));
    const shot2 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('c:\\Users\\ASUS\\Desktop\\AquaPredict\\scripts\\m1_modal_methodology_screenshot.png', Buffer.from(shot2.data, 'base64'));
    console.log('Saved modal methodology screenshot to scripts/m1_modal_methodology_screenshot.png');
    
    // Close modal
    await send('Runtime.evaluate', { expression: "document.getElementById('closeQualityModalBtn').click()" });
    
    ws.close();
    process.exit(0);
  };
}

main().catch(err => {
  console.error('Verification error:', err);
  process.exit(1);
});
