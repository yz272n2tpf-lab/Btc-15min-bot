# BTC15 EARLY PRE-REPRICING LEAD/LAG HYPOTHESIS V1 — 2026-09-20

**Status:** FROZEN BEFORE SCORING  
**Mode:** OFFLINE RESEARCH ONLY | SIGNAL ONLY | NO ORDERS  
**Production:** UNCHANGED

## Purpose

Test one genuinely new EARLY hypothesis aimed at the known problem: protected EARLY can be accurate and cheap when it fires, but often does not fire early enough before Kalshi reprices.

This study uses the preserved old sub-minute EARLY tape `kalshi_early_conf_shadow_v1_2.csv` (2026-09-03 through 2026-09-05). It does **not** inspect or tune on the clean post-fix 2026-09-20 validation window.

## Protected EARLY reference

The protected Tier-1 rule remains unchanged and is scored only as a reference:

- preferred ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 2 to 10 minutes remaining
- absolute BTC target gap >= $25
- first qualifying row per contract

## New hypothesis: PREPRICE_LEADLAG_V1

The hypothesis is that a useful EARLY call can be made sooner when the target-aware fair value is strengthening over 15–30 seconds while Kalshi has not yet repriced by the same amount.

First qualifying row per contract must satisfy all of:

- preferred ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 6 to 11 minutes remaining
- absolute BTC target gap >= $25
- fair_move_15s >= +2 percentage points
- fair_move_30s >= +2 percentage points
- ask_move_15s <= +1c
- ask_move_30s <= +2c

No persistence delay is required. The point is to detect the fair-value move before the market price catches up.

## Truth source

Official Kalshi finalized market result (YES=UP, NO=DOWN) only. Unresolved/API-failed contracts are excluded and counted.

## Frozen metrics

Report:
- eligible settled contracts
- calls and contract coverage
- directional accuracy
- average/median preferred ask
- 25–35c share
- <=50c share
- average/median minutes remaining
- UP/DOWN balance
- overlap with protected Tier-1
- calls earlier than the same contract's protected Tier-1 and median lead seconds
- incremental contracts not reached by protected Tier-1

## Historical screen gate

PREPRICE_LEADLAG_V1 may become a clean-forward candidate only if all are true on this old historical block:

- >= 12 calls
- directional accuracy >= 93%
- average ask <= 40c
- median ask <= 40c
- average time remaining >= 7.0 minutes
- all entries <= 45c
- at least 3 calls occur earlier than the same contract's protected Tier-1 OR at least 3 incremental contracts are added

If it fails, V1 is scratched as written. Do not tune these thresholds after seeing the result.

## Guardrails

- no production change
- no change to protected EARLY
- no change to FINAL
- no change to SCALP
- clean 2026-09-20 validation data remains untouched
- no orders / no auto trading
