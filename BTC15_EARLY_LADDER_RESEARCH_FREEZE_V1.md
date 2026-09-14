# BTC15 EARLY Ladder Research Freeze V1

**Status:** FROZEN BEFORE PRE-WATCH / HANDOFF RESULTS ARE JUDGED  
**Mode:** SIGNAL ONLY | NO ORDERS | OFFLINE RESEARCH

## Protected anchor — never weakened by this research

Tier-1 EARLY remains exactly:

- preferred ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 2 to 10 minutes remaining
- absolute exact Kalshi target gap >= $25
- first qualifying row per contract

Historical untouched holdout anchor remains the reference:

- 20 / 22 correct = 90.9%
- 22% coverage
- average ask 31.9c
- median ask 34.0c
- average 6.09 minutes remaining

No PRE-WATCH or handoff research may redefine this protected Tier-1 rule.

## Research sequence

1. `BTC15_EARLY_PREWATCH_TOURNAMENT_V1.py`
   - Validation half selects one PRE-WATCH champion.
   - Second half is REPORT_ONLY and cannot be used to choose thresholds.
   - No candidate may allow ask > 50c.
   - PRE-WATCH is telemetry only, never actionable by itself.

2. `BTC15_EARLY_PREWATCH_PROGRESS_AUDIT_V1.py`
   - Describes 30 / 60 / 90 / 120 second strengthening or weakening.
   - Measures same-side persistence, fair/edge/ask/gap changes, Tier-1 conversion, and repricing.
   - Selects no threshold and promotes nothing.

3. `BTC15_EARLY_PREWATCH_HANDOFF_TOURNAMENT_V1.py`
   - Tests a separate confirmation handoff from PRE-WATCH toward a possible earlier actionable EARLY tier.
   - Validation only selects the handoff candidate.
   - REPORT_ONLY is scored only after the validation-selected handoff is frozen.
   - Confirmed action ask may never exceed 50c.

## Pre-frozen decision rules

### PRE-WATCH

PRE-WATCH remains **non-actionable** regardless of how good its descriptive accuracy looks. Its purpose is to warn that a cheap directional setup may be forming before Kalshi fully reprices it.

Useful PRE-WATCH evidence should show all of the following:

- meaningful coverage beyond protected Tier-1;
- meaningful rescue of contracts that later became ready-but-expensive (>45c);
- direction persistence rather than frequent side flipping;
- enough lead time to matter economically;
- no dependence on REPORT_ONLY threshold tuning.

If those properties do not appear, scratch PRE-WATCH rather than weaken Tier-1.

### Possible actionable handoff tier

A handoff candidate is **not eligible for forward testing** unless all of these are true:

- validation sample >= 12 actions;
- validation directional accuracy >= 90%;
- REPORT_ONLY sample >= 12 actions;
- REPORT_ONLY directional accuracy >= 90%;
- every confirmed entry ask <= 50c by construction;
- median confirmed ask <= 45c;
- it creates real incremental actionable contracts beyond protected Tier-1;
- it normally acts before protected Tier-1 or rescues contracts that would otherwise reprice above the desired entry range;
- no threshold was changed after seeing REPORT_ONLY results.

Passing these gates earns **forward-test candidate** status only. It does not earn live promotion.

### Untouched forward requirement for a new actionable EARLY tier

Before live promotion, freeze the candidate exactly and collect at least **20 new unique qualifying contracts** with no threshold changes.

Forward report must include:

- unique qualifying contracts;
- directional accuracy;
- actionable coverage;
- average and median ask;
- average and median minutes remaining;
- <=35c share and <=40c share;
- incremental coverage beyond protected Tier-1;
- UP / DOWN balance;
- broad market-regime balance;
- how often the candidate strengthened into protected Tier-1;
- how often it weakened/flipped before settlement.

Promotion requires forward evidence consistent with the >=90% EARLY quality floor and economically useful entry prices. If not, scratch the extension and retain protected Tier-1 unchanged.

## Hard guardrails

- SIGNAL ONLY. Never place orders.
- Never use ask > 50c for the new early actionable tier.
- Do not chase 60c-80c entries just to raise coverage.
- Do not tune against REPORT_ONLY.
- Do not modify the protected scalp challenger while its untouched forward test is accumulating.
- Do not modify the protected FINAL anchor while EARLY research is running.
- Do not display an uncalibrated numeric flip/reversal-risk percentage as if validated.
- A WATCH state is not a trade signal.
- If the extension cannot earn its quality gate, scratch it rather than force coverage.
