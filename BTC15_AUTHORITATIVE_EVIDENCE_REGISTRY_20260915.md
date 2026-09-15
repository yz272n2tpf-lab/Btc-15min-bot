# BTC15 Authoritative Evidence Registry — 2026-09-15

**Signal only · manual execution · no orders**

Purpose: prevent older diagnostics, rejected hypotheses, historical reference
samples, and current fresh-forward confirmation samples from being mixed into a
single misleading score.

## Production / stable behavior

### Production main
- Status: **STABLE / UNCHANGED**
- Railway service: `Btc-15min-bot`
- Production logic is not automatically modified by any research below.

### V5 serial SCALP lifecycle
- Status: **FROZEN SHADOW ARCHITECTURE**
- Unlimited serial opportunities.
- +5c protection arm.
- 4c giveback protected EXIT.
- ENDED_UNARMED = lifecycle reset metadata only, never an exit/sell.
- Armed/no-exit path remains protected/blocking.
- Entry price remains telemetry/guidance, not a hidden qualification filter.

### V12 dashboard
- Status: **CURRENT ACCEPTED SHADOW DISPLAY BASELINE**
- Expensive qualified scalp = tracking/no-position wording.
- Do not replace without visual acceptance.

### V13 dashboard
- Status: **PRESENTATION CANDIDATE ONLY**
- 19 tests + presentation audit PASS.
- Plain-language SCALP wording.
- Not promoted over V12 without user visual acceptance.

## FINAL outcome evidence

### Historical protected FINAL OOS
- Status: **HISTORICAL REFERENCE ONLY**
- 133 calls / 250 contracts.
- 132/133 = 99.25% directional accuracy.
- 53.2% FINAL-only coverage.
- Average ~5.04 minutes left.
- Average locked-side ask ~92.99c; median ~94.4c.
- 0/133 <=50c.
- Interpretation: strong historical correctness anchor, not evidence of cheap
  entry quality.

### FINAL V2 / V3 live samples
- Status: **DIAGNOSTIC ONLY**
- Do not use for final confirmation decisions.
- V2 could remain HTTP-green while the observer stopped advancing.
- V3 fixed the silent-worker issue but its earlier coverage-universe claim was
  superseded by V4.

### FINAL V4 fresh confirmation
- Status: **AUTHORITATIVE / COLLECTING**
- Coverage universe: `FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW`.
- Contract counts only when first seen with >=480 seconds remaining.
- Watchdog supervised.
- Fresh cutoff: 2026-09-15T20:00:00Z.
- Review gate: >=30 eligibility-complete contracts and >=12 officially settled
  protected FINAL locks.
- Latest checked checkpoint: 6 eligibility-complete contracts, 5 locks, 4
  settled locks, 4/4 correct; fresh FINAL-only coverage 0.800; avg lock timing
  ~4.62m; 0/4 settled locks at <=50c; watchdog restarts=0.
- Report separately: directional accuracy, FINAL-only coverage, timing,
  locked-side Kalshi ask, <=50c economics, excluded-late count.
- No auto-promotion.

## EARLY opportunity evidence

### EARLY V1 fresh confirmation
- Status: **AUTHORITATIVE / COLLECTING AFTER FIRST POST-START ROLLOVER**
- Railway service: `early-forward-scorecard-v1`.
- Coverage universe: `FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW`.
- Contract counts only when first seen with >=600 seconds remaining.
- Startup contract excluded.
- Protected producer remains authority; scorecard does not qualify EARLY.
- Frozen producer source facts: ask <=45c, fair >=75%, edge >=8pt, 2–10m left,
  >=$25 absolute target distance.
- Review gate: >=30 eligibility-complete contracts and >=12 officially settled
  protected EARLY calls.
- Settlement same-side rate is secondary context, not FINAL accuracy.
- Report coverage, first-entry ask, 25–35c rate, <=50c rate, timing, fair, edge,
  and settlement same-side rate separately.
- No auto-promotion.

## Protected two-signal workflow evidence

### EARLY → FINAL handoff V1 fresh confirmation
- Status: **AUTHORITATIVE READ-ONLY WORKFLOW AUDIT / COLLECTING**
- Railway service: `early-final-handoff-v1`.
- Service ID: `174bd89d-264b-4882-8d5a-b8dbacf97181`.
- Authoritative deployment: `43e32eee-afea-4986-a944-803a53945852`.
- Research branch: `scalp-move-shadow-v1-20260912`.
- Code: `BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`, commit
  `8c6ebedb14eea11072c0acc1404aa0b68fabb7be`.
- Tests: `test_BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`, commit
  `cb05a536a1164132d4a4b872bb90b7bcd1a804d3`; 10 tests PASS.
- Predeclared freeze: `BTC15_EARLY_FINAL_HANDOFF_FORWARD_FREEZE_20260915.md`,
  commit `8c5212cb3587be9d61a9bcbcbc486a07e491e887`.
- Startup contract excluded; live collection arms on first post-start rollover.
- Coverage universe: first seen with >=600 seconds remaining, before protected
  EARLY can qualify; this is also complete for the later FINAL window.
- Review gate: >=30 eligibility-complete contracts, >=10 real protected
  EARLY→FINAL handoffs, and >=12 officially settled protected FINAL locks.
- First protected EARLY and first protected FINAL are immutable once recorded;
  later side changes are measured as flips, never rewritten.
- Latest checked checkpoint: 3 eligibility-complete contracts, 0 protected EARLY
  calls, 3 FINAL locks, 0 real handoffs, 2 settled FINAL locks, 2/2 correct.
  This is a tiny sample and is not a conclusion; no missing EARLY is backfilled.
- Report EARLY/FINAL/union/dual coverage, handoff time, side agreement/flip,
  EARLY price quality, FINAL locked-side price, same-side price change, and
  official FINAL accuracy separately.
- Test-fixture log lines before `Ran 10 tests ... OK` are non-live. Authoritative
  live evidence begins only after the runtime `START` line.
- No threshold changes, no auto-promotion, no orders.

## Numeric Flip Risk evidence

### Coinbase-based historical calibrated model
- Status: **HISTORICAL CALIBRATION PASS / LIVE PARITY FAIL**
- Historical chronological calibration was strong, but live feature parity was
  only 7/20 because production authority is direct BRTI rather than Coinbase
  1m OHLCV.
- Decision: never substitute live BRTI values into the old Coinbase model.
- Numeric Flip Risk remained hidden.

### Direct-BRTI V1 historical model
- Status: **REJECTED / CLOSED ON ITS OOS COHORT**
- Decision note: `BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_DECISION_20260915.md`, commit
  `3fd013a6222f4e0afd7204046876358934ee65ce`.
- 44 OOS contracts / 387 snapshots.
- raw Brier 0.171614; calibrated Brier 0.171113; null Brier 0.189041;
  Brier skill +9.48%; 2/3 blocks improved/tied; reliability Spearman 0.90.
- Decisive failures: weighted calibration error 8.88pp (>5pp), worst populated
  bin error 15.83pp (>10pp), and stated `stay >=90%` cohort actual stay 89.39%
  (<90%).
- Interpretation: predictive ranking exists, but the V1 probability mapping is
  not trustworthy enough to display as numeric risk.
- Do not tune V1 on the same 44-contract OOS cohort.

### Direct-BRTI future V2 isotonic shadow
- Status: **AUTHORITATIVE FUTURE-ONLY CALIBRATION SHADOW / COLLECTING**
- V2 freeze: `BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2_FREEZE_20260915.md`, commit
  `53e5104baa0ab31db796e24d2198d469bd4cfe39`.
- V2 collector: `BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2.py`, commit
  `a40405e960629be02b0382baf8b589185c10ea78`.
- V2 tests: `test_BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2.py`, commit
  `346b30bf17f9d50ed3a90d578701d6652781804b`.
- Test-first launch ran 12/12 V1+V2 tests PASS before training/collection.
- Reuses legacy retired Railway service `scalp-coverage-audit-v1` only to avoid
  creating another paid service; service ID `f020787f-00fb-4a46-a36c-710f18bbf31e`.
- Authoritative V2 deployment: `60b67800-6709-45fa-a558-de51fa2d9ec0`.
- Runtime START: `2026-09-15T21:26:33Z`; startup contract is excluded and only
  first post-start rollover onward can score.
- Historical frozen training: base model 70 contracts / 593 snapshots; isotonic
  calibration 24 contracts / 214 snapshots; historical training flip prior
  17.88%.
- Live coverage contract must first be seen with >=840s left; review contract
  needs >=6 immutable grid predictions.
- Frozen review requires >=30 prediction-complete fresh contracts and >=240
  officially settled predictions, plus reliability/Brier/high-stay/time-bucket
  gates exactly as predeclared.
- V2 changes only probability calibration; same 12 direct-BRTI features and same
  logistic base model. No signal path consumes V2.
- Numeric Flip Risk remains **hidden and user-facing disallowed** until fresh V2
  passes and manual review separately accepts presentation.
- No auto-promotion; no orders.

## SCALP research decisions

### 15s BRTI/BTC parity >=1.00
- Status: **REJECTED / CLOSED**
- Fresh baseline +10: 82.0%.
- Parity +10: 78.4%.
- Precision delta: -3.6pp.
- Winner retention: 52.0%.
- Do not tune the same cohort.

### BTC30 >=20 tightening
- Status: **REJECTED / CLOSED**

### Normalized momentum floors
- Status: **REJECTED / CLOSED**

### Failed-prearm stop / release
- Status: **REJECTED / CLOSED**
- No prearm stop added.

### Missing-BTC30 recovery
- Status: **REJECTED / CLOSED**
- Recovered candidates themselves were strong, but serial baseline/winner
  retention failed materially (~63% range at final review).
- V5 qualification remains unchanged.

## Kalshi rollover discovery research

### Probe V1
- Status: **DIAGNOSTIC ONLY**
- Placeholder 0/100 books were initially misclassified as usable.

### Probe V2
- Status: **REJECTED / CLOSED UNDER ITS PREDECLARED <=5s GATE**
- Do not relax/relabel the same sample as validation.

### Probe V3
- Status: **AUTHORITATIVE FUTURE-ONLY REPLICATION / COLLECTING**
- Cutoff: 2026-09-15T20:00:00Z.
- Requires >=8 new rollovers, >=6 valid direct-vs-broad comparisons,
  100% identity and clock integrity, direct strict usable book by +15s on >=7/8,
  direct before broad on every valid comparison, median lead >=15s.
- Latest checked checkpoint: 6/8 rollovers; 6/6 strict exact usable by +15s;
  identity/clock clean; direct before broad 6/6; median lead 10.29s. The frozen
  15s median-lead target remains unmet, so there is no PASS yet.
- PASS authorizes only an isolated exact-ticker shadow validation.
- Never authorizes production modification automatically.

## Combined / UNION evidence

Older combined V1/V2 samples that required near-second-zero discovery are
**diagnostic only** for final UNION claims because production-style discovery can
lag rollover. Do not quote them as authoritative overall coverage.

Authoritative UNION scoring should resume only after the currently measured
rollover/discovery behavior is resolved or an honest common-universe denominator
is frozen that cannot miss an eligible EARLY/SCALP event.

## Global rule

A result can move from `COLLECTING` to a decision only under its frozen sample
and integrity gate. A strong number from a diagnostic or rejected cohort cannot
be substituted for a missing authoritative sample. No research result modifies
production automatically.
