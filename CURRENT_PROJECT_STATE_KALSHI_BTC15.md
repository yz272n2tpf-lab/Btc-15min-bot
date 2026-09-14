# BTC / Kalshi 15-Minute Bot — CURRENT PROJECT STATE

## Purpose
This file is the operational source of truth for WHERE THE PROJECT IS RIGHT NOW.

Before proposing ANY code change, test, optimizer, or next phase:
1. Read `MASTER_BUILD_SPEC_KALSHI_BTC15.md`.
2. Read this CURRENT PROJECT STATE file.
3. Confirm the proposed action directly advances the current active objective.
4. If it does not, DO NOT propose it.

---

## CURRENT PHASE

**Combined-system integration of separately earned modules.**

We are NOT rebuilding the protected FINAL model.
We are NOT weakening the protected Tier-1 EARLY entry.
We are NOT retuning the generalized SCALP challenger from forward results.
We are NOT promoting the failed PRE-WATCH/handoff EARLY extension.

Current active objective:

Wire the already-tested side-effect-free integration composer around the protected EARLY, protected FINAL, and locked generalized SCALP outputs without rewriting those modules. Preserve exact contract timing, explicit horizon conflicts, union actionability without double counting, and SIGNAL ONLY / NO ORDERS behavior.

The upcoming integrated smoke must explicitly verify the user-critical SCALP management path: an ACTIVE scalp that runs in profit must surface PROTECT / EXIT guidance early enough to avoid silently giving back a large winning move. This is a management/presentation validation requirement, not a retune of the frozen SCALP entry rule.

---

## PROTECTED / LOCKED MODULES ENTERING INTEGRATION

### FINAL — V4.6 / V4.7 tournament winner

Untouched historical holdout:

- 97.9% qualified FINAL accuracy
- 46 correct / 47 qualified calls
- 47% coverage
- average 4.64 minutes left
- median 5.0 minutes left

Rule:

- fair >= 90%
- <= 8 minutes left
- gap >= $75 when >6 minutes remain
- gap >= $50 when <=6 minutes remain
- distance / recent 5m range >= 1.0x
- preferred fair side = current target side

Status: **PROVISIONALLY LOCKED.**

Do not weaken or retune merely to increase activity.

### TIER-1 EARLY ENTRY — V3 historical-price tournament winner

Untouched historical holdout:

- 90.9% qualified entry accuracy
- 20 correct / 22 qualified entries
- 22% coverage
- average actual Kalshi ask 31.9c
- median ask 34.0c
- average 6.09 minutes left
- median 6.0 minutes left

Rule:

- ask <= 45c
- fair >= 75%
- edge >= 8 percentage points
- 2–10 minutes left
- abs exact Kalshi target gap >= $25
- no persistence requirement
- no strengthening requirement
- no forced current-side agreement

Status: **PROVISIONALLY LOCKED AS TIER-1.**

Replay reproduction on the current 199-contract cache remained clean:

- VALIDATION: 16 calls, 16.2% coverage, 100.0% accuracy, 35.7c average ask, 5.31m remaining.
- REPORT_ONLY: 22 calls, 22.0% coverage, 90.9% accuracy, 31.9c average ask, 6.09m remaining.

### GENERALIZED SCALP — frozen forward-confirmed challenger

Frozen rule:

- first candidate per contract satisfying frozen gates
- seconds_left >= 120
- side-aligned btc30 >= $15
- NO entry-price eligibility filter
- executable ASK -> future BID economics
- management arms after +5c executable gain
- protect/exit after 4c giveback from running executable peak
- one primary qualified scalp signal per contract
- SIGNAL ONLY / NO ORDERS

Forward freeze: `2026-09-14T02:24:03.366238Z`.

Official untouched forward scorekeeper:

- observed contracts: 43
- completed qualified contracts: 40
- pre-frozen minimum decision gate: 20
- actionable coverage: 93.0%
- +5c: 87.5%
- +10c: 62.5%
- +15c: 47.5%
- +20c: 32.5%
- +30c: 15.0%
- average peak executable move: +16.60c
- median peak executable move: +14.00c
- median adverse excursion: -1.00c
- managed average: +11.23c
- managed median: +7.50c
- positive managed exit: 77.5%
- median time to +5c: 33.0s
- median time to +10c: 44.5s
- median time to +20c: 101.0s

Side balance:

- DOWN n=21: +10 61.9%, +20 28.6%, managed average +10.00c
- UP n=19: +10 63.2%, +20 36.8%, managed average +12.58c

Final descriptive stability audit remained positive in both UP and DOWN and across all populated timing/momentum slices. The later stability sample had 41 qualified signals, managed average +10.76c, positive managed exit 75.6%, and median adverse excursion -1.00c.

Known limitation: the stability audit had no qualified observations in the 16–24Z UTC slice. Monitor that session during later integrated smoke/confirmation, but do NOT create a post-hoc filter from this limitation.

Status: **KEEP / LOCKED FOR INTEGRATION WITHOUT RETUNING.**

Decision freeze: `BTC15_GENERALIZED_SCALP_FORWARD_DECISION_20260914.md`.

---

## EARLY COVERAGE-EXTENSION RESEARCH — CLOSED FOR CURRENT DESIGN

The validation-selected PRE-WATCH champion was:

- ask <=45c
- fair >=75%
- edge >=2pp
- gap >=$20
- 3–11 minutes remaining

VALIDATION:

- 18 calls
- 18.2% coverage
- 94.4% accuracy
- average ask 37.9c
- average time 6.50m
- 8 before-expensive-near-miss rescues at 100.0% accuracy
- average lead before repricing 120s

REPORT_ONLY — never used to select thresholds:

- 25 calls
- 25.0% coverage
- **72.0% accuracy**
- average ask 32.5c
- average time 6.68m
- 9 before-expensive-near-miss rescues at 77.8% accuracy

The report-only degradation fails the intended robustness standard.

The frozen PRE-WATCH -> actionable handoff tournament then found **no handoff candidate that passed the validation quality gate of >=12 actions and >=90% accuracy.**

Decision:

- PRE-WATCH remains non-actionable.
- Current handoff extension does NOT earn forward testing.
- Do not retune using REPORT_ONLY.
- Do not loosen protected Tier-1 merely for coverage.
- Keep protected Tier-1 unchanged.

Decision freeze: `BTC15_EARLY_LADDER_DECISION_20260914.md`.

A future stricter/higher-confidence EARLY research layer may be tested separately after current integration/management validation, but it must not alter the protected Tier-1 anchor and must use a new pre-frozen validation design rather than recycling the failed PRE-WATCH thresholds.

---

## COMBINED INTEGRATION CONTRACT — FROZEN

Integration semantics are frozen in `BTC15_SYSTEM_INTEGRATION_FREEZE_V1.md` before combined behavior is judged.

Core rules:

- EARLY, FINAL, and SCALP remain independent authorities with different horizons.
- A SCALP opposite FINAL is allowed and must be labeled rather than suppressed.
- An earlier EARLY call is never silently rewritten by a later FINAL state.
- FINAL `LOCK` comes only from protected FINAL evidence, never scalp momentum.
- SCALP `PROTECT` / `EXIT` come only from validated scalp management.
- WATCH does not count as actionable coverage.
- Union actionable coverage counts each contract once if any separately validated path qualifies.
- No numeric flip/reversal-risk percentage until separately calibrated.
- Manual execution only. No orders.

Pure side-effect-free integration composer:

- `btc15_signal_integration_v1.py`
- `test_btc15_signal_integration_v1.py`

Offline integration validation now has two completed layers:

1. **Unit invariants: 9/9 PASS.**
2. **Deterministic combined fixture scorecard: PASS.**
   - 15 fixtures
   - 45 module-preservation comparisons
   - 14/15 fixture scenarios actionable by construction
   - union counted once per contract
   - conflict labels and display precedence preserved
   - no scalp price gate invented
   - no order field
   - no unvalidated numeric flip-risk output

Important: `14/15` is a synthetic fixture-composition count, **not empirical live union coverage.** Real union coverage is not claimed until protected module outputs are wired on a common contract timeline.

Fixture result freeze/report: `BTC15_COMBINED_SYSTEM_FIXTURE_RESULT_V1.md`.

The fixture run used Railway only as an execution host. Both test processes exited 0, then the same deployment returned to the read-only scalp collector and emitted a healthy live heartbeat with `NO ORDERS`.

Status: **PURE COMPOSER / OFFLINE INTEGRATION SEMANTICS PASSED.**

---

## NON-NEGOTIABLE FINISHED-PRODUCT GOAL

The finished bot is NOT a cherry-pick-only system.

It must evaluate every 15-minute contract and try to find the best positive-expectation opportunity available in that contract.

Current validated opportunity paths entering integration:

- protected Tier-1 EARLY directional entry
- generalized SCALP / reversal move
- protected high-confidence FINAL
- validated SCALP protect/exit management

Possible future paths may include secondary entry or pullback/re-entry, but they must earn evidence independently. Failed extensions are not forced into the system.

Primary coverage metric:

**UNION ACTIONABLE COVERAGE = percentage of contracts with at least one separately validated actionable opportunity.**

---

## DEVELOPMENT SPEED RULE — HARD REQUIREMENT

Default:

- offline batch/replay first
- cheap preflight before expensive work
- automate scoring
- chronological validation
- untouched holdout / fresh forward confirmation
- 20–30 minute live smoke test only when live verification is necessary

DO NOT:

- start 60–90 minute tests by default
- start multi-hour / overnight tests during active development
- retune a frozen module from forward results
- tune against REPORT_ONLY / untouched holdout
- ask the user to wait through a live run for a question that can be answered offline

4–8 hour / overnight run:
ONLY for final confirmation after the integrated system is stable, or when explicitly justified and agreed.

---

## NEXT MILESTONES

1. **DONE:** pure integration/state-composition layer + offline invariants.
2. **DONE:** deterministic combined-system fixture/scorecard proving module preservation and union-count correctness.
3. **ACTIVE:** wire the composer around existing protected module outputs without rewriting those modules.
4. Run a 20–30 minute integrated live smoke test for feed/timer/state-transition correctness, explicitly including:
   - FINAL transition before clock zero
   - exact 15-minute contract alignment
   - SCALP ACTIVE -> PROTECT -> EXIT presentation/timing
   - conflict labels
5. Validate dashboard-facing contract payload: FINAL, EARLY, SCALP, price/timing, conflict label, protect/exit, and reasons for PASS.
6. Build/validate any still-missing exit-warning timing/presentation without inventing unvalidated EARLY/FINAL exit rules or retuning frozen SCALP qualification.
7. Produce combined full-system scorecard:
   - FINAL accuracy + coverage
   - Tier-1 EARLY accuracy + coverage + ask + timing
   - SCALP coverage + executable move + managed outcome
   - UNION actionable coverage on a common contract universe
   - state/conflict behavior
   - exit/protection behavior
8. Optionally test a separately frozen higher-confidence EARLY research layer while preserving Tier-1 unchanged.
9. One longer confirmation run ONLY after the integrated system is stable.
10. Dashboard/app integration only after trading logic and state semantics are locked.

---

## ANTI-DRIFT CHECK BEFORE EVERY NEXT STEP

Before proposing the next action, answer internally:

1. Does it preserve protected FINAL?
2. Does it preserve protected Tier-1 EARLY?
3. Does it preserve frozen SCALP without post-hoc retuning?
4. Does it improve integration, coverage, economics, timing, or another explicit unfinished requirement?
5. Can it be done offline first?
6. Is it the fastest technically sound path?
7. Is REPORT_ONLY / forward data being used only for evaluation, never retroactive tuning?
8. Does the result advance the finished-product goal rather than one isolated metric?

If any answer indicates drift, STOP and redesign the next step.

---

## USER EXPECTATION

Do the maximum useful work possible every iteration.
Do not make the user repeatedly restate the build goal or current phase.
Do not call one selective module "the finished bot."
Do not trade quality for speed.
Do not trade speed for unnecessary testing.
Keep the system SIGNAL ONLY and manual-execution-only at every phase.
