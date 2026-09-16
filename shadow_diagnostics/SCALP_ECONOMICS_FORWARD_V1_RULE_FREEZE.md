# BTC15 Scalp Economics Forward V1 — Rule Freeze

**Mode:** SHADOW ONLY / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION  
**Cutoff:** intentionally not stamped in this file; timestamp is created only after CI passes.  

## Frozen accounting

- Detector and serial opportunity construction unchanged.
- Entry = executable candidate ASK.
- Protection lifecycle unchanged: +5c arm / 4c giveback.
- Realized gross gain exists only when a protected executable exit BID is observed.
- +5/+10/+20 touches are movement telemetry, not realized P&L.
- Unprotected paths never receive a fabricated realized exit.
- Conservative certification view = TAKER_TAKER.
- Fee schedule model = Kalshi general event-contract formula effective 2026-07-07.
- 1-contract and 10-contract lots are both required for the break-even evidence gate.
- Maker-entry and 100-contract views remain diagnostics only.

## Frozen prospective denominator

A contract can enter the forward universe only when:

1. its first passive observation is at or after the later stamped cutoff; and
2. it is proven fully observed by the existing denominator semantics (observed >=840 seconds left and <=60 seconds left).

## Sample readiness

- overall: >=100 future fully observed contracts AND >=50 protected exits
- scalp #1: >=40 protected exits
- scalp #2: >=20 protected exits
- scalp #3+: >=20 protected exits

All lane gates also require the >=100 future fully observed contract universe.

## Break-even evidence conditions

For each ready lane, **both** 1-contract and 10-contract TAKER_TAKER views must satisfy:

- average net gain per contract > 0c
- median net gain per contract > 0c
- positive-net protected-exit rate > 50%

These are economic break-even-style evidence conditions, not optimized return targets.

## Lane isolation

The forward ledger reports independently:

- OVERALL
- SCALP_1
- SCALP_2
- SCALP_3_PLUS

A weak late ladder cannot inherit a pass from stronger scalp #1/#2 economics.

## Decision semantics

- `sample_ready` means enough prospective evidence exists for that lane.
- `manual_review_break_even_evidence_pass` is an evidence flag only.
- no automatic promotion or production change can occur from this scorer.
- no thresholds may be altered using results from the prospective window.

## Safety

- signal-only
- manual execution only
- no order capability
- no production writes
- no automatic promotion
- frozen Coverage Rescue V1 remains independent and untouched
