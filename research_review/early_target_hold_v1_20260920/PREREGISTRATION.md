# BTC15 EARLY Target Hold V1 — preregistration

**Status:** FROZEN BEFORE SCORING  
**Mode:** READ-ONLY RESEARCH | SIGNAL ONLY | NO ORDERS

## Objective

EARLY predicts the official final UP/DOWN settlement side of the same 15-minute Kalshi contract. Primary metric is official settlement directional accuracy.

## Development source

Use only the already-existing settled sub-minute historical dataset:
`subminute_early_dataset_v1.csv`

This is development evidence, not a new untouched holdout. Do not access the post-fix clean validation window.

## Candidate: EARLY_TARGET_HOLD_V1

For each contract and each side, scan chronologically and emit at most one call, the earliest row satisfying all conditions:

1. **7.0 to 10.0 minutes** remaining.
2. Actual side ASK **<=50c**.
3. Candidate side is currently ahead of the exact target: `btc_gap_side >= $40`.
4. At least **10 observations** exist over the trailing 60 seconds.
5. The candidate side remained continuously ahead of target over that trailing minute.
6. The minimum `btc_gap_side` over the trailing minute is **>= $15**.
7. Current `btc_gap_side` is **>=** the first observed `btc_gap_side` in that trailing minute (no net erosion of the target cushion).
8. Current side-aligned 15s and 30s BTC moves are both **>= 0**.
9. Missing required data fails closed.

If both sides could qualify at the same timestamp, choose the side with larger positive `btc_gap_side`; exact ties produce no call.

No model fair threshold, no breakout/retest, no excursion label, and no post-entry information are used.

## Frozen advancement gate

Advance only if ALL are true:
- >=10 calls
- overall official settlement accuracy >=93%
- each chronological half >=90% accuracy where >=4 calls exist
- every entry <=50c
- average ASK <=40c
- average minutes remaining >=7.0
- both UP and DOWN represented

If it fails, do not adjust thresholds from the result. Record rejection.

## Guardrails

- FINAL unchanged.
- SCALP unchanged.
- Production/BRTI/Kalshi plumbing unchanged.
- Clean post-fix validation window untouched.
- SIGNAL ONLY / NO ORDERS.
