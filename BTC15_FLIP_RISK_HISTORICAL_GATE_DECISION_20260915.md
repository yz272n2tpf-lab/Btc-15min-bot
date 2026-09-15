# BTC15 Numeric Flip Risk Historical Gate Decision — 2026-09-15

## Decision
**HISTORICAL GATE PASS — SHADOW NUMERIC DISPLAY VALIDATION ONLY**

This decision does **not** authorize a user-facing numeric Flip Risk %, a new
signal gate, a production change, or any order path.

The acceptance criteria were frozen first in
`BTC15_FLIP_RISK_NUMERIC_VALIDATION_FREEZE_20260915.md` at commit
`c203085899dd0f5011e3b5403a473f24af16629c`.

## Authoritative historical audit
Frozen validator: `kalshi_flip_probability_calibration_validation.py`.

Valid one-shot audit runtime:
- disposable service: `dashboard-source-diag-temp`
- valid raw calibration deployment: `bb263d8c-1234-4ee9-8587-4afe905739bf`
- 663 retained contracts
- 9,282 lifecycle snapshots
- three untouched chronological outer blocks
- no bot changes / no orders.

Two earlier temp deployments that still ran the dashboard diagnostic process are
explicitly non-evidence. Railway command/config precedence was diagnosed before
this decision. The disposable branch/service was restored after the audit.

## Untouched block Brier results
- Block 1 (70→80%): raw 0.1448, calibrated 0.1448 — tie.
- Block 2 (80→90%): raw 0.1562, calibrated 0.1381 — improvement.
- Block 3 (90→100%): raw 0.1716, calibrated 0.1583 — improvement.

Using the published untouched block sizes, approximate aggregate Brier from the
logged rounded values is:
- raw ≈ 0.15760
- calibrated ≈ 0.14712
- improvement ≈ 0.01048.

The margin is large relative to rounding and satisfies the frozen aggregate and
2-of-3 block requirements.

## Reliability gate
Published untouched OOS reliability bins:

| Stated flip risk | n | Actual flip | Avg stated | Abs error |
|---|---:|---:|---:|---:|
| 0–5% | 654 | 3.2% | 1.8% | 1.4pp |
| 5–10% | 181 | 6.6% | 7.8% | 1.2pp |
| 10–20% | 640 | 13.3% | 14.6% | 1.3pp |
| 20–30% | 379 | 28.5% | 26.2% | 2.3pp |
| 30–40% | 451 | 39.5% | 33.4% | 6.1pp |
| 40–50% | 460 | 42.8% | 43.2% | 0.4pp |
| 50–60% | 20 | 50.0% | 56.1% | 6.1pp |

From the frozen audit’s published counts and rounded rates:
- weighted absolute calibration error ≈ **2.116pp** (frozen limit 5pp);
- maximum absolute error among bins with n≥30 = **6.1pp** (frozen limit 10pp);
- actual flip frequency is non-decreasing across all populated n≥20 bins.

These margins remain passing under the reported rounding precision.

## 90% stay calibration check
- `stay >=90%`: n=841
- actual stay = **96.0%**
- average stated stay = 96.9%
- frozen minimum actual stay = 90%.

PASS.

## Hard integrity checks
The frozen validator reported PASS for:
- settlement-label consistency;
- future-data usage guard;
- outer chronological holdouts;
- calibration learned only from historical data;
- no contract split across model/calibration/test;
- corrected Kalshi timing;
- minutes 1–14 evaluated.

## Important time-conditioning finding
Aggregate calibration is strong, but high-stay predictions are not equally
calibrated at every elapsed minute. Notably among `stay >=90%` snapshots:
- minute 6: n=45, actual stay 88.9%, avg stated 96.4%;
- minute 7: n=58, actual stay 86.2%, avg stated 96.6%.

Therefore fresh-forward validation must report time-bucket calibration and must
not treat one aggregate number as equally reliable throughout the contract.
This is a display-calibration concern only; it does not modify protected FINAL.

## Gate interpretation
Historical PASS authorizes only the next research step:
1. prove live feature parity with the frozen historical feature definitions;
2. freeze a future-only shadow Flip Risk sample before collection;
3. collect at least 30 eligibility-complete contracts;
4. validate calibration overall and by time bucket;
5. only then consider a user-facing numeric Flip Risk display.

Until those steps pass, the dashboard numeric Flip Risk remains hidden /
unvalidated. Production, EARLY, SCALP, FINAL, LOCK, PASS, entry, protection and
exit logic remain unchanged. No orders.
