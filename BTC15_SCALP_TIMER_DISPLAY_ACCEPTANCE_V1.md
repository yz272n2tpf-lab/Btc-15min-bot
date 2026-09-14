# BTC15 SCALP TIMER DISPLAY ACCEPTANCE V1

STATUS: SHADOW DISPLAY GATE — NO TRADING LOGIC CHANGES

Purpose: prevent the SCALP card from showing a visibly different contract countdown than the main dashboard.

## Authority

- The existing main dashboard CONTRACT TIMER is the canonical displayed clock.
- The SCALP card must mirror that same visible MM:SS value when available.
- Combined-bridge `canonical_seconds_left` is a display fallback only if the main timer cannot be read.
- Backend timer delta remains diagnostic and must never alter SCALP qualification or management.

## Pass criteria

1. Main timer and SCALP card time show the same MM:SS during normal operation.
2. Contract rollover updates both displays to the new contract without a stale prior-contract value.
3. If the main timer is temporarily unavailable, the SCALP card fails safely to the bridge fallback rather than inventing a time.
4. ACTIVE / PROTECT / EXIT state behavior is unchanged.
5. Contract-alignment, source-freshness, and integration-ready backend guards remain mandatory.
6. EARLY and FINAL logic/rendering remain untouched.
7. SIGNAL ONLY / MANUAL EXECUTION / NO ORDERS remains unchanged.

## Promotion rule

Do not copy the V6 timer-display patch into production until one live shadow screenshot confirms the main timer and SCALP timer visually agree on the same contract.
