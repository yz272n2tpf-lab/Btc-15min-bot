# BTC15 FINAL V4 Review Tooling Authority — 2026-09-16

**READ ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS**

This note freezes the validated review tooling for the authoritative FINAL V4
forward confirmation sample. It does not change FINAL qualification, collection,
settlement, production behavior, or promotion policy.

## Authoritative FINAL collector
- Railway service: `final-forward-scorecard-v1`
- Service ID: `fbe79688-25ed-4329-b0d6-c9b669559b17`
- Deployment: `48b86488-3688-40d3-82b4-ad5fe028a61f`
- Collector version: `BTC15_FINAL_FORWARD_SCORECARD_V4`
- Coverage denominator: `FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW`
- Eligibility window opens at 480 seconds remaining.
- Frozen gate: at least 30 eligibility-complete contracts and at least 12
  officially settled protected FINAL locks.

## Review report implementation
- `BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1.py`
- Report commit: `960908cc91813ecf13408c55c1e28f94e9d0d717`
- `test_BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1.py`
- Test commit: `39f19d7419d3fcd13f2dcd2786c8eb97a0e9b993`

The report fails closed on collector-version drift, denominator drift, eligibility
window drift, threshold/production changes, order behavior, numeric Flip Risk,
and inconsistent count/rate arithmetic. Count satisfaction alone does not open
review: the authoritative collector must also report `sample_ready=true`.

## Live review wrapper
- `BTC15_FINAL_V4_REVIEW_LIVE_V1.py`
- Wrapper commit: `8cbc054b663e141ddee3081a0a83c893f906c3f1`
- `test_BTC15_FINAL_V4_REVIEW_LIVE_V1.py`
- Wrapper-test commit: `384d557c08d1d0a745d86a3883e55f7bd98692fe`

Railway QA/review service:
- Name: `final-v4-review-tooling-v1`
- Service ID: `56b8496c-8dea-409b-a236-9e139a9c2e96`
- Validated deployment: `87083958-7e3f-4d61-9719-7690fe39f5e1`
- Research branch commit: `384d557c08d1d0a745d86a3883e55f7bd98692fe`
- Test gate: 20/20 tests passed before startup.
- Startup live fetch: integrity PASS, `/health` 200, current status
  `WAITING_FOR_FROZEN_GATE` at 24 eligible / 14 settled.

The live wrapper is GET-only and reads the authoritative FINAL V4 `/state`.
It exposes review information only and cannot alter collector state.

## Frozen interpretation
- FINAL accuracy is directional accuracy only on officially settled protected
  FINAL locks.
- FINAL-only coverage is not union/actionable coverage.
- Kalshi locked-side ask/timing are reported separately from directional accuracy.
- The 93% project floor and 95% stretch marker are descriptive checks only.
- `FINAL_V4_MANUAL_REVIEW_READY` authorizes manual review only.
- No threshold retuning from this confirmation sample.
- No automatic promotion.
- No numeric Flip Risk inference.
- No orders.
