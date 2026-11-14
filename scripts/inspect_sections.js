(async () => {
  const res = await fetch('http://127.0.0.1:9222/json');
  const targets = await res.json();
  const page = targets.find(t => t.url.includes('localhost:8000'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  
  ws.onopen = () => {
    ws.send(JSON.stringify({
      id: 1,
      method: 'Runtime.evaluate',
      params: {
        expression: `Array.from(document.querySelectorAll('.control-section')).map(s => ({
          label: s.querySelector('.section-label')?.textContent?.replace(/\\s+/g, ' ').trim(),
          display: window.getComputedStyle(s).display,
          rect: s.getBoundingClientRect()
        }))`,
        returnByValue: true
      }
    }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Control sections:', JSON.stringify(data.result?.result?.value, null, 2));
    ws.close();
  };
})();
