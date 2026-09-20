# BTC15 EARLY CHEAP-SIDE MOTION HYPOTHESIS V1 — 2026-09-20

**Status:** FROZEN BEFORE HISTORICAL SCORING  
**Mode:** OFFLINE RESEARCH ONLY | SIGNAL ONLY | NO ORDERS  
**Production / protected EARLY / FINAL / SCALP:** UNCHANGED

## Why this is a different architecture

Clean post-fix telemetry shows that the existing preferred-side EARLY model often becomes confident only after Kalshi has already repriced above the user's useful entry range. This V1 does **not** loosen the existing <=45c protected rule.

Instead, it asks whether contemporaneous fast BTC movement can identify the still-cheap side before Kalshi catches up.

The numeric movement constants below are borrowed from the already-frozen scalp movement evidence rather than selected from this EARLY outcome sample.

## Historical development source

Use the preserved sub-minute market tape:
- `kalshi_scalp_shadow_snapshots_v1.csv`

Official Kalshi finalized result is truth.

This old tape is development evidence only. The clean 2026-09-20 post-fix window is not used to select or change the rule.

## Frozen candidate: CHEAP_SIDE_MOTION_V1

At each snapshot, evaluate UP and DOWN independently. A side qualifies only when all are true:

- 6 to 13 minutes remain;
- that side's executable ASK <= 50c;
- side-aligned BTC 5s move >= $4;
- side-aligned BTC 15s move >= $8;
- side-aligned BTC 30s move >= $15;
- the current 30-second velocity, projected for two minutes, is sufficient to cover any current wrong-side distance to the exact target;
- that side's ASK has moved no more than +2c over the prior 15 seconds (Kalshi has not already fully chased the move).

If both sides somehow qualify on one row, keep the side with the larger side-aligned BTC 30s move. Score only the first qualifying snapshot per contract.

No fair-value threshold is used. No result/settlement data can influence the live candidate row.

## Frozen metrics

Report:
- settled source contracts;
- calls and contract coverage;
- directional settlement accuracy;
- average and median ASK;
- 25–35c share;
- <=50c share;
- average and median minutes remaining;
- UP/DOWN call balance;
- chronological first-half and second-half metrics;
- unresolved contract count.

## Historical screen gate

V1 may advance to an untouched forward test only if all are true:

- >=15 calls;
- combined directional accuracy >=93%;
- average ASK <=40c;
- median ASK <=40c;
- average time remaining >=7.0 minutes;
- every entry <=50c;
- at least 3 UP and at least 3 DOWN calls;
- second chronological half directional accuracy >=90% with >=6 calls.

If V1 fails, scratch it as written. Do not lower the motion constants, raise the price cap, or change the two-minute projection using this same outcome sample.

## Guardrails

- No production change.
- Protected Tier-1 EARLY remains unchanged.
- Protected FINAL remains unchanged.
- SCALP remains unchanged.
- Clean post-fix data remains untouched for candidate selection.
- Signal only / manual execution / NO ORDERS.
