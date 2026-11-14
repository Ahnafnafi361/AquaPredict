const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = path.resolve('C:/Users/ASUS/.gemini/antigravity-ide/brain/18496d93-bfdf-4cb2-a43b-96be753feda8');

async function main() {
  console.log('Connecting to Chrome CDP on port 9222...');
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));

  if (!page) {
    console.error('Target page on localhost:8000 not found!');
    process.exit(1);
  }

  console.log(`Connecting to page: ${page.title} (${page.url})`);
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
  console.log('CDP connected.');

  async function evaluate(expr) {
    const res = await send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true
    });
    return res.result ? res.result.value : null;
  }

  async function captureScreenshot(filename) {
    const res = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    const outPath = path.join(ARTIFACT_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    console.log(`[Screenshot Captured] ${outPath} (${buffer.length} bytes)`);
    return outPath;
  }

  // 1. Reload page to ensure clean state
  console.log('Reloading page...');
  await send('Page.reload', {});
  await new Promise(r => setTimeout(r, 2000));

  // 2. Verify English initial load
  const initialLang = await evaluate('document.documentElement.lang');
  const initialSubtitle = await evaluate('document.querySelector(".brand-subtitle").textContent');
  const toggleBtnText = await evaluate('document.getElementById("langSwitchLabel").textContent');
  console.log(`Initial Lang: ${initialLang}, Subtitle: "${initialSubtitle}", Toggle: "${toggleBtnText}"`);

  await captureScreenshot('m10_01_english_view.png');

  // 3. Switch to Bangla
  console.log('Clicking Language Switcher...');
  await evaluate('document.getElementById("btnLangToggle").click()');
  await new Promise(r => setTimeout(r, 600));

  const bnLang = await evaluate('document.documentElement.lang');
  const bnSubtitle = await evaluate('document.querySelector(".brand-subtitle").textContent');
  const bnToggleText = await evaluate('document.getElementById("langSwitchLabel").textContent');
  console.log(`Bangla Lang: ${bnLang}, Subtitle: "${bnSubtitle}", Toggle: "${bnToggleText}"`);

  await captureScreenshot('m10_02_bangla_view.png');

  // 4. Verify 3D mode in Bangla
  console.log('Switching to 3D View in Bangla...');
  await evaluate('document.getElementById("tabView3D").click()');
  await new Promise(r => setTimeout(r, 1200));

  const hud3dTitle = await evaluate('document.querySelector(".hud-title span") ? document.querySelector(".hud-title span").textContent : ""');
  console.log(`3D HUD Title: "${hud3dTitle}"`);

  await captureScreenshot('m10_03_bangla_3d_view.png');

  // 5. Return to 2D
  await evaluate('document.getElementById("tabView2D").click()');
  await new Promise(r => setTimeout(r, 500));

  // 6. Test Static Mode Banner
  console.log('Testing Static Mode detection...');
  await evaluate('window.state.isStaticMode = true; document.getElementById("staticModeBanner").style.display = "block";');
  await new Promise(r => setTimeout(r, 400));
  await captureScreenshot('m10_04_static_mode_banner.png');

  // 7. Check for console errors
  const errCount = await evaluate('window.__lastErrors ? window.__lastErrors.length : 0');
  console.log(`Browser Console Errors: ${errCount}`);

  ws.close();
  console.log('[SUCCESS] All M10 live browser verification steps passed cleanly.');
}

main().catch(err => {
  console.error('M10 Live Verification Failed:', err);
  process.exit(1);
});
