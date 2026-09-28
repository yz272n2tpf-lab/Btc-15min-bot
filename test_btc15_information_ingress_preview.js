'use strict';
// Execute the unchanged qualified preview seam with real synthetic pipeline
// outputs. A DOM harness verifies presentation behavior, not device layout.
const assert = require('assert/strict');
const vm = require('vm');
const {script, rows} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const code = script.replace(/^<script[^>]*>/, '').replace(/<\/script>$/, '');

async function exercise(row, mutate = () => {}) {
  const data = structuredClone(row);
  const control = {nonce: true, identityOK: true};
  mutate(data, control);
  const nodes = new Map(), listeners = {}, intervals = [];
  const parent = {appendChild(n) { nodes.set(n.id, n); }};
  for (const id of ['flipRisk', 'finalAction', 'earlyAction', 'combinedScalpClean'])
    nodes.set(id, {textContent: 'authoritative sentinel', dataset: {}, parentElement: parent});
  let now = 100;
  const document = {
    hidden: false, documentElement: {dataset: {}},
    getElementById: id => nodes.get(id),
    createElement: () => ({dataset: {}, style: {}}),
    addEventListener: (event, fn) => { listeners[event] = fn; },
  };
  const calls = [];
  const context = {
    document, structuredClone, AbortController,
    performance: {now: () => now},
    crypto: {randomUUID: () => 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'},
    setTimeout: () => 1, clearTimeout: () => {},
    setInterval: (fn, ms) => intervals.push({fn, ms}),
    addEventListener: (event, fn) => { listeners[event] = fn; },
    fetch: async (url, options) => {
      calls.push(url);
      const ident = url === '/information/identity';
      assert.ok(ident || url === '/information');
      assert.equal(options.cache, 'no-store');
      return {ok: ident ? control.identityOK : true,
        headers: {get: () => control.nonce ? options.headers['X-BTC15-Information-Nonce'] : 'wrong'},
        json: async () => structuredClone(ident ? data.identity : data.frame)};
    },
  };
  vm.runInNewContext(code, context);
  await new Promise(resolve => setImmediate(resolve));
  const render = intervals.find(i => i.ms === 100).fn;
  render();
  function stale() {
    assert.equal(nodes.get('flipRisk').textContent, '—');
    assert.equal(nodes.get('btc15QualifiedBrtiFreshness').dataset.fresh, 'false');
    assert.equal(nodes.get('btc15QualifiedGuardState').dataset.phase, 'DATA_STALE');
  }
  function authorityUnchanged() {
    for (const id of ['finalAction', 'earlyAction', 'combinedScalpClean'])
      assert.equal(nodes.get(id).textContent, 'authoritative sentinel');
  }
  return {data, nodes, listeners, document, render, stale, authorityUnchanged,
    advance: n => {now += n; render();}, calls};
}

(async () => {
  for (const row of rows) {
    const h = await exercise(row);
    assert.equal(h.nodes.get('flipRisk').textContent, row.frame.flip_risk_pct.toFixed(1)+'%');
    assert.equal(h.nodes.get('btc15QualifiedBrtiFreshness').dataset.fresh, 'true');
    assert.equal(h.nodes.get('btc15QualifiedGuardState').dataset.phase, row.frame.protection_phase);
    h.authorityUnchanged();
    h.advance(1001); h.stale(); // Native one-second health lease expires.
    for (const event of ['offline', 'pagehide', 'visibilitychange']) {
      const x = await exercise(row); x.document.hidden = true;
      x.listeners[event](); x.stale(); x.authorityUnchanged();
    }
  }
  for (const mutation of [
    d => {d.frame.status = 'WAIT';},
    d => {d.identity.ticker = 'KXBTC15M-OTHER';},
    d => {d.identity.schema = 'WRONG';},
    d => {d.frame.brti_source_ts = d.frame.checked_ts - 5.000001;},
    d => {d.frame.orders = true;},
    (_, c) => {c.identityOK = false;},
    (_, c) => {c.nonce = false;},
  ]) {
    const x = await exercise(rows[0], mutation); x.stale(); x.authorityUnchanged();
  }
  console.log('EXACT RECOVERED PREVIEW SEAM: numeric flip risk, fresh BRTI, all guard phases, lifecycle/nonce/identity/expiry fail-closed PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
