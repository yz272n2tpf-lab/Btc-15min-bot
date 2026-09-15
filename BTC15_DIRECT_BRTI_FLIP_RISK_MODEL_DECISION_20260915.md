# BTC15 Direct-BRTI Flip Risk Model V1 Decision — 2026-09-15

## Decision
**HISTORICAL DIRECT-BRTI FAIL — V1 CLOSED ON THIS OOS COHORT**

READ ONLY · RESEARCH ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS.

This result is judged strictly against the methodology frozen before fitting in:
- `BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_20260915.md` commit `b51570beee557de70918a55f57034d5b912aed57`
- `BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_ADDENDUM_V1.md` commit `e7add340f98a063941023eedcfb3692505a72c2a`

Model implementation:
- `BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_V1.py` commit `d5a8c4902e844e491c04680020934668e0f358fa`
- tests `test_BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_V1.py` commit `8d3ce3d363b5f81d825d10fab9544eefe4f5b701`
- 6/6 mechanics tests PASS before the real fit.

Execution deployment:
- retired research-only service `scalp-coverage-audit-v1`
- service ID `f020787f-00fb-4a46-a36c-710f18bbf31e`
- one-shot deployment `3bb63f50-840f-4f1e-b840-5a3bda5287c4`
- trigger commit `a164b01d1759fa7500416676d064f0e1c5dbcef0`
- original retired-service start command restored immediately after scoring.

## Data / integrity
- 16,642 direct-BRTI tape rows.
- 100 tape contracts; 94 frozen feature-usable contracts.
- Official finalized Kalshi settlement only was used as truth.
- Feature dataset: 807 snapshots across 93 contracts; 39 frozen grid points excluded fail-closed.
- Chronological walk-forward block separation: PASS.
- Train/calibration/test contract disjointness within every block: PASS.
- No exact-second-zero/start feature.
- No future BRTI lag lookup.
- OOS sample gate: PASS — 44 unique contracts / 387 snapshots.

## Walk-forward block results
| Block | Test snapshots | Raw Brier | Calibrated Brier | Null Brier | Cal improves/ties raw |
|---|---:|---:|---:|---:|---|
| 1 | 128 | 0.187921 | 0.190624 | 0.190140 | NO |
| 2 | 134 | 0.192880 | 0.192662 | 0.224251 | YES |
| 3 | 125 | 0.132117 | 0.128032 | 0.150172 | YES |

Aggregate OOS:
- raw Brier = **0.171614**
- calibrated Brier = **0.171113**
- null Brier = **0.189041**
- calibrated Brier skill vs null = **9.4839%**
- blocks tie/improve = **2/3**

These parts of the frozen gate PASS. The direct-BRTI feature set contains real predictive ranking/skill; V1 did not fail because the signal was completely empty.

## Probability reliability — decisive failure
Populated reliability bins:
- 0–5% stated: n=53, actual=1.89%, stated=2.42%, error=0.53pp
- 5–10% stated: n=79, actual=16.46%, stated=7.34%, error=9.11pp
- 10–20% stated: n=107, actual=29.91%, stated=14.07%, error=15.83pp
- 20–30% stated: n=77, actual=18.18%, stated=24.71%, error=6.53pp
- 30–40% stated: n=47, actual=40.43%, stated=34.54%, error=5.89pp

Frozen gate metrics:
- weighted absolute calibration error = **8.8756pp** vs required <=5pp — **FAIL**
- maximum error among bins with n>=30 = **15.8330pp** vs required <=10pp — **FAIL**
- Spearman stated-vs-actual reliability = **0.9000** vs required >=0.80 — PASS

The main failure is probability calibration, especially severe under-statement of realized flip frequency in the stated 5–20% bands. A number like `12% Flip Risk` would therefore be materially misleading under this V1 model.

## Stay >=90% cohort — failure
- n=132 OOS snapshots
- 35 distinct OOS contracts
- actual stay rate = **89.3939%**
- frozen requirement = >=90%
- **FAIL**

The miss is small numerically, but the rule was frozen beforehand and is binding.

## Time-conditioning safety
Every populated frozen remaining-minute bucket passed the <=15pp time-bucket error limit:
- 9m: error 9.51pp
- 8m: 13.17pp
- 7m: 3.50pp
- 6m: 4.16pp
- 5m: 5.28pp
- 4m: 12.89pp
- 3m: 12.39pp
- 2m: 3.31pp
- 1m: 4.30pp

Therefore the failure is not a single catastrophic minute bucket. The dominant issue is global/reliability-band calibration.

## Binding interpretation
V1 is **closed on this OOS cohort**.

Do not:
- tune Platt/calibration thresholds on these same test blocks;
- add/drop features based on maximizing these same OOS scores and then re-claim them as untouched;
- expose a numeric Flip Risk %;
- modify EARLY, SCALP, FINAL, LOCK, PASS, entry, protection or exit logic;
- place orders.

## Next safe research step
Failure morphology may be diagnosed descriptively on this cohort, but any new calibration method, model family, feature set, or probability transformation must be predeclared and evaluated on **new untouched/future contracts**. The existing 44-contract OOS cohort is spent for model selection.

Until a new source-aligned calibration passes an independent gate, the dashboard numeric Flip Risk remains hidden/unvalidated.
