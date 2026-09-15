# BTC15 COMBINED SAMPLE REVIEW TEMPLATE — 2026-09-15

STATUS: OFFLINE REVIEW TEMPLATE ONLY — NO AUTO-PROMOTION — NO ORDERS

Purpose: make the frozen common-universe EARLY + serial V5 SCALP + FINAL sample immediately reviewable when the 30 full-contract / 25 settled-contract gate is reached. This file changes no thresholds, runtime behavior, production behavior, pricing logic, lifecycle logic, timer behavior, or order behavior.

## Sample integrity

- Combined observer: `BTC15_COMBINED_FORWARD_SCORECARD_V1`
- Fresh cutoff: `2026-09-15T18:00:00Z`
- Startup partial contract excluded: REQUIRED
- Minimum fully observed contracts: 30
- Minimum officially settled contracts: 25
- Common contract universe: REQUIRED
- Union counts each contract once: REQUIRED
- Serial V5 scalp opportunities remain individually counted: REQUIRED
- EARLY / SCALP / FINAL remain separate modules: REQUIRED
- Signal-only / manual execution / no orders: REQUIRED

## Final review readout

### EARLY

- Actionable contracts: ___ / ___
- Contract coverage: ___%
- Settled calls: ___
- Accuracy: ___%
- Average entry ask: ___¢
- Median entry ask: ___¢
- Entry <=50¢: ___ / ___ = ___%
- Ideal 25–35¢ entries: ___
- Average minutes left: ___
- Median minutes left: ___

### SCALP

- Contracts with >=1 scalp: ___ / ___
- Contract coverage: ___%
- Total serial opportunities: ___
- Completed opportunities: ___
- Multi-scalp contracts: ___
- Maximum scalps in one contract: ___
- +5¢ move rate: ___%
- +10¢ move rate: ___%
- +15¢ move rate: ___%
- +20¢ move rate: ___%
- Protected exits: ___
- Positive protected-exit rate: ___%
- ENDED_UNARMED count: ___
- ENDED_UNARMED non-actionable invariant: PASS / FAIL
- Average entry ask: ___¢
- Median entry ask: ___¢
- Entry <=50¢: ___ / ___ = ___%
- Average minutes left at entry: ___
- Median minutes left at entry: ___

IMPORTANT: do not invent a new scalp +10 acceptance threshold here. Report performance; do not auto-promote or retune from this confirmation sample.

### FINAL

- Actionable contracts: ___ / ___
- Contract coverage: ___%
- Settled calls: ___
- Accuracy: ___%
- Average locked-side ask: ___¢
- Median locked-side ask: ___¢
- Locked side <=50¢: ___ / ___ = ___%
- Ideal 25–35¢ locks: ___
- Average minutes left: ___
- Median minutes left: ___

Target comparison only — not automatic promotion:
- FINAL >=93%: PASS / FAIL / INSUFFICIENT
- FINAL >=95%: PASS / FAIL / INSUFFICIENT

### UNION

- Actionable contracts: ___ / ___
- UNION coverage: ___%
- Uncovered contracts: ___
- User target >=90% coverage: PASS / FAIL / INSUFFICIENT

Path-combination counts:
- EARLY only: ___
- SCALP only: ___
- FINAL only: ___
- EARLY + SCALP: ___
- EARLY + FINAL: ___
- SCALP + FINAL: ___
- EARLY + SCALP + FINAL: ___
- NONE: ___

## Required interpretation

1. FINAL accuracy is not entry quality.
2. SCALP move/management metrics are not FINAL outcome accuracy.
3. A contract with several serial scalps still contributes only one contract to UNION coverage.
4. Expensive but correct FINAL locks must remain visible as expensive; they cannot masquerade as <=50¢ entries.
5. ENDED_UNARMED is lifecycle metadata only and never an actionable exit.
6. No numeric flip-risk percentage is valid until separately calibrated.
7. This review never authorizes automatic strategy promotion, automatic production deployment, or order placement.

## Decision line

- Sample ready: YES / NO
- Safety envelope intact: YES / NO
- UNION >=90%: YES / NO / INSUFFICIENT
- FINAL >=93%: YES / NO / INSUFFICIENT
- FINAL >=95%: YES / NO / INSUFFICIENT
- Entry quality acceptable for live-use workflow: REVIEW REQUIRED
- Production promotion authorized: NO — requires separate controlled decision
