# BTC15 Combined-State Bridge Checkpoint — 2026-09-14

**Mode:** SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

## Completed in this integration pass

1. Added `scalp_integration_state_bridge_v4.py`.
   - Keeps the frozen generalized SCALP qualification and management thresholds unchanged.
   - Adds source-event freshness metadata.
   - Stale source data fails closed for integration instead of remaining actionable.
   - Main protected dashboard remains authority for contract and canonical clock.

2. Added `btc15_cross_service_payload_v3.py`.
   - Requires contract alignment and a fresh/ready SCALP source before ACTIVE/PROTECT/EXIT may compose.
   - A stale or mismatched SCALP becomes PASS for the protected combined timeline.
   - Protected EARLY and FINAL are passed through unchanged.

3. Added `btc15_combined_state_bridge_v1.py`.
   - `/state` exposes the read-only generalized SCALP V4 state.
   - `/combined-state` composes protected main EARLY/FINAL/canonical timing with generalized SCALP.
   - Malformed/unavailable main state returns a fail-closed 503 instead of fabricating actionability.
   - No credential/account/order data is added.

4. Added `btc15_combined_state_bridge_v2.py`.
   - Adds a read-only 1-second transition observer so contract sync, freshness, timer alignment, protected EARLY/FINAL, SCALP management, and rollover behavior can be inspected before changing production dashboard UI.

## Regression status

The first V4 deployment preflight ran **25 tests — PASS**.

The combined-state V1 deployment preflight then ran **42 tests — PASS** and started the exact frozen Full-Time V2 collector unchanged (`SHA256 52b79e...`, SIGNAL ONLY, NO ORDERS).

## Deployment issue caught and fixed

A V4 deployment initially failed Railway promotion even though all tests passed and the process was healthy. Root cause: Railway healthcheck was pointed at inherited `/health`, which can require the research/export authorization token. The public signal-only `/state` endpoint is the correct integration healthcheck.

Fix:
- Railway healthcheck changed to `/state`.
- No trading threshold, signal rule, event tape, or order behavior changed.
- The next combined-state V1 deployment promoted successfully.

## Current safety invariants

- Protected FINAL unchanged.
- Protected Tier-1 EARLY unchanged.
- Frozen generalized SCALP unchanged.
- EXIT latch preserved.
- Stale SCALP source fails closed.
- Contract mismatch fails closed.
- Canonical clock comes from protected main dashboard.
- No numeric reversal-risk percentage is fabricated.
- No orders.

## Next integration gate

Run the V2 combined transition observer against live protected main state, verify the composed payload on real contract rollovers and management transitions, then wire only the proven combined state into the existing dashboard cards. Do not rewrite protected trading logic during UI wiring.
