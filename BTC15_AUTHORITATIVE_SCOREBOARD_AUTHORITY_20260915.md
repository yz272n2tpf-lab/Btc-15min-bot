# BTC15 Authoritative Scoreboard Authority — 2026-09-15

**Read only · signal only · manual execution · no orders**

## Authority

- Railway service: `authoritative-scoreboard-v1`
- Service ID: `6c0ec9d5-2187-4623-97ec-44c3304b8074`
- Authoritative deployment: `1bb0e9b5-a299-4516-bad4-79b57686b9ff`
- Runtime: `BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V3.py`
- Score combiner: `BTC15_AUTHORITATIVE_SCOREBOARD_V2.py`
- App view model: `BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1.py`
- Research branch: `scalp-move-shadow-v1-20260912`

## Validation

Startup gate passed **34/34 tests** before runtime:
- 10 Scoreboard V1 separation/safety tests;
- 10 private live-wrapper/network safety tests;
- 8 exact collector field-alias tests;
- 6 app view-model presentation safety tests.

Startup probe connected **5/5 authoritative collectors** over Railway private
networking. No collector was newly exposed publicly.

Validated private sources:
- FINAL V4;
- EARLY V1;
- EARLY→FINAL handoff V1;
- EARLY excursion V1;
- direct-BRTI Flip Risk V2.

## Endpoints

Private service endpoints:
- `/health`
- `/scoreboard` (alias `/state`)
- `/scoreboard.txt`
- `/viewmodel`

The service rejects write methods and owns no trading/model state.

## Frozen reporting semantics

- FINAL directional accuracy remains FINAL-only.
- EARLY settlement same-side rate remains secondary context.
- SCALP +10c remains a price-movement metric, not FINAL accuracy.
- Union coverage is not certified until the common-universe handoff collector
  reaches its frozen sample gate.
- One blended system-accuracy percentage is forbidden.
- Numeric Flip Risk remains hidden until its future validation passes and a
  separate manual user-facing display review approves it.
- Missing/wrong-version/unsafe collector data fails closed as `NOT CONNECTED`;
  stale snapshots are not reused across requests.

## First validated V3 startup snapshot

At the V3 startup probe:
- FINAL: 15 eligible, 9 settled locks, 9/9 correct, 60.0% FINAL-only coverage,
  avg lock time 4.79m, avg locked-side ask 91.1c, 0 <=50c entries.
- EARLY: 13 eligible, 1 settled EARLY call, 7.7% EARLY-only coverage, avg entry
  43.0c, avg time 5.99m.
- EARLY excursion: 4 eligible, 0 protected EARLY entries yet.
- Handoff: 12 eligible, 7 FINAL locks, 0 EARLY handoffs, any-anchor coverage 58.3%,
  sample not ready.
- Flip V2: 2 prediction-complete contracts / 12 settled predictions; numeric risk
  remains `NOT CALIBRATED` / hidden.
- SCALP reference remains 77.4% +10c on 115 completed serial opportunities; the
  separate fresh reference remains 82.0% +10c on 61 opportunities.
- Overall union coverage: `NOT CERTIFIED`.

These values are a startup snapshot only, not a frozen result. Collector sample
gates remain authoritative for decisions.

## Scope

This scoreboard is reporting/presentation infrastructure only. It does not
replace V12, does not promote V13, does not modify production, and does not alter
EARLY, FINAL, SCALP, Flip Risk, timer, qualification, lifecycle, or order behavior.
