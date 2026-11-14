const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = path.resolve('C:/Users/ASUS/.gemini/antigravity-ide/brain/18496d93-bfdf-4cb2-a43b-96be753feda8');

async function main() {
  console.log('Connecting to Chrome CDP on port 9222...');
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));

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

  await new Promise(r => ws.onopen = r);

  async function evaluate(expr) {
    const res = await send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval error: ${JSON.stringify(res.exceptionDetails)}`);
    }
    return res.result ? res.result.value : undefined;
  }

  async function captureScreenshot(name) {
    const res = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    const outPath = path.join(ARTIFACT_DIR, `${name}.png`);
    fs.writeFileSync(outPath, buffer);
    console.log(`Saved screenshot: ${outPath}`);
    return outPath;
  }

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  try {
    // 1. Wait for m6Data and simulation scenarios to be ready
    console.log('Ensuring m6Data and simulation scenarios are loaded...');
    await evaluate(`(async () => {
      if (!state.m6Data) {
        const res = await fetch('data/m6_drainage_network.json');
        state.m6Data = await res.json();
      }
      if (!state.simScenarios) {
        const res = await fetch('data/simulation_scenarios.json');
        state.simScenarios = await res.json();
      }
    })()`);

    // 2. Set M5 simulation timeline to Step 12 (Minute 60)
    console.log('Setting simulation to Step 12 (Minute 60)...');
    await evaluate(`(() => {
      state.simActivePreset = 50;
      state.simActiveStepIdx = 12;
      state.simLayerEnabled = true;
      renderSimDynamicOverlay();
    })()`);

    // 3. Switch to 3D View
    console.log('Switching to 3D View with peak flood frame...');
    await evaluate(`document.getElementById('tabView3D').click()`);
    await sleep(2000);

    // 4. Force build drainage lines if needed
    await evaluate(`window.viewer3D.buildDrainageLines()`);
    await evaluate(`window.viewer3D.updateFloodSurface()`);
    await sleep(1000);

    const peak3DState = await evaluate(`({
      view3DVisible: document.getElementById('view3DContainer').style.display !== 'none',
      terrainMeshVisible: window.viewer3D.terrainMesh?.visible,
      floodMeshVisible: window.viewer3D.floodMesh?.visible,
      drainagePipesCount: window.viewer3D.drainageGroup?.children?.length,
      fps: window.viewer3D.fps,
      frameReadout: document.getElementById('hud3DFrameReadout')?.textContent,
      frameStatus: document.getElementById('hud3DFrameStatus')?.textContent
    })`);
    console.log('Peak Flood 3D State:', peak3DState);

    // Capture screenshot of peak flood + drainage in 3D
    await captureScreenshot('m8_05_3d_peak_flood_and_drainage');

    // 5. Test Step 24 (Minute 120)
    console.log('Setting simulation to Step 24 (Minute 120)...');
    await evaluate(`(() => {
      state.simActiveStepIdx = 24;
      renderSimDynamicOverlay();
    })()`);
    await sleep(1000);

    const step24State = await evaluate(`({
      frameReadout: document.getElementById('hud3DFrameReadout')?.textContent,
      floodMeshVisible: window.viewer3D.floodMesh?.visible
    })`);
    console.log('Step 24 State:', step24State);

    await captureScreenshot('m8_06_3d_step24_flood');

    // 6. Return to 2D
    await evaluate(`document.getElementById('tabView2D').click()`);
    await sleep(1000);
    console.log('Returned to 2D successfully.');

    ws.close();
    process.exit(0);

  } catch (err) {
    console.error('Test execution failed:', err);
    ws.close();
    process.exit(1);
  }
}

main();
