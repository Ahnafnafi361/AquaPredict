const fs = require('fs');
const path = require('path');

async function main() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));

  if (!page) {
    console.error('Target page not found!');
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
    
    // Open Quality Modal and switch to Tab 7
    await send('Runtime.evaluate', {
      expression: `
        (() => {
          const btnQuality = document.getElementById('btnQualityModal');
          if (btnQuality) btnQuality.click();
          const tabM4 = document.querySelector('.modal-tabs .tab-btn[data-tab="tab-m4-synthesis"]');
          if (tabM4) tabM4.click();
        })()
      `
    });

    await new Promise(r => setTimeout(r, 600));

    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(shot.data, 'base64');
    const outPath = path.join(__dirname, '..', 'public', 'm4_modal_tab7_screenshot.png');
    fs.writeFileSync(outPath, buffer);

    const artifactDir = 'C:\\Users\\ASUS\\.gemini\\antigravity-ide\\brain\\7edc98d9-b004-4f1e-b1b5-78a1329b3510';
    if (fs.existsSync(artifactDir)) {
      fs.writeFileSync(path.join(artifactDir, 'm4_modal_tab7_screenshot.png'), buffer);
    }

    console.log('Modal Tab 7 screenshot captured successfully!');
    ws.close();
  };
}

main();
