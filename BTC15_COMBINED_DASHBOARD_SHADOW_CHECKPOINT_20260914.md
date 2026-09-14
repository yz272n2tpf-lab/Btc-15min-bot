# BTC15 Combined Dashboard Shadow Checkpoint — 2026-09-14

**Status:** OFF-PRODUCTION VALIDATION GATE  
**Mode:** SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

## Purpose

Validate the generalized SCALP in the existing locked dashboard card before any production dashboard replacement.

## Shadow service

- Railway service: `combined-dashboard-shadow-v1`
- Service ID: `142e0fe5-13ce-4cb7-a08b-d4a65539fb47`
- Public shadow domain: `combined-dashboard-shadow-v1-production.up.railway.app`
- Source branch: `scalp-move-shadow-v1-20260912`
- This is a separate service. The production `Btc-15min-bot` service is not modified by this shadow deployment.

## Fixed data ownership

- Production main dashboard JSON remains authority for contract, Kalshi quotes, protected EARLY, protected FINAL and canonical clock.
- Generalized SCALP comes from the read-only `BTC15_COMBINED_STATE_BRIDGE_V3` endpoint.
- Existing dashboard layout is preserved. Only the existing SCALP / REVERSAL card renderer is replaced in the shadow copy.
- Contract mismatch, stale generalized-SCALP source, invalid safety envelope or feed loss must fail closed to WAIT/PASS.
- No numeric reversal-risk percentage is introduced.
- No order action is accepted or emitted.

## Shadow endpoints

- `/` — patched V13 dashboard shadow copy.
- `/dashboard_state.json` — read-only validated proxy of production main dashboard state for the shadow page.
- `/health` — shadow service health only.
- `/shadow-status` — read-only live acceptance summary comparing protected main state with combined state. It reports contract alignment, protected EARLY/FINAL preservation, canonical clock presence, safety envelope, generalized-SCALP guard state and management message.

## Promotion gate before touching production dashboard

The shadow must demonstrate:

1. build/startup tests pass,
2. locked layout remains intact,
3. protected EARLY and FINAL render unchanged,
4. generalized SCALP ACTIVE/PROTECT/EXIT render only when the combined bridge is fresh, aligned and integration-ready,
5. stale or mismatched SCALP never remains actionable,
6. at least one normal 15-minute rollover shows no prior-contract scalp leak,
7. countertrend/mixed-horizon context remains visible rather than overwriting FINAL,
8. management transitions remain responsive enough for the frozen combined smoke acceptance target,
9. no orders and no credential/account payloads appear.

Only after this shadow gate passes should the production dashboard renderer be considered for replacement. No trading threshold is changed by this checkpoint.
