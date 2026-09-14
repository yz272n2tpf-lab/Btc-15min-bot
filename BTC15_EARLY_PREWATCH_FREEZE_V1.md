# BTC15 EARLY PRE-WATCH FREEZE V1

Status: research-only. Signal-only. No orders. No live behavior changes.

## Protected anchor
The existing Tier-1 EARLY rule is unchanged and remains the anchor:
- ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 2 to 10 minutes remaining
- absolute exact-target gap >= $25

The historical holdout anchor remains 90.9% accuracy (20/22), 22% coverage, 31.9c average ask, 34.0c median ask, and 6.09 minutes remaining on average.

## Research question
Can a separate PRE-WATCH state appear earlier in contracts that later become strong but too expensive, while Kalshi is still <= 50c, without weakening the protected Tier-1 rule?

## Frozen tournament design
- Search only historical snapshots already present in the processed replay cache.
- Candidate ask caps: 35c, 40c, 45c, 50c. Never test >50c.
- Candidate fair minimums: 60%, 65%, 70%, 75%.
- Candidate edge minimums: 2pp, 4pp, 6pp, 8pp.
- Candidate exact-target-gap minimums: $10, $15, $20, $25.
- Candidate time windows: 2-10m, 3-11m, 4-12m, 5-12m.
- One first qualifying candidate per contract for primary scoring.
- Chronological first half is selection/validation only.
- Second half is report-only and must not be used to tune the rule.
- Minimum validation support: 12 calls.
- Minimum validation accuracy for an eligible research champion: 90%.
- Rank eligible rules first by number of earlier rescues of expensive near-miss contracts, then by validation accuracy/support, incremental coverage, cheaper ask, and earlier timing.

## Guardrails
- PRE-WATCH is not automatically an actionable trade signal.
- No protected EARLY threshold is relaxed in live behavior.
- No holdout result may be used to retune thresholds after viewing it.
- If the validation champion fails badly on the report-only half, do not rationalize it; scratch or redesign before any new untouched test.
- Promotion to an actionable EARLY tier requires a separate frozen rule and untouched confirmation.
- Scalp forward test remains frozen and untouched while this offline EARLY research runs.
- Protected FINAL anchor remains unchanged.

## Desired outputs
For the champion report:
- calls and coverage
- accuracy
- average/median ask
- average/median time remaining
- percent <=35c and <=40c
- incremental coverage beyond protected Tier-1
- number of expensive near-miss contracts rescued earlier
- accuracy on those rescued contracts
- average/median lead time before Kalshi repriced above the protected entry cap

This freeze exists to prevent moving the goalposts after results are visible.
