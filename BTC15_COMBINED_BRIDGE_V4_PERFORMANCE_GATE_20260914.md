# BTC15 Combined Bridge V4 Performance Gate — 2026-09-14

**Frozen before live V4 performance results**  
**Mode:** READ ONLY | SIGNAL ONLY | NO ORDERS

## Problem being solved

The proven combined-state bridge preserves protected EARLY, protected FINAL and frozen generalized SCALP, but the older integration path re-read the entire persistent SCALP CSV for each `/state` / `/combined-state` request and observer tick. A shadow-dashboard startup request exceeded 3 seconds and failed closed. This is an integration-read-path performance problem, not a signal-quality problem.

## Fixed V4 design

- The exact generalized collector remains unchanged.
- The persistent event CSV remains append-only and is never modified by the cache.
- One full CSV read is allowed at V4 startup.
- After startup, the cache consumes only newly appended bytes.
- Frozen SCALP qualification remains seconds-left >=120 plus side-aligned btc30 >=$15.
- Frozen management remains +5c arm and 4c giveback EXIT with EXIT latching.
- Protected EARLY and FINAL are not recomputed or weakened.
- Contract mismatch, stale source, malformed input and unavailable upstream state continue to fail closed.
- No numeric reversal-risk percentage is introduced.
- No orders.

## Required parity checks

Before V4 can replace the older read path, cache-backed state must match full-tape state for:

1. current contract selection,
2. primary frozen candidate selection,
3. ACTIVE state,
4. +5c PROTECT/armed state,
5. first 4c giveback EXIT,
6. EXIT staying latched after later recovery,
7. contract rollover removing prior-contract actionability,
8. stale-source fail-closed behavior,
9. contract-mismatch fail-closed behavior.

## Performance acceptance

The integration target is inherited from the already-frozen combined smoke: a real event-tape change into PROTECT or EXIT should reach the integration/dashboard path within 3 seconds under normal service health.

For V4 specifically:

- there must be no full-tape `read_rows()` call in the normal request or observer path after cache initialization,
- cache polling is fixed at 250ms and is an integration transport cadence, not a trading threshold,
- live `/combined-state` must no longer exhibit the repeated whole-tape-read bottleneck seen in V3,
- any timeout or cache fault must fail closed rather than extending stale actionability.

Passing these checks earns replacement of the V3 read path only. It does not alter or re-promote any trading rule.
