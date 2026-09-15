# BTC15 Numeric Flip Risk Validation Freeze — 2026-09-15

Status: **PREDECLARED BEFORE REVIEWING THE NEW ONE-SHOT CALIBRATION OUTPUT**.

Signal only · manual execution only · no orders.

## Purpose
The dashboard requirement includes a numeric `Flip Risk %`, but a number such as
`12%` must not be displayed unless it is statistically calibrated. Until this
freeze gate is passed, Flip Risk remains qualitative / unvalidated telemetry.

## Existing historical candidate methodology
Reference script: `kalshi_flip_probability_calibration_validation.py`.

It uses:
- only information available at each lifecycle snapshot;
- corrected Kalshi contract timing;
- contract-level chronological separation;
- three untouched outer chronological blocks (70→80%, 80→90%, 90→100%);
- model / calibration / untouched test separation inside each outer block;
- isotonic probability calibration learned only from prior history;
- Brier scoring plus probability reliability tables;
- no bot changes and no order path.

A second independent reference implementation,
`kalshi_continuous_flip_probability_validation.py`, is diagnostic corroboration
only and does not replace the calibrated test.

## Frozen historical acceptance gate
All items below are required before numeric Flip Risk may advance to a **shadow
numeric display** experiment:

1. All hard integrity checks PASS:
   - settlement-label consistency;
   - no future-data use;
   - chronological outer holdouts;
   - calibration learned only from prior history;
   - no contract split across model/calibration/test;
   - corrected Kalshi timing;
   - lifecycle minutes 1–14 represented.
2. Calibrated Brier score must not be worse than raw Brier in the aggregate and
   must improve or tie raw Brier in at least 2 of the 3 untouched outer blocks.
3. Probability reliability must be directionally sensible: for populated bins
   (n>=20), actual flip frequency should generally rise as stated flip risk rises.
4. Weighted absolute calibration error across populated reliability bins must be
   <=5 percentage points in a follow-up scorer before promotion.
5. No populated reliability bin (n>=30) may miss its average stated probability
   by more than 10 percentage points in that follow-up scorer.
6. The `stay >=90%` cohort must empirically stay on the current side at >=90%
   in aggregate. This is a calibration check only and does not alter the
   protected FINAL lock rule.
7. Results must be based on untouched chronological OOS blocks, not the training
   or isotonic calibration segments.

## If historical gate passes
Historical PASS authorizes only:
- a separate read-only shadow `Flip Risk %` field;
- fresh-forward calibration collection;
- no change to EARLY, SCALP, FINAL, LOCK, PASS, entry, protection, or exit logic.

Fresh-forward review must then be frozen before collection and must include at
least 30 eligibility-complete contracts before numeric Flip Risk can be proposed
for the user-facing dashboard.

## If historical gate fails
- Keep numeric Flip Risk hidden / marked unvalidated.
- Do not tune thresholds on the same untouched test blocks.
- Diagnose failure morphology first and predeclare any new calibration method on
  a new holdout/future sample.

## Global guardrail
A visually plausible probability is not enough. Numeric Flip Risk must describe
observed frequency with acceptable calibration error. No result in this lane can
automatically modify production or place orders.
