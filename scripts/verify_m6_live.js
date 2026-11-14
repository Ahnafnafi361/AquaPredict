const fs = require('fs');
const path = require('path');

async function main() {
  console.log("=== AquaPredict M6 Live Browser & Topology Verification ===");

  // 1. Fetch CDP Targets
  let targets;
  try {
    const res = await fetch('http://127.0.0.1:9222/json');
    targets = await res.json();
  } catch (err) {
    console.error("Could not connect to Chrome CDP at port 9222. Is Chrome running with --remote-debugging-port=9222?", err.message);
    process.exit(1);
  }

  const pageTarget = targets.find(t => t.url.includes('localhost:8000') || t.title.includes('AquaPredict'));
  if (!pageTarget) {
    console.error("Could not find AquaPredict page target in Chrome. Active targets:", targets.map(t => ({ title: t.title, url: t.url })));
    process.exit(1);
  }

  console.log(`Connecting to: ${pageTarget.title} (${pageTarget.webSocketDebuggerUrl})`);
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);

  let msgId = 1;
  const pending = new Map();
  const consoleLogs = [];

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
      consoleLogs.push({ type, text });
      if (type === 'error') {
        console.error(`[Browser Console ERROR]: ${text}`);
      } else {
        console.log(`[Browser Console ${type.toUpperCase()}]: ${text}`);
      }
    } else if (data.method === 'Log.entryAdded') {
      const entry = data.params.entry;
      consoleLogs.push({ type: entry.level, text: entry.text });
      if (entry.level === 'error') {
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
    try {
      console.log("CDP WebSocket opened.");
      await send('Runtime.enable');
      await send('Log.enable');
      await send('Page.enable');
      await send('DOM.enable');

      // Reload page to get fresh state
      console.log("Reloading http://localhost:8000/ ...");
      await send('Page.reload', { ignoreCache: true });

      // Wait 3.5 seconds for all assets to load
      await new Promise(r => setTimeout(r, 3500));

      // Execute comprehensive in-browser verification
      const verifyScript = `
        (async () => {
          const results = {
            errors: [],
            checks: {}
          };

          try {
            // Check 1: Header Brand Badge
            const brandBadge = document.querySelector('.brand-title .badge-m0');
            results.checks.brandBadge = brandBadge ? brandBadge.textContent.trim() : null;
            if (!results.checks.brandBadge || !results.checks.brandBadge.includes('M6')) {
              results.errors.push('Brand badge missing M6: ' + results.checks.brandBadge);
            }

            // Check 2: M6 Drainage Modal Button in Header
            const btnDrain = document.getElementById('btnDrainageModal');
            results.checks.hasDrainageButton = !!btnDrain;
            const drainBadge = document.getElementById('headerDrainageBadge');
            results.checks.drainageBadgeText = drainBadge ? drainBadge.textContent.trim() : null;

            // Check 3: State & M6 Data Asset Loaded
            results.checks.hasState = !!window.state;
            results.checks.hasM6Data = !!window.state?.m6Data;
            if (window.state?.m6Data) {
              const m6 = window.state.m6Data;
              results.checks.conduitCount = Object.keys(m6.conduits || {}).length;
              results.checks.nodeCount = Object.keys(m6.nodes || {}).length;
              results.checks.hotspotCount = (m6.hotspots || []).length;
              results.checks.hasDynamicLoading = !!m6.dynamic_simulation_loading;
              results.checks.reachesOutfallConduits = Object.values(m6.conduits || {}).filter(c => c.reaches_bayou_outfall).length;
            }

            // Check 4: Modal Open & Tab Switching
            if (btnDrain) {
              btnDrain.click();
              const modal = document.getElementById('drainageModalBackdrop');
              results.checks.modalOpenVisible = modal && modal.style.display !== 'none';
              
              // Switch tabs
              const tabs = ['draintab-overview', 'draintab-capacity', 'draintab-hotspots', 'draintab-guardrails'];
              for (const t of tabs) {
                const btn = document.querySelector(\`#drainageModalTabs [data-draintab="\${t}"]\`);
                if (btn) btn.click();
              }
              
              // Close modal
              const closeBtn = document.getElementById('closeDrainageModalBtn');
              if (closeBtn) closeBtn.click();
              results.checks.modalClosed = modal && modal.style.display === 'none';
            }

            // Check 5: Workflow Drawer 7/7 Complete
            const wfBadge = document.querySelector('.drawer-step-badge');
            results.checks.drawerBadge = wfBadge ? wfBadge.textContent.trim() : null;
            const step5 = document.getElementById('wfStep5');
            const step7 = document.getElementById('wfStep7');
            results.checks.step5Completed = step5 ? step5.classList.contains('step-completed') : false;
            results.checks.step7Completed = step7 ? step7.classList.contains('step-completed') : false;

            // Check 6: Open Inspector on a known conduit
            const conduitKeys = Object.keys(window.state?.m6Data?.conduits || {});
            const testConduitId = conduitKeys[0] || '3538930';
            const testConduitObj = window.state.m6Data.conduits[testConduitId];
            window.openInspector('Gravity Main', {
              FACILITYID: testConduitId,
              WIDTH: testConduitObj?.diameter_in || 24,
              MATERIAL: testConduitObj?.material || 'RCP',
              SLOPE: testConduitObj?.slope_pct || 0.25
            });

            const card = document.getElementById('assetInspectorCard');
            results.checks.inspectorVisible = card && card.style.display !== 'none';
            const m6Block = document.querySelector('.inspector-m6-block');
            results.checks.inspectorHasM6Block = !!m6Block;
            const traceActions = document.getElementById('inspectorTraceActions');
            results.checks.traceActionsVisible = traceActions && traceActions.style.display !== 'none';

            // Check 7: Upstream Tracing
            window.traceUpstream(testConduitId);
            results.checks.hasActiveTraceLayer = !!window.state?.m6ActiveTraceLayer;
            const summaryBox = document.getElementById('traceSummaryBox');
            results.checks.traceSummaryText = summaryBox ? summaryBox.textContent.replace(/\\s+/g, ' ').trim() : null;

            // Check 8: Downstream Tracing
            window.traceDownstream(testConduitId);
            results.checks.traceDownstreamSummary = summaryBox ? summaryBox.textContent.replace(/\\s+/g, ' ').trim() : null;

            // Clear trace
            window.clearTrace();
            results.checks.traceCleared = !window.state?.m6ActiveTraceLayer;

            // Check 9: M5 Simulation Scrub & Status Bar Dynamic M6 Metrics
            if (window.selectSimPreset) {
              window.selectSimPreset(50);
              window.onSimTimelineChange(12); // Minute 60 (storm peak)
            }

            const valRain = document.getElementById('statusValRainTotal');
            const valMaxDepth = document.getElementById('statusValMaxDepth');
            const valNodes = document.getElementById('statusValSurchargedNodes');
            const valDrains = document.getElementById('statusValOverloadedDrains');
            const valWarn = document.getElementById('statusValActiveWarnings');

            results.checks.statusRainTotal = valRain ? valRain.textContent.trim() : null;
            results.checks.statusMaxDepth = valMaxDepth ? valMaxDepth.textContent.trim() : null;
            results.checks.statusSurchargedNodes = valNodes ? valNodes.textContent.trim() : null;
            results.checks.statusOverloadedDrains = valDrains ? valDrains.textContent.trim() : null;
            results.checks.statusActiveWarnings = valWarn ? valWarn.textContent.trim() : null;

            // Verify status bar is NOT showing "Unavailable (M6 Dependent)"
            if (results.checks.statusSurchargedNodes?.includes('Unavailable')) {
              results.errors.push('Surcharged nodes status still shows Unavailable');
            }
            if (results.checks.statusOverloadedDrains?.includes('Unavailable')) {
              results.errors.push('Overloaded drains status still shows Unavailable');
            }

            // Check 10: Dynamic Conduit Loading Mode
            const toggleLoad = document.getElementById('toggleDrainageLoadingMode');
            if (toggleLoad) {
              toggleLoad.checked = true;
              window.toggleDrainageLoadingMode(true);
              results.checks.drainageLoadingModeActive = window.state?.drainageLoadingMode === true;
            }

          } catch (e) {
            results.errors.push('Exception in verification: ' + e.toString());
          }

          return results;
        })()
      `;

      console.log("Evaluating in-browser tests...");
      const evalRes = await send('Runtime.evaluate', {
        expression: verifyScript,
        awaitPromise: true,
        returnByValue: true
      });

      const report = evalRes.result.value;
      console.log("\n=======================================================");
      console.log("LIVE BROWSER TEST REPORT:");
      console.log("=======================================================");
      console.log(JSON.stringify(report, null, 2));

      // Capture Screenshot
      console.log("\nCapturing full screenshot...");
      const screenshot = await send('Page.captureScreenshot', { format: 'png' });
      const imgBuffer = Buffer.from(screenshot.data, 'base64');

      const outDir = path.join(__dirname, '..', 'public', 'data');
      const outPath = path.join(outDir, 'm6_live_verification.png');
      fs.writeFileSync(outPath, imgBuffer);
      console.log(`Saved screenshot to: ${outPath} (${imgBuffer.length} bytes)`);

      // Check for errors
      const hasErrors = (report.errors && report.errors.length > 0);
      if (hasErrors) {
        console.error("\n[FAIL] Verification errors detected:", report.errors);
        process.exit(1);
      } else {
        console.log("\n[PASS] All live browser checks passed cleanly!");
        process.exit(0);
      }

    } catch (err) {
      console.error("Test execution failed:", err);
      process.exit(1);
    }
  };
}

main();
