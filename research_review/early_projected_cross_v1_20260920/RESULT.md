# EARLY_PROJECTED_CROSS_V1 — development result

**Decision: REJECT.**

Preregistration commit: `031ab15699bf3028045bc378d791faefb5975120`

Development source: `subminute_early_dataset_v1.csv` (57 settled historical contracts; development evidence only).

No clean post-fix validation data was accessed.

## Result

- Calls: **33 / 57**
- Coverage: **57.89%**
- Correct: **13 / 33**
- Official settlement accuracy: **39.39%**
- First chronological half: **5 / 17 = 29.41%**
- Second chronological half: **8 / 16 = 50.00%**
- UP / DOWN calls: **19 / 14**
- Average / median ASK: **29.87c / 30c**
- Ideal 25–35c entries: **14 / 33**
- Average / median minutes remaining: **8.92 / 9.05**

## Frozen gate

Price, timing and coverage were attractive, but official settlement accuracy failed decisively.

No thresholds were changed after seeing the result.

## Interpretation

A fast projected target crossing is not enough to predict the eventual settlement winner. This behaves like short-horizon momentum: it finds cheap, early movement, but many projected crossings reverse before contract close.

This exact hypothesis is closed for EARLY final-direction use. It may describe short-horizon movement behavior, but it must not be relabeled as successful EARLY settlement prediction.

SIGNAL ONLY / NO ORDERS.
