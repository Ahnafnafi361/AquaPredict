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
    console.log('CDP connected. Reloading page with cache disabled for clean M3 test pass...');
    await send('Runtime.enable');
    await send('Log.enable');
    await send('Network.enable');
    await send('Network.setCacheDisabled', { cacheDisabled: true });
    await send('Page.reload', { ignoreCache: true });
    
    // Wait 4s for page reload and all assets to load
    await new Promise(r => setTimeout(r, 4000));
    
    // Evaluate page verification
    const evalRes = await send('Runtime.evaluate', {
      expression: `
        (() => {
          const results = {};
          
          // 1. Check title & badge
          const brandTitle = document.querySelector('.brand-title');
          results.brandTitle = brandTitle ? brandTitle.textContent.trim() : null;
          
          // 2. Check Validation button in header
          const valBtn = document.getElementById('btnValidationModal');
          const valBadge = document.getElementById('headerValidationBadge');
          results.hasValidationBtn = !!valBtn;
          results.headerBadgeText = valBadge ? valBadge.textContent.trim() : null;
          
          // 3. Check M3 Tab in Quality Modal
          const qualityTab6 = document.querySelector('button[data-tab="tab-m3-validation"]');
          results.hasQualityTab6 = !!qualityTab6;
          
          // 4. Check state objects
          results.hasM3State = !!(window.state && window.state.validationReadiness);
          results.m3Decision = window.state && window.state.validationReadiness ? window.state.validationReadiness.decision : null;
          results.m3CandidateCount = window.state && window.state.validationReadiness ? window.state.validationReadiness.candidate_sources.length : 0;
          
          // 5. Open validation modal
          if (valBtn) valBtn.click();
          const modalBackdrop = document.getElementById('validationModalBackdrop');
          results.modalVisibleAfterClick = modalBackdrop && modalBackdrop.style.display !== 'none';
          
          const modalBadge = document.getElementById('validationModalBadge');
          results.modalBadgeText = modalBadge ? modalBadge.textContent.trim() : null;
          
          const rows = document.querySelectorAll('#candidateSourcesTableBody tr');
          results.renderedCandidateRows = rows.length;
          
          // 6. Check existing M0, M1, M2 features
          results.m0Layers = {
            mains: !!window.state?.layers?.gravityMains,
            inlets: !!window.state?.layers?.inlets,
            manholes: !!window.state?.layers?.manholes,
            discharge: !!window.state?.layers?.discharge,
            demTerrain: !!window.state?.layers?.demTerrain
          };
          results.m1Susceptibility = !!window.state?.layers?.susceptibility;
          results.m2RainfallGauge = !!window.state?.layers?.rainfallGauge;
          
          return results;
        })()
      `,
      returnByValue: true
    });
    
    console.log('\n--- M3 In-Browser Verification Audit ---');
    console.log(JSON.stringify(evalRes.result.value, null, 2));
    
    // Wait 1s and take screenshot
    await new Promise(r => setTimeout(r, 1000));
    
    const screenshot = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(screenshot.data, 'base64');
    fs.writeFileSync('scripts/m3_live_verification_screenshot.png', buffer);
    console.log('\nSaved verification screenshot to scripts/m3_live_verification_screenshot.png');
    
    // Close modal
    await send('Runtime.evaluate', {
      expression: `
        (() => {
          const btn = document.getElementById('dismissValidationModalBtn');
          if (btn) btn.click();
        })()
      `
    });
    
    // Test Quality Modal Tab 6
    const tab6Eval = await send('Runtime.evaluate', {
      expression: `
        (() => {
          const qBtn = document.getElementById('btnQualityModal');
          if (qBtn) qBtn.click();
          const tab6 = document.querySelector('button[data-tab="tab-m3-validation"]');
          if (tab6) tab6.click();
          const panel = document.getElementById('tab-m3-validation');
          const isActive = panel && panel.classList.contains('active');
          const closeBtn = document.getElementById('dismissModalBtn');
          if (closeBtn) closeBtn.click();
          return { tab6Found: !!tab6, tab6Activated: isActive };
        })()
      `,
      returnByValue: true
    });
    console.log('Quality Modal Tab 6 test:', tab6Eval.result.value);
    
    console.log(`\nTotal Browser Console Errors: ${consoleErrors.length}`);
    if (consoleErrors.length > 0) {
      console.error('FAIL: Console errors detected:');
      consoleErrors.forEach(e => console.error('  - ' + e));
      process.exit(1);
    } else {
      console.log('PASS: Zero browser console errors!');
    }
    
    ws.close();
    process.exit(0);
  };
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
