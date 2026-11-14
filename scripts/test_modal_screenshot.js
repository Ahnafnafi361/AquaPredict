const fs = require('fs');

async function testScreenshot() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  
  let msgId = 1;
  function send(m, p={}) { 
    return new Promise(r => { 
      const id = msgId++; 
      const handler = e => { 
        const d = JSON.parse(e.data); 
        if (d.id === id) {
          ws.removeEventListener('message', handler);
          r(d.result); 
        }
      }; 
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({id, method: m, params: p})); 
    }); 
  }

  ws.onopen = async () => {
    console.log('Opening validation modal and capturing screenshot...');
    // Open validation modal
    await send('Runtime.evaluate', { 
      expression: `
        document.getElementById('validationModalBackdrop').style.display = 'flex';
      ` 
    });
    await new Promise(r => setTimeout(r, 600));

    const ss = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m3_modal_validation_screenshot.png', Buffer.from(ss.data, 'base64'));
    console.log('Saved: scripts/m3_modal_validation_screenshot.png');

    // Close validation modal and open Quality Modal Tab 6
    await send('Runtime.evaluate', { 
      expression: `
        document.getElementById('validationModalBackdrop').style.display = 'none';
        document.getElementById('qualityModalBackdrop').style.display = 'flex';
        document.querySelector('.modal-tabs .tab-btn[data-tab="tab-m3-validation"]').click();
      ` 
    });
    await new Promise(r => setTimeout(r, 600));

    const ss2 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m3_quality_tab6_screenshot.png', Buffer.from(ss2.data, 'base64'));
    console.log('Saved: scripts/m3_quality_tab6_screenshot.png');

    // Close quality modal and capture main map screen
    await send('Runtime.evaluate', { 
      expression: `
        document.getElementById('qualityModalBackdrop').style.display = 'none';
        document.getElementById('validationModalBackdrop').style.display = 'none';
      ` 
    });
    await new Promise(r => setTimeout(r, 400));
    const ss3 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('scripts/m3_main_map_screenshot.png', Buffer.from(ss3.data, 'base64'));
    console.log('Saved: scripts/m3_main_map_screenshot.png');
    ws.close();
  };
}

testScreenshot();
