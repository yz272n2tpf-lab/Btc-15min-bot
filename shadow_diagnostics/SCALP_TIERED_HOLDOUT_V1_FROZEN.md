# BTC15 Scalp Tiered Holdout V1 — Frozen Result

**Research only | signal only | no orders | no promotion**

This document freezes the first precommitted three-role holdout reveal. The role definitions were committed and tested before the holdout results below were read. They must not be retuned using these holdout outcomes.

## Source integrity

- Live reviewer: `BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3_4`
- Railway deployment: `ba6cff2b-ccb0-4c16-b753-11576bec3542`
- Event export SHA-256: `0d1ec96d8f1b86623851920eb9b0cde8fd2b3cd23900d33bb08f749b618d2324`
- Export rows: 283,308
- Fully observed contract universe: **271**
- Validation contracts: **54**
- Holdout contracts: **55**
- The fully observed 271-contract universe and baseline metrics were unchanged from the preceding V3.3 review. Additional export rows did not change the completed-contract denominator.

## Raw baseline context

- Covered contracts: **241 / 271 = 88.93%**
- Completed serial opportunities: **382**
- +10c conversion: **69.90%**
- +5c conversion: **85.60%**
- +20c conversion: **36.13%**
- <=50c contract coverage: **53.87%**
- Average entry ask: **50.02c**
- Average time remaining: **9.49m**

## Frozen role results

### PRECISION_CORE
Validation-selected rule:
- model: RANDOM_FOREST
- core threshold: 0.60
- rescue threshold: 0.60
- validation n: 36
- validation +10c: **97.22%**
- validation true contract coverage: **48.15%**

Untouched holdout report:
- holdout n: 42
- +5c: **83.33%**
- +10c: **76.19%**
- +20c: **40.48%**
- true contract coverage: **67.27%**
- <=50c true coverage: **30.91%**
- average entry ask: **52.60c**
- average time remaining: **9.46m**
- CORE-only +10c: **79.41%**
- CORE-only coverage: **52.73%**
- rescue +10c: **62.50%**
- rescue coverage gain: **14.55pp**

### BALANCED_90
Validation-selected rule:
- model: LOGISTIC
- core threshold: 0.60
- rescue threshold: 0.45
- validation n: 56
- validation +10c: **91.07%**
- validation true contract coverage: **81.48%**

Untouched holdout report:
- holdout n: 45
- +5c: **82.22%**
- +10c: **71.11%**
- +20c: **33.33%**
- true contract coverage: **69.09%**
- <=50c true coverage: **36.36%**
- average entry ask: **51.11c**
- average time remaining: **9.21m**
- CORE-only +10c: **76.47%**
- CORE-only coverage: **49.09%**
- rescue +10c: **54.55%**
- rescue coverage gain: **20.00pp**

### COVERAGE_FRONTIER
Validation-selected rule:
- model: RANDOM_FOREST
- core threshold: 0.60
- rescue threshold: 0.45
- validation n: 56
- validation +10c: **89.29%**
- validation true contract coverage: **85.19%**

Untouched holdout report:
- holdout n: 50
- +5c: **80.00%**
- +10c: **70.00%**
- +20c: **36.00%**
- true contract coverage: **81.82%**
- <=50c true coverage: **34.55%**
- average entry ask: **52.92c**
- average time remaining: **9.78m**
- CORE-only +10c: **79.41%**
- CORE-only coverage: **52.73%**
- rescue +10c: **50.00%**
- rescue coverage gain: **29.09pp**

## Decision

**NO PROMOTION.**

The validation quality spike did not survive holdout. A single quality filter is therefore not the path to simultaneously improving +10c conversion and preserving >=90% contract coverage on this dataset.

The next research target is the baseline coverage gap itself: classify the 30 fully observed contracts that produced no baseline serial scalp opportunity and determine whether they contain recoverable candidate/path structure that is currently excluded by the baseline BTC30/time/lifecycle gates, versus contracts with no usable candidate information at all.

No thresholds are changed by this document. No automatic orders. No production promotion.
