# BTC15 Direct-BRTI Flip Risk Model Freeze Addendum V1

Status: **PREDECLARED BEFORE FIRST MODEL FIT**.

This addendum resolves implementation details left implicit in
`BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_20260915.md`. It does not change the
feature set, data universe, block assignments, or acceptance thresholds.

## Platt calibrator
The one-dimensional calibration model is fixed as:
- `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=2000)`
- no class weights
- input = clipped base-model logit in [-12,+12]
- output class `flip=1` probability.

## Reliability bins
Fixed flip-probability bins:
- [0.00,0.05)
- [0.05,0.10)
- [0.10,0.20)
- [0.20,0.30)
- [0.30,0.40)
- [0.40,0.50)
- [0.50,0.60)
- [0.60,0.70)
- [0.70,0.80)
- [0.80,0.90)
- [0.90,0.95)
- [0.95,1.001)

Weighted absolute calibration error weights each populated bin by its OOS
snapshot count. Maximum-bin error gate uses only bins with n>=30.

Spearman reliability correlation is computed between each populated bin's
**average stated flip probability** and **actual flip frequency** for bins with
n>=20.

## Aggregate weighting
Aggregate raw, calibrated, and null Brier scores weight every eligible OOS
snapshot equally. Each OOS row uses the training-prior null probability from its
own walk-forward block.

## Snapshot tie-breaking
For each frozen target remaining minute, choose the tape row with smallest
absolute difference from target seconds-left. If tied, choose the earlier UTC
row. Absolute difference must be <=7.5 seconds.

## Time-bucket safety
Time-conditioning buckets are the frozen target remaining-minute labels
`9,8,7,6,5,4,3,2,1`. For each bucket with n>=20 OOS snapshots, compare mean
calibrated flip probability with actual flip frequency; absolute error must be
<=15 percentage points.

## No post-result edits
These definitions are frozen before the first direct-BRTI model fit. If the
study fails, do not alter them on the same OOS cohort.
