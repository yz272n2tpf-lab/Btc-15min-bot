# BTC15 SCALP PULLBACK-AFTER-MOVE HYPOTHESIS V1 — 2026-09-20

**Status:** FROZEN BEFORE SCORING  
**Mode:** OFFLINE RESEARCH ONLY | SIGNAL ONLY | NO ORDERS  
**Production / EARLY / FINAL:** UNCHANGED

## Why this hypothesis exists

Previous hard momentum tightening paths failed. The stable descriptive pattern in the preserved historical scalp tape is different: after movement qualification, +10c winners more often had a larger executable ASK pullback from the recent 60-second high than never-armed false starts.

This V1 therefore tests **timing the entry after the move is detected**, not adding another absolute-price gate and not tightening the movement detector itself.

## Protected movement baseline for the historical screen

The old preserved event tape can reproduce the previously frozen historical movement reference available in that file:

- first candidate per contract
- seconds_left >= 120
- side-aligned btc_move_30s >= $15
- no entry-price filter

This is a historical approximation only. It is not permission to replace the current full detector.

## Frozen candidate: PULLBACK_AFTER_MOVE_V1

For each historical baseline opportunity:

1. movement qualification happens first;
2. if the side's executable ASK is already at least **4c below its trailing 60-second ASK high**, the candidate may enter immediately;
3. otherwise watch for at most **30 seconds**;
4. trigger on the first later same-side row that still satisfies the historical movement baseline and has **drawdown_from_high >= 4c**;
5. if no such row appears within 30 seconds, the candidate passes on that opportunity.

No absolute ASK ceiling/floor is allowed. A 7c, 30c, or 70c entry can qualify if the movement + pullback timing rule qualifies.

Protected management after entry remains unchanged:
- +5c executable gain arms protection;
- EXIT remains the validated 4c giveback from running executable peak;
- no pre-arm stop is added.

## Frozen historical metrics

Compare baseline vs candidate:
- opportunities
- +5c arm rate inferred from max executable gain
- +10c hit rate
- +15c / +20c hit rates
- average / median entry ASK
- average seconds left
- average candidate delay
- opportunity retention
- +10c winner-ID retention
- +10c precision lift
- adverse excursion
- price-band distribution (telemetry only)

## Historical screen gate

V1 may become a clean-forward candidate only if all are true:

- candidate opportunity retention >= 70%
- +10c winner-ID retention >= 80%
- +10c precision lift >= +5 percentage points
- candidate average ASK <= baseline average ASK
- candidate average delay <= 30 seconds
- no price-band gate is introduced

If V1 fails, scratch it as written. Do not lower the 4c pullback or extend the 30-second wait after seeing the result.

## Guardrails

- historical tape only for development
- clean 2026-09-20 post-fix validation data remains untouched
- current movement detector is not changed by this study
- current serial lifecycle / ENDED_UNARMED semantics are not changed
- +5c arm / 4c giveback is not changed
- EARLY and FINAL are not changed
- signal only / manual execution / NO ORDERS
