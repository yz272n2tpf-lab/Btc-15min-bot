# BTC15 Raw Baseline Coverage Gap Audit V1 — Frozen Real-Tape Result

**Research only | signal only | no orders | no automatic promotion**

This document freezes the first real-tape audit of fully observed contracts not covered by the current raw serial scalp baseline. The hindsight opportunity ceiling below is diagnostic only and must never be treated as a live signal or certified strategy result.

## Source

- Live reviewer: `BTC15_SCALP_BASELINE_GAP_LIVE_REVIEW_V1`
- Railway deployment: `a7c2f378-aa95-44f2-9d52-58772aced3e5`
- Source SHA-256: `fe79ea2db2b60e72268b7ced4c46c9421cdbea4af8043e94b4593dfe79ae16fb`
- Source bytes: 180,318,003
- Source rows: 283,993
- Fully observed contracts: **272**

## Current raw baseline

- Covered contracts: **242 / 272 = 88.9706%**
- Uncovered contracts: **30**
- Contracts needed to reach 90% true coverage on this fixed sample: **3**

## Why the 30 contracts were missed

- `NO_CANDIDATE_ROWS`: **18**
- `BTC30_BELOW_BASELINE_15`: **6**
- `LATE_ONLY_CANDIDATES`: **2**
- `QUALIFIED_CANDIDATE_NO_RESULT`: **2**
- `SERIAL_LIFECYCLE_BLOCKED`: **2**

## Hindsight opportunity ceiling inside the 30 missed contracts

These are labels describing what later happened in already-collected candidate paths. They are **not** causal signal results.

- Missed contracts with any complete candidate path: **12**
- Missed contracts with any later executable +5c: **9**
- Missed contracts with any later executable +10c: **9**
- Missed contracts with any later executable +20c: **2**
- Missed contracts with an EARLY +10c opportunity: **8**
- Missed contracts with an <=50c +10c opportunity: **6**
- Missed contracts with an EARLY AND <=50c +10c opportunity: **5**
- Missed contracts with a +10c path from a candidate that did not meet the current raw baseline: **9**

## Interpretation locked before next build

The raw 88.97% contract reach is not at its structural ceiling. The collected tape contains recoverable movement in some uncovered contracts. Since only three additional covered contracts would cross 90% on this sample, a narrow non-overlapping gap lane may be sufficient; the current baseline does **not** need to be weakened.

The largest absolute gap category is `NO_CANDIDATE_ROWS` (18/30), which requires upstream/passive-snapshot regime detection rather than merely changing a quality classifier. However, the candidate-bearing uncovered contracts provide a smaller and safer first target for a gap-recovery lane.

## Change control

1. Do not lower the existing baseline BTC30 >=15 gate globally from this hindsight audit.
2. Do not retune the failed V3.4 quality tiers on their revealed holdout.
3. Any new gap detector built from this observed tape is development-only.
4. Freeze the new detector before evaluating on a new prospective forward window.
5. Keep baseline and gap-lane scores separate, then report their contract-union coverage.
6. Keep <=50c economics and timing as first-class metrics.
7. No orders.
