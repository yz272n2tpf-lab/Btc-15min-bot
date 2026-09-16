# BTC15 Scalp Entry + Profit-Protection Ladder V1

**RESEARCH ONLY · SIGNAL ONLY · NO ORDERS**

This branch is isolated from the frozen Coverage Rescue V1 forward test. It does not change the generalized scalp detector, FINAL, EARLY, the live collector, or production dashboard logic.

## Question

Can we improve the ladder's entry economics and realized executable scalp capture without sacrificing useful timing or serial opportunity frequency?

## Entry policies

The policy grid is fixed for V1:

- `IMMEDIATE` — enter at the original candidate executable ask.
- `AFFORDABLE_15` — if original ask is above 50c, wait up to 15 seconds for the first then-current ask <=50c; otherwise PASS that candidate.
- `AFFORDABLE_30` — same, 30 seconds.
- `AFFORDABLE_45` — same, 45 seconds.
- `AFFORDABLE_60` — same, 60 seconds.
- `IDEAL_25_35_60` — wait up to 60 seconds for a then-current ask in the 25–35c ideal band; otherwise PASS that candidate.

Every delayed entry is rebased to the actual ask observed at entry. No historical/original ask is reused after the delay.

## Exit / profit-protection policies

- `LEGACY_5_4` — arm after +5c executable gain; exit after 4c giveback from the running peak.
- `PROTECT_5_3` — arm +5c; 3c giveback.
- `PROTECT_5_2` — arm +5c; 2c giveback.
- `STEPLOCK_5_3_10_4` — arm +5c with 3c giveback; after +10c, maintain at least a +5c floor while trailing 4c behind the running peak.
- `RUNNER_10_4` — do not arm until +10c; then trail by 4c.

A new serial scalp may start only after an actually observed protection exit. A terminal path value is accounting telemetry and cannot manufacture a serial reset.

## Scoring

Entry is executable ASK. Future movement and exit are executable BID minus that entry ASK. Reported metrics include:

- true contract coverage within each chronological split,
- +5c / +10c / +20c reach,
- <=50c entry rate,
- 25–35c entry rate,
- average/median entry ask,
- entry timing,
- average/median executable exit gain,
- positive exit rate,
- protected-exit rate,
- opportunities per covered contract,
- maximum serial opportunity index.

Exchange fees are **not yet included**, so executable exit gain is not a net-profit claim.

## Validation discipline

Contracts are split chronologically 60% DEVELOPMENT / 20% VALIDATION / 20% HOLDOUT. The live V1 reviewer exposes the policy grid on VALIDATION only. HOLDOUT remains sealed until a policy or small Pareto set is frozen from DEVELOPMENT + VALIDATION evidence.

V1 performs no automatic policy selection and no automatic promotion.
