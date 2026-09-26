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
    'protection_phase', 'five_minute_caution', 'three_minute_guard']) assessment[key] = payload[key];
  return {authority: 'INFORMATIONAL_READ_ONLY', status: 'AVAILABLE',
    label: 'Information only — no entry or exit advice', assessment};
}
function twoClockView(authoritative, informational, nowMs) {
  return {authoritative, information: informationView(informational, nowMs)};
}
if (typeof module !== 'undefined') module.exports = {captureInformation, informationView, twoClockView};
