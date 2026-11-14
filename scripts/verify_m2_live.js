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
  const consoleErrors = [];
  
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
      if (type === 'error') {
        consoleErrors.push(text);
        console.error(`[Browser Console ERROR]: ${text}`);
      } else {
        console.log(`[Browser Console ${type.toUpperCase()}]: ${text}`);
      }
    } else if (data.method === 'Log.entryAdded') {
      const entry = data.params.entry;
      if (entry.level === 'error') {
        consoleErrors.push(entry.text);
        console.error(`[Browser Log ERROR]: ${entry.text}`);
      }
    } else if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    }
  };
  
  ws.onopen = async () => {
    console.log('CDP connected. Reloading page for clean M2 test pass...');
    await send('Runtime.enable');
    await send('Log.enable');
    await send('Page.reload');
    
    // Wait 3s for page reload and all assets to load
    await new Promise(r => setTimeout(r, 3000));
    
    // 1. Evaluate M0/M1/M2 DOM & State
    const checkState = await send('Runtime.evaluate', {
      expression: `
        (() => {
          return {
            brandTitle: document.querySelector('.brand-title')?.innerText,
            headerBadge: document.getElementById('headerRainfallBadge')?.innerText,
            sidebarStatus: document.getElementById('sidebarRainfallStatusPill')?.innerText,
            quickCardStatus: document.getElementById('quickCardStatus')?.innerText,
            btnRainfallExists: !!document.getElementById('btnRainfallModal'),
            gaugePinLayerExists: !!state.layers.rainfallGauge,
            liveSeriesStatus: state.rainfallLive?.status,
            sampleSeriesStatus: state.rainfallSample?.status,
            gravityMainsCount: state.layers.gravityMains?.getLayers()?.length,
            inletsCount: state.layers.inlets?.getLayers()?.length,
            manholesCount: state.layers.manholes?.getLayers()?.length,
            dischargeCount: state.layers.discharge?.getLayers()?.length,
            suscLayerActive: !!state.layers.susceptibility && state.map.hasLayer(state.layers.susceptibility),
            demLayerActive: !!state.layers.demTerrain && state.map.hasLayer(state.layers.demTerrain)
          };
        })()
      `,
      returnByValue: true
    });
    
    console.log('\n--- State Audit ---');
    console.log(JSON.stringify(checkState.result.value, null, 2));

    // 2. Open Rainfall Modal (Default Live Empty State)
    await send('Runtime.evaluate', {
      expression: `document.getElementById('btnRainfallModal').click();`
    });
    await new Promise(r => setTimeout(r, 600));

    const checkEmptyModal = await send('Runtime.evaluate', {
      expression: `
        (() => {
          const modal = document.getElementById('rainfallModalBackdrop');
          const isVisible = modal && modal.style.display !== 'none';
          const title = document.getElementById('rainfallModalTitle')?.innerText;
          const badge = document.getElementById('rainfallModalBadge')?.innerText;
          const bodyText = document.getElementById('rainfallModalBody')?.innerText;
          const hasEmptyCard = !!document.querySelector('.rainfall-empty-card');
          return { isVisible, title, badge, hasEmptyCard, bodySnippet: bodyText.substring(0, 150) };
        })()
      `,
      returnByValue: true
    });
    console.log('\n--- Rainfall Modal (Live Empty State) ---');
    console.log(JSON.stringify(checkEmptyModal.result.value, null, 2));

    // Screenshot 1: Empty state
    const ss1 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m2_empty_state_screenshot.png', Buffer.from(ss1.data, 'base64'));
    console.log('Saved: scripts/m2_empty_state_screenshot.png');

    // 3. Switch to Exploratory Sample Fixture
    await send('Runtime.evaluate', {
      expression: `document.getElementById('btnSourceSample').click();`
    });
    await new Promise(r => setTimeout(r, 600));

    const checkSampleModal = await send('Runtime.evaluate', {
      expression: `
        (() => {
          const badge = document.getElementById('rainfallModalBadge')?.innerText;
          const barsCount = document.querySelectorAll('.rain-bar').length;
          const metricVals = Array.from(document.querySelectorAll('.rain-metric-val')).map(el => el.innerText.trim());
          const hasSvg = !!document.querySelector('.svg-chart-viewport svg');
          
          // Trigger mouse hover on a peak bar (e.g. index 23)
          const bar = document.querySelector('.rain-bar[data-idx="23"]');
          if (bar) {
            bar.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
          }
          const tooltipText = document.getElementById('hyetographTooltip')?.innerText;

          return { badge, barsCount, metricVals, hasSvg, tooltipText };
        })()
      `,
      returnByValue: true
    });
    console.log('\n--- Rainfall Modal (Exploratory Fixture & Hyetograph) ---');
    console.log(JSON.stringify(checkSampleModal.result.value, null, 2));

    // Screenshot 2: Hyetograph with hover tooltip
    const ss2 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m2_hyetograph_screenshot.png', Buffer.from(ss2.data, 'base64'));
    console.log('Saved: scripts/m2_hyetograph_screenshot.png');

    // 4. Close Rainfall Modal and Open Data Quality Modal (Tab 5)
    await send('Runtime.evaluate', {
      expression: `
        document.getElementById('closeRainfallModalBtn').click();
        document.getElementById('btnQualityModal').click();
        const tabBtn = document.querySelector('.modal-tabs .tab-btn[data-tab="tab-m2-rainfall"]');
        if (tabBtn) tabBtn.click();
      `
    });
    await new Promise(r => setTimeout(r, 600));

    // Screenshot 3: Data Quality Modal (M2 Tab)
    const ss3 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m2_modal_lineage_screenshot.png', Buffer.from(ss3.data, 'base64'));
    console.log('Saved: scripts/m2_modal_lineage_screenshot.png');

    // 5. Close Quality Modal, re-center map, and capture final live application screenshot
    await send('Runtime.evaluate', {
      expression: `
        document.getElementById('closeQualityModalBtn').click();
        document.getElementById('btnRecenter').click();
      `
    });
    await new Promise(r => setTimeout(r, 800));

    const ss4 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m2_live_verification_screenshot.png', Buffer.from(ss4.data, 'base64'));
    console.log('Saved: scripts/m2_live_verification_screenshot.png');

    console.log('\n--- Browser Console Errors ---');
    console.log(`Total errors: ${consoleErrors.length}`);
    if (consoleErrors.length > 0) {
      consoleErrors.forEach(e => console.error(' ', e));
    } else {
      console.log(' [PASS] 0 console errors detected in browser session.');
    }

    ws.close();
    process.exit(consoleErrors.length > 0 ? 1 : 0);
  };
}

main().catch(err => {
  console.error('Fatal verification error:', err);
  process.exit(1);
});
