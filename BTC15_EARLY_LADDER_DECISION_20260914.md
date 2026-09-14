# BTC15 EARLY Ladder Decision — 2026-09-14

**Status:** RETAIN PROTECTED TIER-1 | DO NOT FORWARD-TEST CURRENT PRE-WATCH/HANDOFF EXTENSION  
**Mode:** SIGNAL ONLY | NO ORDERS | OFFLINE RESEARCH

## Protected Tier-1 remains unchanged

Exact protected Tier-1 EARLY rule:

- preferred ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 2 to 10 minutes remaining
- absolute exact Kalshi target gap >= $25
- first qualifying row per contract

Historical untouched holdout reference:

- 20 / 22 correct = 90.9%
- 22% coverage
- average ask 31.9c
- median ask 34.0c
- average 6.09 minutes remaining

Replay reproduction in this research run:

- VALIDATION: 16 calls, 16.2% coverage, 100.0% accuracy, 35.7c average ask, 38.0c median ask, 5.31 minutes remaining.
- REPORT_ONLY: 22 calls, 22.0% coverage, 90.9% accuracy, 31.9c average ask, 34.0c median ask, 6.09 minutes remaining.

## Validation-selected PRE-WATCH champion

Selected using VALIDATION only:

- ask <= 45c
- fair >= 75%
- edge >= 2pp
- exact-target gap >= $20
- 3 to 11 minutes remaining

VALIDATION:

- 18 calls
- 18.2% coverage
- 94.4% directional accuracy
- average ask 37.9c
- median ask 39.0c
- average time remaining 6.50m
- 8 expensive-near-miss rescues before repricing
- those 8 were 100.0% directionally correct
- average lead before repricing: 120s
- 4 incremental contracts without protected Tier-1 (4.0%)

REPORT_ONLY — never used to select thresholds:

- 25 calls
- 25.0% coverage
- 72.0% directional accuracy
- average ask 32.5c
- median ask 34.0c
- average time remaining 6.68m
- 9 expensive-near-miss rescues before repricing
- rescue directional accuracy 77.8%
- average lead before repricing 100s
- 5 incremental contracts without protected Tier-1 (5.0%)

Decision: PRE-WATCH remains non-actionable. The report-only degradation is too large to support promotion or threshold tuning.

## Progression audit

VALIDATION PRE-WATCH calls showed strong same-side persistence after 30–120 seconds, with same-side directional accuracy at 100% on available follow-up rows. Kalshi repriced rapidly: median ask increase was roughly +32c by 30–60 seconds and +45c by 90–120 seconds.

REPORT_ONLY showed 84.0% same-side persistence but only 81.0% same-side directional accuracy. Median ask increase was about +30c by 30–60 seconds and +41c by 90–120 seconds.

This confirms the economic problem — strong-looking setups often reprice quickly — but does not create an actionable rule.

## Frozen handoff tournament result

The syntax-only runner repaired two malformed display f-strings in the frozen handoff scorer. No research rule, threshold, grid, ranking, split, metric, or eligibility condition was changed.

The frozen handoff tournament found **no candidate that passed the validation quality gate** of at least 12 actions with at least 90% directional accuracy.

The diagnostic fallback shown by the scorer produced zero confirmed actions and is not eligible for promotion.

Therefore the current PRE-WATCH -> handoff design fails the pre-frozen requirement before REPORT_ONLY promotion criteria are even considered.

## Decision

**DO NOT FORWARD-TEST OR PROMOTE THE CURRENT EARLY EXTENSION.**

- Keep protected Tier-1 EARLY exactly unchanged.
- Keep PRE-WATCH non-actionable.
- Do not retune against REPORT_ONLY.
- Do not loosen the <=45c protected Tier-1 entry cap to manufacture coverage.
- Do not create a new actionable EARLY rule from this historical result.
- A future EARLY extension would require a genuinely new, pre-frozen research hypothesis rather than post-hoc tuning of this failed tournament.

This is a successful research outcome: the extension was tested without moving the goalposts, failed its frozen quality requirements, and is rejected without damaging the protected anchor.

## Next system phase

Proceed with the modules that have earned their evidence:

1. Protected Tier-1 EARLY — retained unchanged.
2. Protected FINAL — retained unchanged.
3. Generalized SCALP challenger — KEEP / locked for integration based on untouched forward confirmation.

Next engineering target: build the integration layer that keeps EARLY, FINAL, and SCALP independent, resolves display/state precedence without allowing one module to overwrite another, and produces a combined system scorecard and live smoke-test path.

Hard guardrails: SIGNAL ONLY | NO ORDERS | no unvalidated numeric reversal-risk percentage.
