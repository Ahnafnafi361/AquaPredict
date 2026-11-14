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
    
    // Scroll sidebar to Section 5
    await send('Runtime.evaluate', {
      expression: `
        (() => {
          const scrollable = document.querySelector('.sidebar-scrollable');
          const m4Section = document.querySelector('.highlight-m4-item');
          if (scrollable && m4Section) {
            scrollable.scrollTop = m4Section.offsetTop - 80;
          }
        })()
      `
    });

    await new Promise(r => setTimeout(r, 600));

    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(shot.data, 'base64');
    const outPath = path.join(__dirname, '..', 'public', 'm4_sidebar_controls_screenshot.png');
    fs.writeFileSync(outPath, buffer);

    const artifactDir = 'C:\\Users\\ASUS\\.gemini\\antigravity-ide\\brain\\7edc98d9-b004-4f1e-b1b5-78a1329b3510';
    if (fs.existsSync(artifactDir)) {
      fs.writeFileSync(path.join(artifactDir, 'm4_sidebar_controls_screenshot.png'), buffer);
    }

    console.log('Sidebar screenshot captured successfully!');
    ws.close();
  };
}

main();
