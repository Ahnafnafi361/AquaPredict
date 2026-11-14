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
        expression: `({
          scrollTop: document.querySelector('.sidebar-scrollable').scrollTop,
          scrollHeight: document.querySelector('.sidebar-scrollable').scrollHeight,
          clientHeight: document.querySelector('.sidebar-scrollable').clientHeight,
          firstSectionText: document.querySelector('.control-section .section-label')?.textContent?.trim(),
          sectionsCount: document.querySelectorAll('.control-section').length
        })`,
        returnByValue: true
      }
    }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Sidebar state:', data.result?.result?.value);
    ws.close();
  };
})();
