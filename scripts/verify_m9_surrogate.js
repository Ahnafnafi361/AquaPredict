const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = path.resolve('C:/Users/ASUS/.gemini/antigravity-ide/brain/18496d93-bfdf-4cb2-a43b-96be753feda8');

async function main() {
  console.log('Connecting to Chrome CDP on port 9222...');
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));

  if (!page) {
    throw new Error('Could not find AquaPredict browser tab on port 9222');
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
    console.log('Reloading page to ensure fresh state...');
    await send('Page.navigate', { url: 'http://localhost:8000/' });
    await sleep(2500);

    // 1. Initial State Verification (Physical Screening Model)
    console.log('\n--- Step 1: Verify Initial Physical Screening Baseline ---');
    const initEngine = await evaluate(`window.state.simEngine`);
    console.log('Default Simulation Engine:', initEngine);
    if (initEngine !== 'original') throw new Error(`Expected engine 'original', got '${initEngine}'`);

    const warningDisplay1 = await evaluate(`document.getElementById('surrogateWarningBanner').style.display`);
    console.log('Surrogate Warning Banner display (expected "none"):', warningDisplay1);
    if (warningDisplay1 !== 'none') throw new Error(`Warning banner should be hidden initially`);

    // Enable M5 Simulation Layer and jump to peak (50mm step 18)
    console.log('\n--- Step 2: Enable Simulation Layer & Peak Inundation ---');
    await evaluate(`
      const toggle = document.getElementById('toggleSimulationLayer');
      if (toggle && !toggle.checked) {
        toggle.checked = true;
        toggleSimulationLayer(true);
      }
      jumpToSimPeak();
    `);
    await sleep(800);

    const origRainMode = await evaluate(`document.getElementById('rainModeText').textContent`);
    console.log('Original Rain Mode Text:', origRainMode);

    await captureScreenshot('m9_01_original_screening_simulation');

    // 3. Switch to ML Surrogate Mode
    console.log('\n--- Step 3: Switch to ML Surrogate Mode (M9) ---');
    await evaluate(`
      const btnSurr = document.getElementById('btnEngineSurrogate');
      if (btnSurr) btnSurr.click();
    `);
    await sleep(1500);

    const surrEngine = await evaluate(`window.state.simEngine`);
    console.log('Active Engine after toggle:', surrEngine);
    if (surrEngine !== 'surrogate') throw new Error(`Failed to switch to surrogate engine`);

    const warningDisplay2 = await evaluate(`document.getElementById('surrogateWarningBanner').style.display`);
    console.log('Surrogate Warning Banner display (expected "block"):', warningDisplay2);
    if (warningDisplay2 !== 'block') throw new Error(`Warning banner should be visible in surrogate mode`);

    const warningText = await evaluate(`document.getElementById('surrogateWarningBanner').innerText`);
    console.log('Warning Banner Text:\n', warningText);
    if (!warningText.includes('SYNTHETIC SURROGATE')) {
      throw new Error('Warning banner missing mandatory SYNTHETIC SURROGATE label');
    }

    const latencyText = await evaluate(`document.getElementById('surrogateLatencyReadout').textContent`);
    console.log('Latency Readout:', latencyText);

    const surrRainMode = await evaluate(`document.getElementById('rainModeText').textContent`);
    console.log('Surrogate Rain Mode Text:', surrRainMode);
    if (!surrRainMode.includes('ML Surrogate Simulation') || !surrRainMode.includes('UNVALIDATED')) {
      throw new Error('Header pill missing mandatory UNVALIDATED surrogate label');
    }

    await captureScreenshot('m9_02_surrogate_simulation_active');

    // 4. Scrub Timestep on Surrogate
    console.log('\n--- Step 4: Scrub Timestep on Surrogate (Step 24 / 120 min) ---');
    await evaluate(`onSimTimelineChange(24);`);
    await sleep(800);

    const scrubTime = await evaluate(`document.getElementById('simTimeLabel').textContent`);
    console.log('Time Readout after scrub:', scrubTime);

    await captureScreenshot('m9_03_surrogate_step24_scrub');

    // 5. Switch to 3D View and Verify Surrogate Flood Surface
    console.log('\n--- Step 5: Switch to 3D Terrain & Verify Surrogate Synchronization ---');
    await evaluate(`
      const tab3D = document.getElementById('tabView3D');
      if (tab3D) tab3D.click();
    `);
    await sleep(2000);

    const hud3DReadout = await evaluate(`document.getElementById('hud3DFrameReadout').textContent`);
    console.log('3D HUD Readout:', hud3DReadout);
    if (!hud3DReadout.includes('[SURROGATE]')) {
      throw new Error(`3D HUD readout missing [SURROGATE] tag: '${hud3DReadout}'`);
    }

    await captureScreenshot('m9_04_3d_surrogate_flood_view');

    // 6. Switch Back to Physical Screening in 3D
    console.log('\n--- Step 6: Restore Physical Screening Model ---');
    await evaluate(`
      const btnOrig = document.getElementById('btnEngineOriginal');
      if (btnOrig) btnOrig.click();
    `);
    await sleep(1000);

    const restoredEngine = await evaluate(`window.state.simEngine`);
    console.log('Restored Engine:', restoredEngine);
    const restoredHud = await evaluate(`document.getElementById('hud3DFrameReadout').textContent`);
    console.log('Restored 3D HUD Readout:', restoredHud);
    if (restoredHud.includes('[SURROGATE]')) {
      throw new Error(`Restored 3D HUD should not have [SURROGATE] tag: '${restoredHud}'`);
    }

    // Switch back to 2D
    await evaluate(`
      const tab2D = document.getElementById('tabView2D');
      if (tab2D) tab2D.click();
    `);
    await sleep(800);

    await captureScreenshot('m9_05_restored_original_screening');

    console.log('\n============================================================');
    console.log(' All Live Browser M9 Surrogate Verifications PASSED!');
    console.log('============================================================');

  } catch (err) {
    console.error('Browser live verification failed:', err);
    process.exit(1);
  } finally {
    ws.close();
  }
}

main();
