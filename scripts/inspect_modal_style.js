async function run() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  ws.onopen = async () => {
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
    
    // Open validation modal
    await send('Runtime.evaluate', { expression: `document.getElementById('btnValidationModal').click();` });
    
    const r = await send('Runtime.evaluate', {
      expression: `
        (() => {
          const el = document.getElementById("validationModalBackdrop");
          const d = el ? el.querySelector(".modal-dialog") : null;
          const rect = d ? d.getBoundingClientRect() : null;
          const elRect = el ? el.getBoundingClientRect() : null;
          return {
            elDisplay: el ? el.style.display : null,
            elBg: el ? window.getComputedStyle(el).backgroundColor : null,
            elZ: el ? window.getComputedStyle(el).zIndex : null,
            elPosition: el ? window.getComputedStyle(el).position : null,
            elRect: elRect ? { w: elRect.width, h: elRect.height, t: elRect.top, l: elRect.left } : null,
            dBg: d ? window.getComputedStyle(d).backgroundColor : null,
            dRect: rect ? { w: rect.width, h: rect.height, t: rect.top, l: rect.left } : null
          };
        })()
      `,
      returnByValue: true
    });
    console.log(r && r.result ? r.result.value : r);
    ws.close();
  };
}
run();
