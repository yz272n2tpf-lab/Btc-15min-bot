# BTC15 Frozen Review Hub V2 Authority — 2026-09-16

**READ ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS**

This note freezes the validated four-lane review/reporting infrastructure used
while the fresh forward samples continue collecting. It does not change any
signal qualification, threshold, collector state, settlement behavior, or
production behavior.

## Railway authority
- Service name: `final-v4-review-tooling-v1`
- Service ID: `56b8496c-8dea-409b-a236-9e139a9c2e96`
- Validated deployment: `f87af17d-c932-456b-b58d-6d21056dea61`
- Research branch commit: `c50da5e21a0f838249a6000b7082723eda98f62b`
- Runtime: `BTC15_REVIEW_HUB_LIVE_V2.py`
- Startup gate: **71/71 tests passed** before serving.
- `/health`: HTTP 200 after live startup.
- Hub live integrity: PASS across all four review lanes.

## Four independent review lanes
1. FINAL V4
   - Collector: `final-forward-scorecard-v1`
   - Review report: `BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1.py`
   - Gate: >=30 eligible + >=12 officially settled protected FINAL locks.

2. EARLY V1
   - Collector: `early-forward-scorecard-v1`
   - Review report: `BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1.py`
   - Gate: >=30 eligible + >=12 settled protected EARLY calls.
   - Settlement-side rate remains secondary context, never FINAL accuracy.

3. EARLY -> FINAL handoff V1
   - Collector: `early-final-handoff-v1`
   - Review report: `BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1.py`
   - Gate: >=30 eligible + >=10 true same-contract handoffs + >=12 settled FINAL locks.
   - **This is the only review lane allowed to certify union/actionable coverage.**
   - Union identity is checked as `EARLY + FINAL - true handoffs` on one common universe.

4. EARLY excursion V1
   - Collector: `early-excursion-forward-v1`
   - Review report: `BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1.py`
   - Gate: >=30 eligible + >=10 completed protected EARLY excursions.
   - MFE/MAE and +5/+10/+15/+20c are tradable-move utility metrics, never FINAL accuracy and never new qualification rules.

## Network boundaries
- FINAL and EARLY are read via their existing read-only state endpoints.
- Handoff and excursion remain non-public and are read over Railway private
  networking:
  - `early-final-handoff-v1.railway.internal:8080/state`
  - `early-excursion-forward-v1.railway.internal:8080/state`
- The hub uses GET-only reads and has no collector mutation path.

## Frozen reporting rules
- No blended system accuracy.
- Standalone EARLY and FINAL coverage may never be added to claim union coverage.
- Union coverage comes only from the handoff common-universe report.
- FINAL directional accuracy and Kalshi entry economics remain separate.
- EARLY settlement-side rate is secondary only.
- Excursion/scalp move rates are not FINAL accuracy.
- Count satisfaction alone is insufficient; each authoritative collector must
  report its own frozen `sample_ready` state.
- Every review-ready state authorizes **manual review only**.
- No threshold retuning from confirmation samples.
- No automatic promotion.
- No orders.

## Numeric Flip Risk
Flip Risk V2 is intentionally **not** included in Review Hub V2. Its future
validation is calibration-based and has a separate frozen decision structure.
Numeric Flip Risk remains hidden until its own validation passes and a later
manual display review explicitly approves user-facing numeric output.

## Live startup checkpoint
At validated startup the hub reported:
- FINAL: 24/30 eligible, 14 settled, 14/14 correct, 58.33% FINAL-only coverage,
  avg timing ~4.83m, avg ask ~90.0c, 0 <=50c.
- EARLY: 22/30 eligible, 2 settled calls, 9.1% EARLY-only coverage, avg/median
  entry 43c, 2/2 <=50c, 0 ideal 25–35c, settlement same-side 1/2 secondary.
- HANDOFF: 21/30 eligible, 0/10 true handoffs, 12/12 settled FINAL minimum,
  observed common-universe any-signal coverage 13/21 = 61.9%, not certified.
- EARLY EXCURSION: 13/30 eligible, 1/10 complete, first completed case had
  avg/current MFE +55.9c and MAE -1.0c with +5/+10/+15/+20 all reached; n=1 only.

These startup values are checkpoints, not frozen outcome conclusions. Collector
samples continue forward without being restarted by this review infrastructure.
