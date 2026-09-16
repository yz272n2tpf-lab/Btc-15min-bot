# Scalp Specialist Union V2

**Research only | signal only | no orders**

## Objective

Raise executable +10c scalp conversion without sacrificing useful 15-minute contract coverage or affordable entry economics.

V2 treats coverage as a hard research constraint rather than a side statistic.

## Specialist CORE lanes

1. `KALSHI_LAG` — side-aligned BTC/BRTI impulse while Kalshi ask repricing remains muted.
2. `MOMENTUM` — aligned continuation with intact structure and sufficient acceleration.
3. `REVERSAL_RECROSS` — a later serial opportunity flips side after a protected exit.
4. `REENTRY_CONTINUATION` — a later serial opportunity resumes the same side after a protected exit.

CORE remains restricted to these specialist lanes.

## Coverage rescue

If a fully observed contract has no CORE selection, V2 may use exactly one baseline scalp candidate as `COVERAGE_RESCUE` when its model probability clears the validation-frozen rescue threshold.

The rescue candidate may be unclassified by the four specialist lanes. This is intentional: classification rigidity must not silently destroy contract coverage.

Coverage rescue does **not** force a signal:
- no candidate -> no rescue;
- below rescue threshold -> no rescue;
- quiet contracts remain uncovered and stay in the denominator.

## True coverage denominator

A contract is counted in the denominator only when the event tape proves early and late observation of that 15-minute contract:
- at least one row with >=840 seconds remaining;
- at least one row with <=60 seconds remaining.

Once a contract qualifies for the denominator, it remains there even if it produced zero scalp opportunities.

## Contract-zone map

The companion `scalp_contract_zone_map_v1.py` reports where opportunities appear:
- 15-12 minutes left
- 12-9 minutes
- 9-6 minutes
- 6-3 minutes
- 3-2 minutes

It also reports cumulative true coverage by 12m, 9m, 6m, 3m and 2m remaining, including <=50c affordable contract coverage.

This helps distinguish two different problems:
- insufficient coverage because a contract never produces a candidate;
- sufficient coverage that arrives too late to be economically useful.

## Validation discipline

- Lane cut points: DEVELOPMENT feature distributions only.
- Quality model: DEVELOPMENT fit.
- CORE/rescue thresholds: VALIDATION only.
- HOLDOUT: report-only.
- Future PATH/RESULT fields are labels only.
- No automatic promotion.

Any rule chosen after reviewing this research still requires a newly frozen forward test on contracts that were not used to design or select it.

## Live review wrapper

`scalp_specialist_union_live_review_v1.py` is a separate read-only wrapper that can pull the existing event export with GET only and expose:
- baseline scalp metrics;
- specialist-lane metrics;
- contract-zone map;
- cumulative coverage;
- validation-selected V2 candidate;
- untouched holdout result.

The wrapper has no order capability and no production writes.
