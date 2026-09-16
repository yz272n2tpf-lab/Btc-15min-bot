# BTC15 Flip Risk V2 Review Authority — 2026-09-16

**READ ONLY · SHADOW ONLY · MANUAL EXECUTION · NO ORDERS**

This note freezes the separate calibration-review logic for future-only Direct-BRTI
Flip Risk V2. It does not add numeric Flip Risk to the app, change the model,
retune the same sample, or authorize promotion.

## Active collector
- Railway service ID: `f020787f-00fb-4a46-a36c-710f18bbf31e`
- Deployment: `60b67800-6709-45fa-a558-de51fa2d9ec0`
- Runtime: `BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2.py`
- Fresh start: startup contract excluded; first post-start rollover onward.

## Review implementation
- `BTC15_FLIP_RISK_V2_FROZEN_REVIEW_REPORT_V1.py`
- `test_BTC15_FLIP_RISK_V2_FROZEN_REVIEW_REPORT_V1.py`
- Corrected test-fixture commit: `5bcfc7e61cf3d6693a0c42d704916ee7de7f4788`
- Validated as part of review-tool service deployment
  `bf74b182-7507-4ed8-9a25-9e7041d37e1f`.
- Full startup gate: **85/85 tests passed**.

## Frozen decision tree
Base sample readiness requires:
- >=30 settled prediction-complete fresh contracts; and
- >=240 settled review predictions.

Base readiness alone is **not** a PASS.

High-stay readiness requires >=30 settled `stay>=90%` snapshots. The decision
then still requires at least 8 distinct settled contracts in that cohort and
actual stay rate >=90% to pass the high-stay gate. If the high-stay cohort is
still sparse at 50 settled prediction-complete contracts, the frozen design
forces a FAIL rather than waiting forever or relaxing the gate.

When a decision is ready, PASS additionally requires all of:
- calibrated Brier <= raw/base Brier;
- Brier skill >=5% versus the historical-prior null model;
- >=3 reliability bins with n>=20;
- weighted absolute calibration error <=5 percentage points;
- max error among bins with n>=30 <=10 percentage points;
- reliability monotonicity Spearman >=0.80;
- high-stay cohort requirements above;
- every populated time bucket with n>=20 has absolute calibration error <=15pp.

## Fail-closed integrity checks
The review packet verifies:
- collector version and frozen historical training/calibration snapshot counts;
- sample-ready / high-stay-ready / forced-fail / decision-ready arithmetic;
- Brier-skill arithmetic;
- reliability-bin stated/actual/error arithmetic and aggregate ECE;
- time-bucket error arithmetic;
- gate booleans and status agreement;
- production unchanged, manual execution only, no orders;
- numeric Flip Risk remains user-facing disabled.

## Interpretation
- `READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW` authorizes manual review only.
- It does **not** make numeric Flip Risk user-facing automatically.
- `FUTURE_V2_REVIEW_SAMPLE_FAILED` closes this frozen V2 lane for the sample;
  no same-sample retuning.
- Numeric Flip Risk remains hidden until a later explicit manual display review.
- Flip V2 stays separate from the simpler FINAL/EARLY/HANDOFF/EXCURSION review hub.
- No automatic promotion. No orders.
