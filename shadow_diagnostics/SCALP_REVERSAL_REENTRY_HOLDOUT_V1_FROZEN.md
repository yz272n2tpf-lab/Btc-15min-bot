# BTC15 Reversal/Recross + Re-entry Ladder V1 — Frozen Holdout Result

**RESEARCH ONLY · SIGNAL ONLY · NO ORDERS · NO V1 RETUNE AFTER HOLDOUT**

Holdout reviewer source SHA256: `e90782256132273fcbb2174d25a9263fac892a1919e78034af57cf19144c6472`

Reviewer: `BTC15_SCALP_REVERSAL_REENTRY_HOLDOUT_REVIEW_V1`

Coverage in this report means **retention of serial-eligible contracts**, not all 15-minute contracts. The frozen Coverage Rescue forward scorer remains authoritative for true all-contract coverage.

## Fixed lane definitions

The lane definitions were frozen before holdout:

- `REENTRY_CONTINUATION`: later baseline-qualified scalp candidate is the same side as the prior scalp, strictly after a real +5c-arm / 4c-giveback protected exit.
- `REVERSAL_RECROSS`: later candidate flips side vs the prior protected scalp.
- index 1 is not a serial lane.
- unresolved candidate or missing protected exit fails closed.
- baseline candidate gate remains BTC30 >=15 and >=120 seconds left.

No holdout result selected a lane definition or threshold.

## Validation vs holdout

### SERIAL_UNION
Validation:
- serial-eligible contracts: 29
- signals: 38
- serial contract retention: 100%
- +5: 89.47%
- +10: 81.58%
- +20: 39.47%
- avg ask: 57.43c; median 62c
- <=50c: 44.74%
- avg timing: 6.33m left
- avg MFE: 21.05c; avg MAE: -6.08c
- avg protected exit capture: 7.33c

Holdout:
- serial-eligible contracts: 26
- signals: 34
- serial contract retention: 100%
- +5: 79.41%
- +10: 52.94%
- +20: 26.47%
- avg ask: 43.52c; median 43.5c
- <=50c: 58.82%
- ideal 25–35c: 8.82%
- avg timing: 6.52m left
- avg MFE: 15.91c; avg MAE: -5.16c
- protected exit rate: 55.88%
- avg protected exit capture: 4.72c

### REENTRY_CONTINUATION
Validation:
- 16 signals / 14 contracts
- +10: 81.25%
- +20: 43.75%
- <=50c: 37.5%
- avg ask: 63.59c

Holdout:
- 16 signals / 15 contracts
- +5: 87.5%
- +10: 56.25%
- +20: 18.75%
- <=50c: 56.25%
- avg ask: 45.07c; median 42.5c
- avg timing: 6.57m left
- avg protected exit capture: 3.87c

### REVERSAL_RECROSS
Validation:
- 22 signals / 20 contracts
- +10: 81.82%
- +20: 36.36%
- <=50c: 50.0%
- avg ask: 52.96c; median 46c

Holdout:
- 18 signals / 16 contracts
- +5: 72.22%
- +10: 50.0%
- +20: 33.33%
- <=50c: 61.11%
- avg ask: 42.14c; median 44c
- avg timing: 6.48m left
- avg protected exit capture: 5.88c

### By opportunity index
#2 validation: 29 signals, +10 82.76%, +20 41.38%, avg timing 6.96m left.
#2 holdout: 26 signals, +10 53.85%, +20 26.92%, avg timing 7.38m left.

#3 validation: 9 signals, +10 77.78%, +20 33.33%, avg timing 4.32m left.
#3 holdout: 8 signals, +10 50.0%, +20 25.0%, avg timing 3.72m left.

## Complementarity
Validation: re-entry 14 contracts, reversal 20, both 5, union 29/29 serial-eligible.
Holdout: re-entry 15 contracts, reversal 16, both 5, union 26/26 serial-eligible.

The two lane identities remain complementary across splits, but their movement conversion degraded materially out of sample.

## Decision

`NO_PROMOTION_V1`.

The serial lane architecture is useful descriptive structure, and it preserves the distinction between same-side re-entry and opposite-side reversal. However, the validation +10 rates around 81% did not generalize to holdout (~53% union). V1 must not be retuned after this reveal.

Any successor must be labeled a new hypothesis/version, may use the V1 result only as development evidence, and must require a fresh prospective window before promotion.
