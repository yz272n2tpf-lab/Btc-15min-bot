# BTC15 Signal Role + Entry Economics Map — 2026-09-16

Status: **INTERPRETATION FREEZE ONLY — NO RULE CHANGE — NO PROMOTION — NO ORDERS**

This note prevents metric drift while the fresh collectors continue. It does not alter EARLY, SCALP, FINAL, timer, Kalshi sync, price filtering, lifecycle, or order behavior.

## 1. FINAL = high-confidence direction / LOCK anchor, not the cheap-entry solution

### Historical fresh OOS reference
- Universe: 250 contracts after the old dataset.
- Calls: 133.
- Settlement accuracy: 132/133 = 99.25%.
- FINAL-only coverage: 53.2%.
- Average time left: 5.04 minutes; median: 5.00 minutes.
- Average preferred-side ask: 92.99c; median ask: 94.4c.
- Calls at or below 50c: 0/133.

### Current protected FINAL V4 forward sample, checked 2026-09-16 around 00:56 UTC
- Eligible fully observed contracts: 20.
- First FINAL locks: 11.
- Settled locks: 11.
- Correct settled locks: 11/11 so far.
- Current descriptive FINAL-only coverage: 11/20 = 55.0%.
- With no additional lock after the most recent emitted economics summary, lock economics remain: average ask 90.4c, median ask 92.0c, 0 locks at or below 50c; average 4.96 minutes left, median 4.85 minutes left.
- Fresh gate is **not ready**: requires >=30 eligible and >=12 settled locks.

Interpretation: FINAL remains the high-confidence direction/LOCK anchor. Its current and historical economics do **not** support treating it as the user's <=50c entry mechanism.

## 2. EARLY = affordable entry/opportunity lane; settlement direction is secondary context

Protected EARLY producer remains unchanged:
- preferred-side ask <=45c;
- target-aware model fair >=75%;
- model edge >=8 percentage points;
- 2 to 10 minutes remaining;
- absolute distance from Kalshi target >=$25.

### Historical fresh OOS EARLY_P40_NEW reference
- Calls: 12.
- Coverage: 4.8% of 250 contracts.
- Settlement same-side rate: 83.3%.
- Average ask: 30.4c; median ask: 32.0c.
- <=40c: 100%.
- Average time left: 6.42 minutes; median: 6.00 minutes.
- Acceptance result in the original frozen study: **NOT READY** because accuracy <93% and calls <15. Cheap economics and timing passed their checks.

### Historical fresh OOS EARLY_P45_PROVISIONAL reference
- Calls: 20.
- Coverage: 8.0%.
- Settlement same-side rate: 75.0%.
- Average ask: 35.4c; median ask: 39.0c.
- Average time left: 7.00 minutes; median: 6.50 minutes.

Interpretation: the historical EARLY lanes demonstrate the desired price/timing shape, but they do not establish the required final-outcome reliability. That is why the protected fresh EARLY collector and excursion collector remain separate confirmation lanes.

### First completed live EARLY excursion in the current frozen collector
Contract `KXBTC15M-26SEP152000-00`:
- EARLY side: DOWN.
- Entry ask: 43c.
- Time left: 3.29 minutes.
- Fair: 0.763; edge: 0.333.
- +5c, +10c, +15c, and +20c targets were all reached about 5.05 seconds after entry observation.
- Maximum favorable excursion: +55.9c.
- Maximum adverse excursion: about -1.0c.
- Official settlement: DOWN; same side as EARLY.

This is **n=1 descriptive evidence only**. It does not authorize promotion or threshold changes.

## 3. SCALP = movement / management lane, not FINAL settlement accuracy

Frozen reference remains:
- 115 completed serial opportunities.
- +10c movement rate: 77.4%.
- 70 protected exits.
- First-4c-crossing correctness on reviewed protected exits: 100%.
- Separate fresh reference: 61 opportunities / 33 contracts with 82.0% +10c movement rate.

Interpretation: +5/+10/+15/+20 are move/excursion metrics. They must never be relabeled as final-outcome accuracy.

## 4. Handoff / common universe = system coverage accounting

The handoff/common-universe lane is responsible for measuring how EARLY, SCALP, and FINAL combine on the same contracts. Union coverage is counted once per contract. Path-specific performance remains separate.

At the latest live check:
- Handoff collector remained healthy.
- 17 eligible contracts.
- 1 EARLY call, priced at 43c.
- 9 FINAL calls.
- 0 real EARLY->FINAL handoffs yet.
- Sample not ready.

Do not infer finished-system coverage or accuracy before the frozen handoff/common-universe gate is met.

## 5. Frozen reporting rules

1. **FINAL accuracy** = settlement accuracy of protected FINAL locks only.
2. **EARLY settlement same-side rate** = secondary directional context, never substituted for FINAL accuracy.
3. **EARLY economics** = ask, timing, edge, and protected excursion behavior.
4. **SCALP +10c** = movement-rate / opportunity-quality metric, never final accuracy.
5. **Union coverage** = one count per contract on the common universe only.
6. Never produce a blended 'system accuracy' by mixing FINAL settlement, EARLY settlement, and SCALP move metrics.
7. <=50c entry goal is evaluated through EARLY/SCALP opportunity economics, not by pretending expensive FINAL locks are entries.
8. Numeric Flip Risk stays hidden until separately validated and manually approved for display.
9. Signal-only, manual execution, no order placement.

## 6. Current working interpretation

The evidence is consistent with a three-part system design rather than one signal trying to do every job:

- **EARLY:** find tradable price/timing opportunities before the market becomes expensive.
- **SCALP:** capture and manage meaningful intracontract moves/reversals.
- **FINAL:** provide the selective high-confidence outcome/LOCK anchor.

This role split is descriptive and frozen for interpretation while the active forward gates collect. No production behavior changes are authorized by this note.
