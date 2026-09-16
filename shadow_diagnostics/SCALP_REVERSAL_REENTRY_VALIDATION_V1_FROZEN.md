# BTC15 Reversal/Recross + Re-entry Ladder V1 — Frozen Validation Snapshot

**RESEARCH ONLY · SIGNAL ONLY · NO ORDERS**

Validation reviewer source SHA256: `d3239e471e202058f1960b4ef461704ca56260063cac9ecff580409a5c6aeed4`

Reviewer: `BTC15_SCALP_REVERSAL_REENTRY_LIVE_REVIEW_V1`

## Frozen causal definitions

The generalized baseline candidate gate remains unchanged: BTC30 >= 15 and >= 120 seconds left.

The legacy serial lifecycle remains unchanged: +5c executable gain arms protection; 4c giveback from running peak creates the protected exit.

A contract becomes serial-eligible only when a real protected exit has occurred and a later baseline-qualified candidate appears strictly after that exit.

- `REENTRY_CONTINUATION`: later candidate is the same side as the prior protected scalp.
- `REVERSAL_RECROSS`: later candidate is the opposite side from the prior protected scalp.
- index 1 is never a serial lane.
- an unresolved candidate or missing protected exit fails closed and cannot unlock a later scalp.

These definitions were fixed before holdout review and are not chosen using outcome labels.

## Validation snapshot

Serial-eligible contracts: **29**.

Serial union:
- 38 signals across 29 contracts
- +5: 89.47%
- +10: 81.58%
- +20: 39.47%
- average entry ask: 57.43c
- median entry ask: 62c
- <=50c entries: 44.74%
- ideal 25–35c entries: 18.42%
- average timing: 6.33 minutes left
- average MFE: 21.05c
- average MAE: -6.08c
- protected exit rate: 52.63%
- average protected exit capture: 7.33c
- max opportunity index: 3

REENTRY_CONTINUATION:
- 16 signals / 14 contracts
- +5: 93.75%
- +10: 81.25%
- +20: 43.75%
- avg ask: 63.59c
- <=50c: 37.5%
- avg timing: 6.53m left
- avg MFE: 18.81c
- avg MAE: -6.12c

REVERSAL_RECROSS:
- 22 signals / 20 contracts
- +5: 86.36%
- +10: 81.82%
- +20: 36.36%
- avg ask: 52.96c
- median ask: 46c
- <=50c: 50.0%
- ideal 25–35c: 27.27%
- avg timing: 6.18m left
- avg MFE: 22.68c
- avg MAE: -6.06c

By serial index:
- #2: 29 signals; +10 82.76%; +20 41.38%; avg timing 6.96m left
- #3: 9 signals; +10 77.78%; +20 33.33%; avg timing 4.32m left

Complementarity:
- re-entry contracts: 14
- reversal contracts: 20
- both lanes: 5
- union: 29 / 29 serial-eligible contracts

## Holdout discipline

The fixed lanes above are the only V1 lanes eligible for holdout reporting. Holdout cannot redefine lane identity, add filters, select thresholds, or promote a rule automatically. Any successor changes after holdout must be a new version/hypothesis and require fresh out-of-sample evidence.

This report's denominator is **serial-eligible contracts**, not all 15-minute contracts. The frozen Coverage Rescue prospective scorer remains authoritative for true all-contract coverage.
