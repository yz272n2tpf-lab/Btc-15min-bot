# BTC15 Direct-BRTI Flip Risk Model Study Freeze — 2026-09-15

## Status
**PREDECLARED BEFORE ANY DIRECT-BRTI MODEL FIT.**

READ ONLY · RESEARCH ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS.

Historical Coinbase-based Flip Risk calibration passed its historical gate but
failed live feature parity (7/20 exact). Therefore this is a **new model study**,
not a substitution of BRTI values into the old model.

## Frozen data authority
Primary tape: `kalshi_direct_brti_parity_v1.csv`.

Inventory V1:
- 16,642 rows / 100 contracts;
- median cadence 5.000s; p95 5.038s;
- 100/100 contracts have within-contract p95 spacing <=8s;
- BRTI ready on 99.11% of rows;
- median BRTI age 1.159s, p95 1.876s;
- 97/100 first seen with >=10m remaining;
- 94/100 meet the conservative feature-usable definition;
- no model was fit during inventory.

Official truth refresh:
- targeted public Kalshi GET only;
- 100/100 tape contracts finalized with official UP/DOWN result;
- 94/94 feature-usable contracts have official truth;
- 0 fetch errors / 0 missing results;
- complete final60 proxy agreed with official truth on 53/53, but **final60 is
  never allowed as the model label**.
- Official truth refresh reference deployment:
  `bc77e89b-ba38-432c-a33d-b5efef98f406`.

## No-second-zero rule
The model MUST NOT use exact contract-start BRTI or `move_from_start` because
live broad/exact discovery can begin several seconds after canonical start.
No synthetic start value may be backfilled.

Allowed model inputs must be reproducible causally from already-observed direct
BRTI tape plus the fixed Kalshi target and canonical seconds remaining.

## Frozen snapshot grid
One candidate snapshot per contract at each target remaining time:
**9, 8, 7, 6, 5, 4, 3, 2, 1 minutes left**.

For each target minute, use the closest observed row within +/-7.5 seconds.
The chosen snapshot and all lag inputs must be causal: no future row may be used
for a lagged feature. Snapshot must have `direct_brti_ready=True` and BRTI age
<=5 seconds.

A snapshot is eligible only if at least 300 seconds of observed BRTI history is
available and the 5-minute feature window has:
- >=50 BRTI samples;
- no observed within-window gap >8 seconds.

Missing/incomplete snapshots are excluded fail-closed; no imputation.

## Frozen direct-BRTI feature set
Exactly these 12 features, with no feature search on test blocks:

1. `remaining_min`
2. `current_side_sign` (+1 UP, -1 DOWN; exact target ties excluded)
3. `signed_dist_target_pct = (BRTI-target)/target`
4. `abs_dist_target_pct`
5. `dist_per_min_remaining_pct = abs_dist_target_pct / remaining_min`
6. `aligned_move_1m_pct`
7. `aligned_move_2m_pct`
8. `aligned_move_3m_pct`
9. `aligned_move_5m_pct`
10. `brti_range_5m_pct = (max-min)/current_BRTI`
11. `brti_vol_5m` = sample standard deviation of causal 5-second BRTI returns
    inside the prior 5-minute window
12. `dist_over_range_5m = abs(BRTI-target) / max(BRTI_range_5m_dollars, 1e-6)`

For aligned moves:
- locate the latest causal BRTI observation at or before now-lag;
- it must be no more than 7.5 seconds older than the requested lag time;
- raw move pct = `(current/past)-1`;
- aligned move = raw move pct * current_side_sign.
Positive means momentum supports the current side; negative means reversal
pressure.

No Coinbase OHLC, volume, TradingView indicator, Kalshi price, FINAL output,
EARLY output, scalp state, future BRTI, or settlement information is a feature.

## Frozen label
`flip=1` iff the direct-BRTI current side at the snapshot differs from the
**official finalized Kalshi settlement side** for that contract. Otherwise 0.
Flat/tie snapshots are excluded.

## Frozen model family
Base model only:
- `StandardScaler`
- `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=2000)`
- no class weights
- fixed random behavior / no hyperparameter sweep.

Probability calibrator:
- Platt/sigmoid calibration only;
- fit a separate one-dimensional logistic regression on the base model logit
  from the calibration contracts;
- logits clipped to +/-12 before calibration for numerical stability.

No isotonic-vs-sigmoid tournament. No model-family tournament.

## Frozen chronological walk-forward blocks
Order the 94 usable contracts by their first tape timestamp. The model may use
only contracts earlier than its test block.

- Block 1: train contracts indices 0:40; calibration 40:50; test 50:65.
- Block 2: train 0:55; calibration 55:65; test 65:80.
- Block 3: train 0:70; calibration 70:80; test 80:94.

Test blocks are disjoint. A contract that was an earlier test may become
historical calibration/training data for a later block; this is legitimate
walk-forward use because time only moves forward.

No contract may appear in train/calibration/test simultaneously within a block.

## Frozen null comparator
For each block, the null flip probability is the empirical flip rate among all
eligible **training snapshots only** in that block. Test Brier skill is:
`1 - calibrated_brier / null_brier`.

## Frozen historical screening gate
This study can advance only to a **fresh read-only shadow Flip Risk collector**
if all are true:

### Integrity
- 94-contract order and block assignments are deterministic and chronological.
- train/calibration/test contract sets are disjoint within every block.
- official Kalshi settlement is the only label source.
- all features pass causal lag checks; no future row used.
- no exact-second-zero/start feature exists.

### OOS sample
- all three test blocks run;
- >=40 unique OOS test contracts total;
- >=250 eligible OOS snapshots total.

### Probability quality
- aggregate calibrated Brier <= aggregate raw Brier;
- calibrated Brier improves or ties raw Brier in >=2 of 3 test blocks;
- aggregate calibrated Brier skill vs the frozen training-prior null >=5%;
- weighted absolute calibration error across reliability bins with n>=20 <=5pp;
- no reliability bin with n>=30 has absolute error >10pp;
- Spearman correlation between stated and actual flip rate across populated
  reliability bins (n>=20) >=0.80, with >=3 populated bins.

### High-confidence stay calibration
For snapshots with calibrated `stay_prob >=90%`:
- >=30 OOS snapshots;
- >=8 distinct OOS contracts;
- actual stay rate >=90%.

### Time-conditioning safety
For each remaining-minute bucket with >=20 OOS snapshots, absolute error between
average stated flip risk and actual flip frequency must be <=15pp.
Any failing populated time bucket blocks historical PASS rather than being
silently hidden after seeing results.

## Meaning of PASS
Historical PASS authorizes only:
1. freezing a future-only direct-BRTI shadow sample;
2. running the numeric Flip Risk model read-only beside the dashboard;
3. collecting >=30 eligibility-complete fresh contracts before any proposal to
   show the number to the user.

It does **not** authorize:
- production integration;
- a user-facing numeric Flip Risk field;
- changing FINAL/EARLY/SCALP/LOCK/PASS/entry/protection/exit logic;
- orders.

## Meaning of FAIL
Do not tune this same OOS cohort. Diagnose failure morphology first and
predeclare any new model/feature/calibration method on a new holdout/future
sample.
