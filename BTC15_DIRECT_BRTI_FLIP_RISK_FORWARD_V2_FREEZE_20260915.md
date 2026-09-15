# BTC15 Direct-BRTI Flip Risk Forward V2 Freeze — 2026-09-15

## Status
**PREDECLARED BEFORE ANY V2 FUTURE OUTCOME IS SCORED.**

READ ONLY · SHADOW ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS.

## Why V2 exists
Direct-BRTI V1 had useful out-of-sample ranking/skill but failed the probability
calibration gate:
- aggregate calibrated Brier skill vs null = +9.48%;
- 2/3 chronological blocks improved/tied raw Brier;
- reliability Spearman = 0.90;
- but weighted calibration error = 8.88pp (>5pp);
- worst populated-bin error = 15.83pp (>10pp);
- `stay >=90%` actual stay = 89.39% (<90%).

Therefore V1 is closed on its historical OOS cohort. V2 does **not** change the
12 direct-BRTI features or the logistic base model. It changes only the
probability calibrator from Platt/sigmoid to monotonic isotonic calibration and
is judged on new future contracts only.

## Frozen historical training recipe
Historical tape: `kalshi_direct_brti_parity_v1.csv`.

Use the exact 94 feature-usable contracts and exact 12-feature definitions from
`BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_20260915.md` and its addendum.
Official finalized Kalshi settlement remains the only historical label source.

Chronological contract order is fixed by each contract's first tape timestamp.

### Base model training set
- contracts indices **0:70** only.
- model = `StandardScaler` +
  `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=2000)`.
- no class weights.
- no feature changes.

### Isotonic calibration set
- contracts indices **70:94** only.
- base model is not refit on these 24 contracts.
- obtain raw flip probabilities from the frozen base model.
- fit `sklearn.isotonic.IsotonicRegression(out_of_bounds='clip', increasing=True)`
  to raw probability -> official flip label.
- no threshold sweep, no calibrator tournament.

This 70/24 historical split is training/calibration only. It is **not** used to
claim V2 performance. Only future contracts after the V2 collector cutoff may
validate V2.

## Frozen live feature source
Production remains untouched. The shadow reads only:
`https://btc-15min-bot-production.up.railway.app/dashboard_state.json`

Live inputs:
- `contract`
- canonical `timer.seconds_left`
- fixed Kalshi `market.target`
- direct `market.brti_value`
- BRTI samples in `chart.points[*].t` + `chart.points[*].brti`

No Coinbase data, TradingView values, EARLY, SCALP, FINAL, Kalshi odds, future
BRTI, settlement, or exact contract-start price is a prediction feature.

## Fresh-start / coverage universe
- Startup contract is excluded.
- Collection arms on the first post-start contract rollover.
- A future contract is coverage-eligible only if first observed with
  **>=840 seconds left** (before 14:00 remaining).
- This provides at least five minutes of causal observed BRTI history before the
  frozen first prediction target at 9:00 remaining under normal <=8s cadence.
- A contract first seen below 840s is excluded fail-closed; never backfilled.

## Frozen future prediction grid
Attempt one prediction at each remaining-minute target:
**9, 8, 7, 6, 5, 4, 3, 2, 1 minutes left**.

A target is captured only when the observer sees canonical seconds-left within
+/-7.5s. Tie/duplicate behavior: first valid captured prediction wins and is
immutable.

The live feature calculation uses the same causal requirements as V1:
- current direct BRTI valid and >0;
- exact target valid and >0;
- exact target ties excluded;
- current BRTI age <=5s when an age field is available;
- >=300s of chart BRTI history;
- >=50 BRTI samples in prior 5m;
- no within-window BRTI timestamp gap >8s;
- lag prices at 1/2/3/5m use latest observation at or before requested lag,
  no more than 7.5s older than requested time;
- no imputation.

A contract is **prediction-complete for the review denominator** only when it is
coverage-eligible and has >=6 valid frozen-grid predictions before rollover.
Contracts with fewer than 6 predictions remain diagnostic/excluded from the
review denominator rather than being backfilled.

## Frozen settlement/scoring
After rollover, fetch official finalized Kalshi result read-only. `yes=UP`,
`no=DOWN`. No proxy label is allowed.

For each immutable prediction:
- `flip=1` iff snapshot current BRTI side != official final side;
- raw probability = base logistic probability;
- V2 probability = isotonic-calibrated probability;
- `stay_prob = 1 - flip_prob`.

## Frozen review sample
Do not make a V2 decision until all are true:
- **>=30 prediction-complete fresh contracts**;
- **>=240 officially settled V2 prediction snapshots**;
- at least 8 distinct settled contracts represented in the `stay >=90%` cohort
  if that cohort is populated enough for its gate;
- observer/watchdog healthy with no unresolved data-integrity error.

No maximum-time shortcut. Sample may continue beyond 30 contracts until the
240-snapshot floor is met.

## Frozen future acceptance gate
All are required for `READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW`:

### Integrity
- official Kalshi settlement only;
- no startup/late contract contamination;
- no future BRTI use;
- no prediction overwrite;
- frozen historical 70/24 training/calibration split unchanged;
- frozen 12-feature set unchanged;
- no signal path or production behavior changed.

### Brier / calibration
- V2 aggregate Brier <= raw base-model Brier;
- V2 Brier skill vs a frozen historical base-training flip-prior null >=5%;
- weighted absolute calibration error across fixed reliability bins with n>=20
  <=5pp;
- no fixed reliability bin with n>=30 has absolute error >10pp;
- >=3 populated reliability bins with n>=20;
- Spearman correlation between average stated flip probability and actual flip
  frequency across those bins >=0.80.

Fixed reliability bins remain:
0–5, 5–10, 10–20, 20–30, 30–40, 40–50, 50–60, 60–70, 70–80,
80–90, 90–95, 95–100%.

### High-confidence stay
If `stay_prob >=90%` has >=30 settled snapshots:
- >=8 distinct contracts;
- actual stay rate >=90%.

If fewer than 30 such snapshots exist at the 30-contract review point, the gate
is **not ready**, not a PASS and not a FAIL; continue collection until the cohort
reaches 30 snapshots or the overall sample reaches 50 prediction-complete
contracts. At 50 contracts, if the high-stay cohort is still <30, numeric Flip
Risk remains unapproved because high-confidence calibration is unproven.

### Time conditioning
For every frozen remaining-minute bucket with n>=20 settled predictions:
absolute error between mean V2 stated flip risk and actual flip frequency <=15pp.

## Meaning of PASS
PASS earns **manual review only** for a user-facing numeric Flip Risk field.
It does not automatically change the dashboard, production, or any signal rule.
A separate presentation/visual acceptance step is still required.

## Meaning of FAIL
Do not tune V2 on the same future sample. Record the failure morphology and
predeclare any V3 method before a new future sample.

## Non-negotiables
- Numeric Flip Risk stays hidden until this fresh V2 gate passes and manual
  review accepts it.
- EARLY, SCALP, FINAL, LOCK, PASS, entry, protection, and exit remain unchanged.
- No auto-promotion.
- No orders.
