# BTC15 Combined System Fixture Result V1

**Date:** 2026-09-14  
**Mode:** PURE OFFLINE INTEGRATION VALIDATION | SIGNAL ONLY | NO ORDERS

## Purpose

Verify the already-frozen integration semantics before wiring the composer around live/protected module outputs.

This test does **not** change or re-qualify EARLY, FINAL, or SCALP rules.

## Test run

Railway deployment used only as an execution host and then immediately returned to the read-only scalp collector process.

- Deployment: `6d2f057e-d3ae-4375-af1d-9251bb67015c`
- Integration unit tests: **9/9 PASS**
- Deterministic combined fixtures: **15**
- Module-preservation comparisons: **45**
- Fixture scorecard result: **PASS**
- Test process exits: `INTEGRATION_TEST_EXIT=0`, `FIXTURE_EXIT=0`

## What passed

The deterministic fixture set verified:

- protected EARLY payload values survive composition unchanged
- protected FINAL payload values survive composition unchanged
- frozen SCALP payload values survive composition unchanged
- `WATCH` never counts as actionable
- union actionability is one boolean per contract and never double-counts active paths
- EARLY + FINAL alignment is labeled `ALIGNED`
- EARLY / FINAL disagreement is labeled `EARLY_FINAL_DIVERGENCE` + `MIXED_HORIZONS`
- countertrend SCALP vs FINAL is labeled `COUNTERTREND_SCALP` + `MIXED_HORIZONS`
- SCALP `PROTECT` / `EXIT` has display priority without deleting FINAL state
- FINAL `LOCK` keeps priority over ordinary SCALP `ACTIVE`
- low-price and high-price SCALP fixtures both remain actionable, proving the composer does not invent a SCALP price filter
- no order field exists
- manual execution flag remains true
- no unvalidated numeric flip-risk percentage is emitted

## Fixture union number is not empirical coverage

The fixture run produced `14/15` union-actionable scenarios because the fixture set intentionally contains fourteen actionable state combinations and one all-non-actionable control.

**This is a deterministic correctness test, not a claim that live union actionable coverage is 93.3%.**

Empirical union coverage must be calculated only after real protected module outputs are wired on a common contract timeline.

## Live collector safety check

After both offline checks completed, the same deployment transitioned back to:

- `PATH EXPORT BRIDGE V1 START`
- `SCALP MOVE SHADOW V2 START`
- BRTI `PRIMARY_OK`
- live contract heartbeat
- `NO ORDERS`

No trading threshold was changed.

## Decision

**PASS — integration composer semantics are ready for the next engineering step.**

## Next step

Wire `btc15_signal_integration_v1.py` around the existing protected EARLY, FINAL, and SCALP outputs without rewriting those modules, then run a short integrated smoke test focused on:

- exact 15-minute contract/timer alignment
- state transitions
- FINAL no-longer-waits-to-zero behavior
- SCALP ACTIVE -> PROTECT -> EXIT presentation/timing
- conflict labels
- dashboard-facing payload completeness
- SIGNAL ONLY / NO ORDERS
