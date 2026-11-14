async function main() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  
  if (!page) {
    console.error('Page target not found in Chrome!');
    process.exit(1);
  }
  
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let msgId = 1;
  const pending = new Map();
  
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    }
  };
  
  ws.onopen = async () => {
    await send('Runtime.enable');
    
    const toggleScript = `
      (() => {
        const tests = [];
        const map = state.map;
        
        // 1. Susceptibility Toggle
        const toggleSusc = document.getElementById('toggleSusceptibility');
        const suscLayer = state.layers.susceptibility;
        
        const initSuscOn = map.hasLayer(suscLayer);
        toggleSusc.click();
        const afterSuscOff = map.hasLayer(suscLayer);
        toggleSusc.click();
        const afterSuscOn = map.hasLayer(suscLayer);
        tests.push({
          name: 'Susceptibility Toggle',
          pass: initSuscOn === true && afterSuscOff === false && afterSuscOn === true
        });
        
        // 2. Susceptibility Modes (Composite, Depressions, Proximity)
        const btnDep = document.getElementById('btnModeDepressions');
        const btnProx = document.getElementById('btnModeInletProx');
        const btnComp = document.getElementById('btnModeComposite');
        
        btnDep.click();
        const depActive = map.hasLayer(state.layers.depressions) && !map.hasLayer(state.layers.susceptibility);
        
        btnProx.click();
        const proxActive = map.hasLayer(state.layers.inletProximity) && !map.hasLayer(state.layers.depressions);
        
        btnComp.click();
        const compActive = map.hasLayer(state.layers.susceptibility) && !map.hasLayer(state.layers.inletProximity);
        
        tests.push({
          name: 'Susceptibility Mode Switching',
          pass: depActive && proxActive && compActive
        });
        
        // 3. Gravity Mains Toggle
        const togglePipes = document.getElementById('toggleGravityMains');
        const pipesLayer = state.layers.gravityMains;
        const initPipesOn = map.hasLayer(pipesLayer);
        togglePipes.click();
        const afterPipesOff = map.hasLayer(pipesLayer);
        togglePipes.click();
        const afterPipesOn = map.hasLayer(pipesLayer);
        tests.push({
          name: 'Gravity Mains Toggle',
          pass: initPipesOn === true && afterPipesOff === false && afterPipesOn === true
        });
        
        // 4. Inlets Toggle
        const toggleInlets = document.getElementById('toggleInlets');
        const inletsLayer = state.layers.inlets;
        const initInletsOn = map.hasLayer(inletsLayer);
        toggleInlets.click();
        const afterInletsOff = map.hasLayer(inletsLayer);
        toggleInlets.click();
        const afterInletsOn = map.hasLayer(inletsLayer);
        tests.push({
          name: 'Inlets Toggle',
          pass: initInletsOn === true && afterInletsOff === false && afterInletsOn === true
        });
        
        // 5. Manholes Toggle
        const toggleMh = document.getElementById('toggleManholes');
        const mhLayer = state.layers.manholes;
        const initMhOn = map.hasLayer(mhLayer);
        toggleMh.click();
        const afterMhOff = map.hasLayer(mhLayer);
        toggleMh.click();
        const afterMhOn = map.hasLayer(mhLayer);
        tests.push({
          name: 'Manholes Toggle',
          pass: initMhOn === true && afterMhOff === false && afterMhOn === true
        });
        
        // 6. Discharge Toggle
        const toggleDis = document.getElementById('toggleDischarge');
        const disLayer = state.layers.discharge;
        const initDisOn = map.hasLayer(disLayer);
        toggleDis.click();
        const afterDisOff = map.hasLayer(disLayer);
        toggleDis.click();
        const afterDisOn = map.hasLayer(disLayer);
        tests.push({
          name: 'Discharge Toggle',
          pass: initDisOn === true && afterDisOff === false && afterDisOn === true
        });
        
        // 7. DEM Terrain Toggle
        const toggleDem = document.getElementById('toggleDemTerrain');
        const demLayer = state.layers.demTerrain;
        const initDemOn = map.hasLayer(demLayer);
        toggleDem.click();
        const afterDemOff = map.hasLayer(demLayer);
        toggleDem.click();
        const afterDemOn = map.hasLayer(demLayer);
        tests.push({
          name: 'DEM Terrain Toggle',
          pass: initDemOn === true && afterDemOff === false && afterDemOn === true
        });
        
        return tests;
      })()
    `;
    
    const result = await send('Runtime.evaluate', { expression: toggleScript, returnByValue: true });
    console.log('\n--- LAYER TOGGLE VERIFICATION RESULTS ---');
    console.log(JSON.stringify(result.result.value, null, 2));
    
    ws.close();
    process.exit(0);
  };
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
