'use strict';
(() => {
  let token = null, busy = false, generation = 0;
  const status = document.getElementById('btc15-information-status');
  const assessment = document.getElementById('btc15-information-assessment');
  function render() {
    const view = informationView(token, performance.now());
    status.textContent = view.status === 'AVAILABLE' ? view.label : 'WAIT — information unavailable';
    const a = view.assessment;
    assessment.textContent = a ? `${a.ticker} · descriptive UP ${(a.probability_up*100).toFixed(1)}% · DOWN ${(a.probability_down*100).toFixed(1)}% · BRTI ${a.brti_agrees ? 'agrees' : 'differs'}` : '';
  }
  async function poll() {
    if (busy || document.hidden) return;
    busy = true;
    const mine = generation, started = performance.now();
    const nonce = crypto.randomUUID().replaceAll('-', '');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 700);
    try {
      const response = await fetch('/information', {cache:'no-store',signal:controller.signal,
        headers:{'X-BTC15-Information-Nonce':nonce}});
      if (!response.ok || response.headers.get('X-BTC15-Information-Nonce') !== nonce)
        throw new Error('Information unavailable or replayed response');
      const payload = await response.json();
      if (mine === generation) token = captureInformation(payload, started, performance.now());
    } catch (_) { if (mine === generation) token = null; }
    finally { clearTimeout(timeout); busy = false; render(); }
  }
  function invalidate() { generation++; token = null; render(); }
  // BFCache, hidden tabs and reconnect never retain a previously captured token.
  addEventListener('pagehide', invalidate);
  addEventListener('pageshow', () => { invalidate(); poll(); });
  addEventListener('offline', invalidate);
  addEventListener('online', () => { invalidate(); poll(); });
  document.addEventListener('visibilitychange', () => { invalidate(); if (!document.hidden) poll(); });
  setInterval(render, 100);
  setInterval(poll, 500);
  render(); poll();
})();
