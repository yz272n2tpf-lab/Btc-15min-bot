# BTC15 EARLY → FINAL HANDOFF FORWARD FREEZE — 2026-09-15

## Status
PREDECLARED BEFORE LIVE HANDOFF COLLECTION.

READ ONLY · SIGNAL ONLY · MANUAL EXECUTION ONLY · NO ORDERS · NO AUTO-PROMOTION.

## Purpose
Measure the actual two-signal workflow contract-by-contract:
1. first already-protected EARLY `QUALIFIED` opportunity;
2. first already-protected FINAL `LOCK`;
3. elapsed handoff time, side confirmation/flip, Kalshi price progression, coverage, and official settlement context.

This observer does **not** create, recalculate, weaken, strengthen, or replace either signal.

## Authority inputs
- EARLY authority: `btc15_main_protected_state_adapter_v1.early_state_from_main()` reading protected production EARLY state.
- FINAL authority: `btc15_main_protected_state_adapter_v1.final_state_from_main()` reading protected production FINAL state.
- Production dashboard state is read from `https://btc-15min-bot-production.up.railway.app/dashboard_state.json`.
- Official settlement is descriptive/scoring truth only and cannot influence a live signal.

## Fresh-sample rule
- Startup contract is excluded.
- Collection arms on the first post-start rollover.
- No pre-start/pre-rollover signal can enter the sample.

## Coverage universe
A contract is eligibility-complete only if this observer first sees it with **>=600 seconds left**.

Reason: protected EARLY cannot qualify before the 10-minute-remaining window opens. Seeing the contract before that point gives complete observability for both EARLY and FINAL. Any contract first seen below 600 seconds is excluded fail-closed from coverage statistics.

## Frozen review gate
All three are required:
- **>=30 eligibility-complete contracts**;
- **>=10 contracts with both protected EARLY and protected FINAL**;
- **>=12 officially settled protected FINAL locks**.

Reaching this gate earns **manual review only**. It does not authorize a rule change or production promotion.

## Frozen metrics
Per contract / aggregate:
- EARLY-only coverage;
- FINAL-only coverage;
- union/any-signal coverage;
- dual-anchor coverage;
- EARLY-only / FINAL-only / no-anchor counts;
- first EARLY side, ask, fair, edge, minutes remaining;
- EARLY 25–35c count/rate;
- EARLY <=50c count/rate;
- first FINAL side, locked-side ask, fair, minutes remaining;
- FINAL <=50c count/rate;
- EARLY→FINAL elapsed handoff minutes;
- EARLY/FINAL side agreement rate;
- same-side Kalshi ask change from EARLY to FINAL;
- official FINAL accuracy for settled FINAL locks;
- EARLY same-side-as-settlement rate labeled **secondary directional context**, never FINAL accuracy.

## Safety invariants
- First protected EARLY is immutable once recorded for a contract.
- First protected FINAL is immutable once recorded for a contract.
- A later flip does not rewrite the earlier state; it is measured as a flip.
- Locked-side FINAL ask must come from the matching UP/DOWN Kalshi ask.
- Late-discovered contracts are excluded rather than backfilled.
- Observer/watchdog may restart only the read-only collector worker.
- No order-placement path exists.
- No signal threshold is implemented in this auditor.

## Implementation
- Auditor: `BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`
- Auditor commit: `8c6ebedb14eea11072c0acc1404aa0b68fabb7be`
- Tests: `test_BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`
- Test commit: `cb05a536a1164132d4a4b872bb90b7bcd1a804d3`
- Railway service (isolated): `early-final-handoff-v1`
- Service ID: `174bd89d-264b-4882-8d5a-b8dbacf97181`
- Correct research deployment must be on branch `scalp-move-shadow-v1-20260912`; the automatic bootstrap `main` snapshot is non-authoritative.

## Decision rule
Do not tune this handoff study after collection starts. If the frozen sample exposes a weakness, diagnose it in a **new named research hypothesis** with a new future-only sample. Do not rewrite this sample or gate.
