# BTC15 Protected EARLY Excursion Forward Freeze — 2026-09-15

**Read only · signal only · manual execution only · no orders**

## Purpose

Measure whether the already-protected EARLY opportunity path produces a
tradable Kalshi move after entry. This is separate from FINAL settlement
accuracy and separate from SCALP qualification.

## Frozen source authority

- Production protected EARLY remains the only authority for an EARLY call.
- This study never re-runs, weakens, or strengthens EARLY qualification.
- Production protected FINAL remains the only authority for a later FINAL lock.
- No research output from this study changes production automatically.

## Fresh-sample semantics

- Startup contract is excluded.
- Fresh scoring begins only on the first post-start contract rollover.
- A contract enters the EARLY coverage universe only when first seen with
  **>=600 seconds remaining**, before protected EARLY can legally qualify.
- No historical or pre-start opportunity may be backfilled into the sample.

## Frozen excursion semantics

For the first protected EARLY call in each eligible contract:

- **Entry price** = protected EARLY preferred-side Kalshi ask.
- **Executable excursion price** = later live Kalshi bid on that same side.
- **MFE** = maximum later same-side bid minus EARLY entry ask.
- **MAE** = minimum later same-side bid minus EARLY entry ask.
- The initial bid/ask spread is intentionally included in MAE.

Descriptive move checkpoints:

- +5c
- +10c
- +15c
- +20c

For each checkpoint, record whether it was reached and time-to-first-hit.
These checkpoints are **measurement only**. They do not become qualification,
exit, protection, or promotion rules from this study.

## Downstream context

If protected FINAL later locks in the same contract, record:

- FINAL side,
- FINAL fair/confidence,
- FINAL locked-side ask,
- minutes remaining,
- whether FINAL confirms or flips from EARLY.

Official Kalshi settlement may be attached after contract close, but EARLY
settlement same-side rate is secondary context only. EARLY is an opportunity
path, not FINAL outcome authority.

## Frozen review readiness gate

The study becomes `EARLY_EXCURSION_REVIEW_SAMPLE_READY` only after:

- **>=30 eligibility-complete contracts**, and
- **>=10 completed protected EARLY excursions**.

When ready, report at minimum:

- EARLY call count and EARLY-only coverage,
- average/median entry ask,
- 25–35c ideal-entry count/rate,
- average/median minutes remaining at entry,
- average/median MFE,
- average/median MAE,
- +5c/+10c/+15c/+20c hit counts/rates,
- time-to-hit distributions,
- protected FINAL-after-EARLY count,
- EARLY/FINAL agreement rate,
- official-settlement same-side rate labeled secondary.

## Interpretation boundary

This study has **no predeclared PASS threshold**. It is a descriptive forward
measurement designed to answer whether protected EARLY creates useful tradable
moves at attractive entry prices. Any future rule change would require a
separate, explicitly frozen hypothesis and independent validation sample.

No numeric Flip Risk is inferred from this study. No order-placement path exists.
