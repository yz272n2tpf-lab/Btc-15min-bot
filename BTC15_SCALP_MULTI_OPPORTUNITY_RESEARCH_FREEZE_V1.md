# BTC15 SCALP MULTI-OPPORTUNITY + FAILED-PRIMARY RESEARCH FREEZE V1

Status: **RESEARCH ONLY / SIGNAL ONLY / NO ORDERS**

Purpose: investigate two gaps discovered during live shadow validation without changing the protected generalized scalp challenger:

1. later qualified scalp opportunities in the same 15-minute contract are currently hidden after the first primary scalp is selected;
2. a primary scalp that never reaches the protected +5c arm can remain ACTIVE while losing because no validated pre-arm failure exit exists yet.

## Protected logic that remains unchanged

The existing primary scalp stays frozen:

- first qualified candidate per contract;
- seconds_left >= 120;
- side-aligned btc30 >= $15;
- **no entry-price filter**;
- profit protection arms at +5c executable gain;
- protected EXIT occurs at 4c giveback from running executable peak after arming;
- SIGNAL ONLY / NO ORDERS.

Nothing in this research may rewrite the primary entry rule, +5c arm, 4c giveback, protected EARLY, or protected FINAL.

## A. Secondary / tertiary scalp ladder

A later scalp can only be studied as a separate opportunity after the prior displayed scalp has reached its protected terminal EXIT.

Research sequence inside one contract:

1. PRIMARY = exact protected first qualified candidate.
2. SECONDARY = first later candidate that satisfies the exact same frozen qualification gate **after PRIMARY protected EXIT time**.
3. TERTIARY = first later frozen-qualified candidate **after SECONDARY protected EXIT time**.
4. Continue descriptively if more exist, but V1 promotion analysis focuses on PRIMARY / SECONDARY / TERTIARY.

No candidate may overlap an already-active displayed scalp in V1. No entry-price filter may be introduced. Later raw candidates that fail the frozen gate remain telemetry only.

For each opportunity report:

- side, ask, seconds left, btc30;
- +5/+10/+15/+20c hit rates;
- peak executable gain;
- adverse excursion;
- time to +5/+10/+15/+20;
- whether +5 arm occurred;
- protected 4c-giveback EXIT gain and elapsed time;
- contract/opportunity index.

Promotion requirement for a secondary/tertiary layer is not met by historical replay alone. An exact candidate rule must be frozen first, then collect at least **20 new unique forward qualified later opportunities** before app promotion.

## B. Pre-arm failed-primary audit

A separate audit studies protected PRIMARY signals that never reach +5c. V1 does **not** add a stop rule.

Pre-frozen descriptive grid:

- adverse levels: -3c, -5c, -7c, -10c;
- minimum elapsed times: 10s, 20s, 30s, 45s, 60s;
- for every grid cell measure how often the trigger occurs, realized gain at trigger, later best recovery, and whether the trade later would have reached +5c if not cut.

This grid is evaluated on a chronological validation half first. The second half is REPORT_ONLY and may not be used to change the grid or selection objective.

If a failure-cut challenger is later selected, it must be frozen before report-only review and then pass a fresh forward test before promotion. The protected +5c arm / 4c giveback logic remains the authority for trades that do arm.

## Hard guardrails

- SIGNAL ONLY / NO ORDERS.
- Do not alter protected primary eligibility.
- Do not add a scalp entry-price filter.
- Do not let a secondary scalp overwrite FINAL or EARLY.
- Do not allow simultaneous overlapping scalp positions in V1 research.
- Do not tune using REPORT_ONLY data.
- Do not promote a historical winner directly into the app.
- Any new actionable layer requires a frozen rule plus untouched forward confirmation.

Created after live shadow evidence showed: one contract produced a protected first scalp followed by a later strong opposite-side candidate, and another protected primary never armed +5c yet remained ACTIVE while materially adverse.
