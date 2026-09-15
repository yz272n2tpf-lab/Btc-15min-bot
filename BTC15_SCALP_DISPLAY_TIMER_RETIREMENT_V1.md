# BTC15 SCALP DISPLAY TIMER RETIREMENT V1

STATUS: SHADOW UI DECISION — NO TRADING LOGIC CHANGE

## Decision

Remove the duplicate `Contract time left` row from the SCALP / REVERSAL card.
The existing top-right main CONTRACT TIMER remains the only visible contract countdown.

## What this does NOT change

- SCALP still scans the full 15-minute contract continuously.
- Internal seconds-left / contract timing data remains available to qualification, safety checks, scoring, and research.
- The serial ladder can continue producing later scalps after a validated prior lifecycle terminal.
- +5c protection arm and first 4c giveback EXIT are unchanged.
- Contract alignment, source freshness, and integration readiness remain fail-closed guards.
- Kalshi entry price remains telemetry only; no price filter is introduced.
- EARLY and FINAL are untouched.
- SIGNAL ONLY / MANUAL EXECUTION / NO ORDERS remains unchanged.

## Why

The duplicate SCALP countdown added no useful decision information for manual use and created avoidable visual sync churn. The top-right contract timer is clearer and already authoritative for the user.

## Acceptance

The SCALP card should retain entry, current bid, executable gain, running peak, giveback from peak, management state, protection rule, and context while showing no second contract countdown.
