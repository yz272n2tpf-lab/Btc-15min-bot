/* P3 descriptive owner. Original information qualification and delivery only. */
(() => {
  'use strict';
  if(window.BTC15InformationOwner||window.btc15CurrentModelInformation)throw Error('BTC15_INFORMATION_OWNER_ALREADY_LOADED');
  const hostDocument=window.document,nodes=new Map();
  const document=Object.freeze({
    get hidden(){return hostDocument.hidden;},
    getElementById(id){if(!nodes.has(id)){const n=hostDocument.createElement('p');n.textContent='WAIT — information refresh pending';nodes.set(id,n);}return nodes.get(id);},
    addEventListener:hostDocument.addEventListener.bind(hostDocument)
  });
  const listeners=new Set();let resolved=null,retainedDelivery=null;
  function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
  function publish(value){resolved=freeze(structuredClone(value));for(const fn of listeners){try{fn(resolved);}catch(error){console.error('BTC15 information subscriber failed',error);}}}
  Object.defineProperty(window,'BTC15InformationOwner',{value:Object.freeze({
    getResolvedView:()=>resolved,
    subscribe(fn){if(typeof fn!=='function')throw TypeError('Display listener required');listeners.add(fn);return ()=>listeners.delete(fn);}
  })});
// P3_VIEW_BEGIN
'use strict';
// Optional dashboard adapter; never installed by importing the Python worker.
// Capture once per actual HTTP response; never renew this token on a render.
const capturedResponses = new WeakSet();
function captureInformation(payload, requestStartedMs, receivedMs) {
  const token = Object.freeze({payload: Object.freeze(structuredClone(payload)), requestStartedMs, receivedMs});
  capturedResponses.add(token);
  return token;
}
// Call on every render/timer, even if fetch fails. All times here are from the
// SAME page's performance.now(); local UTC clock offset is irrelevant. Counting
// the entire request RTT after server checked_ts overestimates response age.
function informationView(token, nowMs) {
  const wait = {authority: 'INFORMATIONAL_READ_ONLY', status: 'WAIT',
    label: 'Information unavailable', assessment: null};
  if (!token || !capturedResponses.has(token) || !Number.isFinite(nowMs) ||
      !Number.isFinite(token.requestStartedMs) || !Number.isFinite(token.receivedMs) ||
      token.requestStartedMs < 0 || token.receivedMs < token.requestStartedMs ||
      nowMs < token.receivedMs) return wait;
  const payload = token.payload;
  if (!payload || typeof payload !== 'object') return wait;
  const nowSeconds = payload.checked_ts + (nowMs-token.requestStartedMs)/1000;
  if (!payload || payload.authority !== 'INFORMATIONAL_READ_ONLY' ||
      payload.schema !== 'BTC15_INFORMATION_V1' || payload.status !== 'AVAILABLE' ||
      payload.orders !== false || payload.signal_only !== true ||
      !Number.isFinite(nowSeconds) || !Number.isFinite(payload.checked_ts) ||
      !Number.isFinite(payload.display_until) || !Number.isFinite(payload.expires_at) ||
      !Number.isFinite(payload.brti_source_ts) ||
      payload.brti_source_ts > payload.checked_ts ||
      nowSeconds < payload.checked_ts || nowSeconds >= payload.display_until ||
      nowSeconds >= payload.expires_at || nowSeconds - payload.brti_source_ts > 5) return wait;
  // Explicit allowlist, never spread a received object into the action stream.
  const assessment = {};
  for (const key of ['ticker', 'probability_up', 'probability_down', 'model_flip_probability',
    'probability_up_change_since_native', 'preferred_side', 'brti_agrees', 'btc_gap', 'brti_gap',
    'up_bid', 'up_ask', 'down_bid', 'down_ask', 'native_decision_ts', 'evaluated_ts',
    'published_ts', 'btc_source_ts', 'brti_source_ts', 'quote_source_ts', 'flip_risk_pct',
    'protection_phase', 'five_minute_caution', 'three_minute_guard', 'profit_protection_status',
    'profit_protection_basis']) assessment[key] = payload[key];
  return {authority: 'INFORMATIONAL_READ_ONLY', status: 'AVAILABLE',
    label: 'Information only — no entry or exit advice', assessment};
}
function twoClockView(authoritative, informational, nowMs) {
  return {authoritative, information: informationView(informational, nowMs)};
}
if (typeof module !== 'undefined') module.exports = {captureInformation, informationView, twoClockView};
// P3_VIEW_END
// P3_PANEL_BEGIN
'use strict';
(() => {
  let token = null, busy = false, generation = 0, lastQualified = null;
  const status = document.getElementById('btc15-information-status');
  const assessment = document.getElementById('btc15-information-assessment');
  function render() {
    const view = informationView(token, performance.now());
    if (view.assessment) lastQualified = view.assessment;
    status.textContent = view.status === 'AVAILABLE' ? view.label : lastQualified ? 'LAST QUALIFIED / REFRESHING — information only' : 'WAIT — information refresh pending';
    const a = view.assessment || lastQualified;
    assessment.textContent = a ? `${a.ticker} · descriptive UP ${(a.probability_up*100).toFixed(1)}% · DOWN ${(a.probability_down*100).toFixed(1)}% · Flip risk ${Number(a.flip_risk_pct).toFixed(1)}% · ${a.protection_phase === '3M_GUARD' ? '3M GUARD' : a.protection_phase === '5M_CAUTION' ? '5M CAUTION' : 'NORMAL'} · Profit protection ${a.profit_protection_status === 'OBSERVE_ONLY_NO_POSITION_CONTEXT' ? 'OBSERVE' : 'REFRESHING'} · BRTI ${a.brti_agrees ? 'agrees' : 'differs'}` : 'WAIT — information refresh pending';
    // P3_BEGIN_INFORMATION_HOOK
    if(view.assessment)retainedDelivery={requestStartedMs:token.requestStartedMs,receivedMs:token.receivedMs,payload:structuredClone(token.payload)};
    publish({schema:'BTC15_COCKPIT_INFORMATION_DISPLAY_R1',authority:'INFORMATIONAL_READ_ONLY',signal_only:true,orders:false,
      resolved_monotonic:performance.now(),generation,busy,hidden:document.hidden,
      current:view,retained:lastQualified,retained_source:retainedDelivery,display:a,selection:view.assessment?'current':a?'retained':'none',
      labels:{status:status.textContent,assessment:assessment.textContent},
      delivery:token?{requestStartedMs:token.requestStartedMs,receivedMs:token.receivedMs,payload:token.payload}:null
    });
    // P3_END_INFORMATION_HOOK
  }
  // Fresh, validated descriptive probabilities only. Action owners cannot renew
  // any lease or create strategy events from this projection.
  window.btc15CurrentModelInformation = () => {
    const a=informationView(token,performance.now()).assessment;
    return a && Number.isFinite(a.probability_up) && Number.isFinite(a.probability_down) && a.probability_up>=0 && a.probability_down>=0 && Math.abs(a.probability_up+a.probability_down-1)<1e-9 ? {...a} : null;
  };
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
// P3_PANEL_END
})();
