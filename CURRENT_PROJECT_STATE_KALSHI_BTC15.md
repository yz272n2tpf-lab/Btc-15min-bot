# BTC / Kalshi 15-Minute Bot — CURRENT PROJECT STATE

## Purpose
This file is the operational source of truth for WHERE THE PROJECT IS RIGHT NOW.

Before proposing ANY code change, test, optimizer, or next phase:
1. Read MASTER_BUILD_SPEC_KALSHI_BTC15.md.
2. Read this CURRENT PROJECT STATE file.
3. Confirm the proposed action directly advances the current active objective.
4. If it does not, DO NOT propose it.

---

## CURRENT PHASE
Coverage expansion around locked high-quality anchors.

We are NOT rebuilding the core FINAL model.
We are NOT replacing the validated Tier-1 early-entry rule.
We are NOT doing long live tests by default.

Current active objective:
Increase UNION ACTIONABLE COVERAGE toward "almost every contract" using additional independently validated opportunity paths, while protecting accuracy, entry price, and timing.

---

## LOCKED / PROVISIONALLY LOCKED ANCHORS

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

Status:
PROVISIONALLY LOCKED.
Do not weaken or retune merely to increase activity.
Additional opportunity paths must fill coverage gaps around it.

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

Status:
PROVISIONALLY LOCKED AS TIER-1.
It is NOT the finished entry system.
It may later be improved toward 93–95%+ if accuracy can rise without destroying useful price/timing/coverage.

---

## NON-NEGOTIABLE COVERAGE GOAL
The finished bot is NOT a cherry-pick-only system.

It must evaluate every 15-minute contract and try to find the best positive-expectation opportunity available in that contract.

Possible opportunity paths:
- Tier-1 early directional entry
- secondary directional entry
- pullback / re-entry
- momentum scalp
- reversal scalp
- later high-confidence FINAL
- exit / profit-protection opportunity

True PASS is the exception for genuinely untradeable / nail-biter situations.

A FINAL PASS does NOT mean there was no intraperiod scalp/reversal opportunity.

Primary coverage metric:
UNION ACTIONABLE COVERAGE = percentage of contracts with at least one validated actionable opportunity.

---

## CURRENT RESEARCH QUESTION
For contracts NOT covered by the locked Tier-1 entry:
Can secondary entry + realistic scalp/reversal paths materially increase union actionable coverage while maintaining acceptable accuracy and economic value?

Scalp evaluation must use:
- actual Kalshi ASK to enter
- actual future Kalshi BID to exit
- spread included
- profit target / stop loss chronology respected

---

## DEVELOPMENT SPEED RULE — HARD REQUIREMENT
We are streamlining aggressively WITHOUT lowering standards.

Default:
- offline batch/replay first
- cheap preflight before expensive work
- automate scoring
- chronological validation
- untouched holdout
- 20–30 minute live smoke test only when live verification is necessary

DO NOT:
- start 60–90 minute tests by default
- start multi-hour / overnight tests during active development
- brute-force a slow computation when an equivalent cached/vectorized approach can answer it faster
- ask the user to wait through a long run merely because the code was written inefficiently

60–90 minute behavior test:
ONLY when a 20–30 minute smoke test cannot answer the specific live question.

4–8 hour / overnight run:
ONLY for final confirmation after the integrated system is stable, or when explicitly justified and agreed.

If a proposed offline computation may take >10–15 minutes:
OPTIMIZE / CACHE / VECTORIZE IT FIRST whenever reasonably possible.

---

## ANTI-DRIFT CHECK BEFORE EVERY NEXT STEP
Before proposing the next action, answer internally:

1. What phase are we in?
2. What exact question are we answering?
3. Does this preserve locked FINAL?
4. Does this preserve locked Tier-1 ENTRY?
5. Does this improve union actionable coverage OR another explicit unfinished requirement?
6. Is this the fastest technically sound way to answer it?
7. Can it be done offline instead of live?
8. Can multiple candidate ideas be tested together safely?
9. Is the user being asked to wait longer than necessary?
10. Does the result advance the finished-product goal rather than just one isolated metric?

If any answer indicates drift, STOP and redesign the next step.

---

## NEXT MILESTONES
1. Finish coverage-expansion optimizer efficiently.
2. Evaluate validation + untouched-holdout UNION actionable coverage.
3. Keep only additional paths that earn their place.
4. Integrate validated coverage paths around v4.7 anchors.
5. 20–30 minute combined smoke test.
6. Build / validate exit guidance.
7. Combined full-system scorecard:
   - FINAL accuracy + coverage
   - Tier-1 entry accuracy + coverage + ask + timing
   - secondary entry metrics
   - scalp/reversal metrics
   - UNION actionable coverage
   - exit behavior
8. One longer confirmation run ONLY after the system is stable.
9. Dashboard/app integration only after logic is locked.

---

## USER EXPECTATION
Do the maximum useful work possible every iteration.
Do not make the user repeatedly remind the assistant of the build goal, current phase, or streamlined workflow.
Do not call a selective high-accuracy tier "the finished bot."
Do not trade quality for speed.
Do not trade speed for unnecessary testing.
