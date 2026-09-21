# BTC15 EARLY Coverage Expansion — Tiered Directional Ladder V1

**Decision: NO STABLE HIGH-COVERAGE EARLY LADDER.**

No additional actionable tier is eligible to freeze for clean validation. No strategy was deployed or promoted.

The frozen three-family tournament did not approach 70–80% coverage with 93–95% official-settlement accuracy. More decisively, even an omniscient selector could cover only 52.26% of the August contracts or 55.50% of the September contracts at 93% accuracy using the recorded ≤50¢ quotes in the frozen 2–10 minute window. These are ceilings on these recorded observations, not a claim about unseen seconds, other market regimes, or entries with more than 10 minutes remaining.

## Preregistration and boundaries

Preregistration commit: `34edb8c30e34f9614bfb44e21b078c764bcda0a9`. Base/input commit: `13c8988fed8c97479203910f5620df64826246f3`. Three fixed families and three fixed ladder orders; no threshold grid, fitting, post-result changes, or second tournament. All source observations end by September 6, well before either reserved clean boundary.

Branch: `research/early-coverage-ladder-v1-20260921`. Final results commit is recorded by the Git commit containing this report. The protected forward specification and original Tier-1 rule remain unchanged.

| Family | Frozen hypothesis | Availability |
| --- | --- | --- |
| Tier 1 | ASK ≤45¢, fair ≥75%, edge ≥8pp, 2–10m, absolute exact-target gap ≥$25; first qualifying row | Both cohorts; unchanged |
| A | Target cushion ≥1.50 × volatility scaled to remaining time; no momentum projection or fair threshold | Both cohorts |
| B | BTC and fresh BRTI both ≥$25 ahead of the same target; disagreement ≤$15; BRTI age ≤2s | September only |
| C | Preferred fair ≥75%, strengthening ≥10pp/30s, nondecreasing over 15s, ASK not rising over 30s, target-supported | September only |

Lower-tier common gates: actual ASK ≤50¢, spread ≤5¢, 4–10 minutes left; finite valid inputs. Exact formulas, missing-data handling, sample floors and advancement gates are in [PREREGISTRATION.md](PREREGISTRATION.md). B and C are unavailable in August, not empirically rejected there. A produced no calls in either cohort. B and C failed on September evidence and remain non-actionable; WATCH is not BUY.

## Sources and population

August replay: 199 unique contracts and 2,700 preferred-side minute snapshots, August 20–22. September observed sample: 221 unique contracts across September 3–6; 218 have a valid observation in the 2–10m denominator window. The raw snapshot source contributes 153 eligible contracts and the unified source 65, with no overlap. Three contracts without that window are excluded explicitly. This is observed-contract coverage, not continuous-calendar uptime coverage.

All 420 distinct historical contracts were matched to saved official Kalshi finalized market.result responses; zero unresolved, zero conflicts with the available archived settlement labels. Every nonmissing derived/logged fixed target matches the official floor strike within $0.01. Two side rows of one zero-gap August snapshot have an unrecoverable derived target (0/0); they fail the target-cushion family and cannot qualify Tier 1. Labels are official yes→UP / no→DOWN. No +5/+10 excursion is used as success.

| Historical source at base commit | Rows | Contracts | Use |
| --- | --- | --- | --- |
| union_optimizer_processed_snapshot_cache.csv | 2700 | 199 | Feature/quote source |
| brti_calibration_results.csv | 663 | 663 | Archived label/target cross-check |
| kalshi_scalp_shadow_snapshots_v1.csv | 25828 | 156 | Feature/quote source |
| kalshi_early_conf_shadow_v1.csv | 2590 | 15 | Feature/quote source |
| kalshi_early_conf_shadow_v1_1.csv | 23 | 1 | Feature/quote source |
| kalshi_early_conf_shadow_v1_2.csv | 16660 | 101 | Feature/quote source |
| kalshi_direct_brti_parity_v1.csv | 16642 | 100 | Feature/quote source |
| kalshi_subminute_unified_v1_1.csv | 22320 | 65 | Feature/quote source |
| subminute_official_truth_cache.csv | 60 | 60 | Archived label/target cross-check |
| kalshi_official_settlement_check.csv | 583 | 583 | Archived label/target cross-check |
| subminute_early_dataset_v1.csv | 3914 | 57 | Provenance only; excluded from scoring |

Full SHA-256 hashes, timestamps and the exact settlement allowlist are in `source_manifest.json`; all official responses are preserved in `evidence.zip`. The old price-filtered sub-minute dataset was not scored because its builder used nearest joins that could take features up to four seconds in the future. This study instead used raw snapshots with backward-only, same-contract, same-target enrichment, at most five seconds old. That lag is added to BRTI age. Missing inputs fail closed.

August ASK is a reconstructed candle-end historical quote, not proof of a contemporaneously executable manual fill. The original BTC candle timestamp open/close semantics remain unresolved; the archived benchmark is reproduced, not certified as causal live performance. September uses observed quote snapshots, typically five seconds apart (maximum observed within-contract gap 385.38 seconds). Neither dataset proves depth, a manual fill, fees, or latency. Fair-model versions and sampling differ across cohorts; their accuracies are not pooled.

## Chronological development halves

| Cohort | Half | Contracts | First close UTC | Last close UTC |
| --- | --- | --- | --- | --- |
| august_replay | 1 | 99 | 2026-08-20 12:00:00+00:00 | 2026-08-21 12:30:00+00:00 |
| august_replay | 2 | 100 | 2026-08-21 12:45:00+00:00 | 2026-08-22 13:30:00+00:00 |
| september_observed | 1 | 109 | 2026-09-03 04:15:00+00:00 | 2026-09-04 22:45:00+00:00 |
| september_observed | 2 | 109 | 2026-09-04 23:00:00+00:00 | 2026-09-06 19:00:00+00:00 |

All rules were frozen before scoring either half. The second half is report-only for this run. All data were previously exposed historical development evidence, so neither half is a new independent holdout.

## August reconstructed replay

Standalone families (each first call per unique contract):

| Family | Calls | Coverage | Official settlement accuracy | First half | Second half | UP / DOWN |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 38 | 19.10% | 36/38 (94.74%) | 16/16 (100.00%) | 20/22 (90.91%) | 28 / 10 |
| A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| B | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| C | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |

| Family | ASK mean / median ¢ | 25–35¢ count / rate | ≤40¢ count / rate | ≤50¢ rate | Minutes mean / median | Wilson 95% accuracy interval |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 33.51 / 36.50 | 12 / 31.58% | 30 / 78.95% | 100.00% | 5.76 / 5.00 | 82.71%–98.54% |
| A | — / — | 0 / — | 0 / — | — | — / — | —–— |
| B | — / — | 0 / — | 0 / — | — | — / — | —–— |
| C | — / — | 0 / — | 0 / — | — | — / — | —–— |

The protected benchmark reproduces exactly: **36/38 = 94.74%**, coverage **19.10%**. Its unchanged 7–10m first-call slice also reproduces **13/14 = 92.86%**, mean ASK 37.29¢, mean time 9.14m. No lower family adds an August contract. Every ladder prefix therefore remains 38 calls, 19.10% coverage and 94.74% accuracy.

Incremental membership attribution (higher tiers own overlapping contracts; no double-counting):

| Ladder | Tier | Incremental calls | Coverage added | Settlement accuracy | First half | Second half | UP / DOWN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Tier 1: T1 | 38 | 19.10% | 36/38 (94.74%) | 16/16 (100.00%) | 20/22 (90.91%) | 28 / 10 |
| L1 | Tier 2: A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L1 | Tier 3: B | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L2 | Tier 1: T1 | 38 | 19.10% | 36/38 (94.74%) | 16/16 (100.00%) | 20/22 (90.91%) | 28 / 10 |
| L2 | Tier 2: B | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L2 | Tier 3: C | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L3 | Tier 1: T1 | 38 | 19.10% | 36/38 (94.74%) | 16/16 (100.00%) | 20/22 (90.91%) | 28 / 10 |
| L3 | Tier 2: A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L3 | Tier 3: C | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |

| Ladder | Tier | ASK mean / median ¢ | 25–35¢ count / rate | ≤40¢ count / rate | ≤50¢ rate | Minutes mean / median |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | Tier 1: T1 | 33.51 / 36.50 | 12 / 31.58% | 30 / 78.95% | 100.00% | 5.76 / 5.00 |
| L1 | Tier 2: A | — / — | 0 / — | 0 / — | — | — / — |
| L1 | Tier 3: B | — / — | 0 / — | 0 / — | — | — / — |
| L2 | Tier 1: T1 | 33.51 / 36.50 | 12 / 31.58% | 30 / 78.95% | 100.00% | 5.76 / 5.00 |
| L2 | Tier 2: B | — / — | 0 / — | 0 / — | — | — / — |
| L2 | Tier 3: C | — / — | 0 / — | 0 / — | — | — / — |
| L3 | Tier 1: T1 | 33.51 / 36.50 | 12 / 31.58% | 30 / 78.95% | 100.00% | 5.76 / 5.00 |
| L3 | Tier 2: A | — / — | 0 / — | 0 / — | — | — / — |
| L3 | Tier 3: C | — / — | 0 / — | 0 / — | — | — / — |

Causal combined prefixes (first actual entry across enabled tiers; a later Tier 1 cannot replace it):

| Ladder | Enabled families | Union calls | Union coverage | Union accuracy | Mean ASK ¢ | Mean minutes | First half | Second half |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | T1 | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L1 | T1 + A | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L1 | T1 + A + B | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L2 | T1 | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L2 | T1 + B | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L2 | T1 + B + C | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L3 | T1 | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L3 | T1 + A | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |
| L3 | T1 + A + C | 38 | 19.10% | 36/38 (94.74%) | 33.51 | 5.76 | 16/16 (100.00%) | 20/22 (90.91%) |

## September observed snapshots

Standalone families (each first call per unique contract):

| Family | Calls | Coverage | Official settlement accuracy | First half | Second half | UP / DOWN |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 14 | 6.42% | 8/14 (57.14%) | 4/8 (50.00%) | 4/6 (66.67%) | 4 / 10 |
| A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| B | 16 | 7.34% | 10/16 (62.50%) | 6/11 (54.55%) | 4/5 (80.00%) | 4 / 12 |
| C | 12 | 5.50% | 5/12 (41.67%) | 3/5 (60.00%) | 2/7 (28.57%) | 6 / 6 |

| Family | ASK mean / median ¢ | 25–35¢ count / rate | ≤40¢ count / rate | ≤50¢ rate | Minutes mean / median | Wilson 95% accuracy interval |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 37.93 / 39.00 | 5 / 35.71% | 8 / 57.14% | 100.00% | 4.89 / 3.13 | 32.59%–78.62% |
| A | — / — | 0 / — | 0 / — | — | — / — | —–— |
| B | 42.56 / 44.50 | 2 / 12.50% | 5 / 31.25% | 100.00% | 7.76 / 7.35 | 38.64%–81.52% |
| C | 44.17 / 45.50 | 1 / 8.33% | 3 / 25.00% | 100.00% | 7.73 / 8.53 | 19.33%–68.05% |

The same protected qualification rule yields **8/14 = 57.14%** on these September observations. That is a material historical generalization concern, not a score of the current clean observer. Its standalone Wilson interval is 32.59–78.62%; do not carry the August 94.74% result forward as a universal accuracy claim.

Incremental membership attribution (higher tiers own overlapping contracts; no double-counting):

| Ladder | Tier | Incremental calls | Coverage added | Settlement accuracy | First half | Second half | UP / DOWN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Tier 1: T1 | 14 | 6.42% | 8/14 (57.14%) | 4/8 (50.00%) | 4/6 (66.67%) | 4 / 10 |
| L1 | Tier 2: A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L1 | Tier 3: B | 9 | 4.13% | 6/9 (66.67%) | 4/6 (66.67%) | 2/3 (66.67%) | 2 / 7 |
| L2 | Tier 1: T1 | 14 | 6.42% | 8/14 (57.14%) | 4/8 (50.00%) | 4/6 (66.67%) | 4 / 10 |
| L2 | Tier 2: B | 9 | 4.13% | 6/9 (66.67%) | 4/6 (66.67%) | 2/3 (66.67%) | 2 / 7 |
| L2 | Tier 3: C | 4 | 1.83% | 1/4 (25.00%) | 1/1 (100.00%) | 0/3 (0.00%) | 2 / 2 |
| L3 | Tier 1: T1 | 14 | 6.42% | 8/14 (57.14%) | 4/8 (50.00%) | 4/6 (66.67%) | 4 / 10 |
| L3 | Tier 2: A | 0 | 0.00% | 0 calls; not estimable | 0 calls; not estimable | 0 calls; not estimable | 0 / 0 |
| L3 | Tier 3: C | 7 | 3.21% | 2/7 (28.57%) | 2/4 (50.00%) | 0/3 (0.00%) | 4 / 3 |

| Ladder | Tier | ASK mean / median ¢ | 25–35¢ count / rate | ≤40¢ count / rate | ≤50¢ rate | Minutes mean / median |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | Tier 1: T1 | 37.93 / 39.00 | 5 / 35.71% | 8 / 57.14% | 100.00% | 4.89 / 3.13 |
| L1 | Tier 2: A | — / — | 0 / — | 0 / — | — | — / — |
| L1 | Tier 3: B | 43.22 / 48.00 | 1 / 11.11% | 3 / 33.33% | 100.00% | 8.34 / 8.78 |
| L2 | Tier 1: T1 | 37.93 / 39.00 | 5 / 35.71% | 8 / 57.14% | 100.00% | 4.89 / 3.13 |
| L2 | Tier 2: B | 43.22 / 48.00 | 1 / 11.11% | 3 / 33.33% | 100.00% | 8.34 / 8.78 |
| L2 | Tier 3: C | 44.00 / 44.00 | 0 / 0.00% | 1 / 25.00% | 100.00% | 6.78 / 6.56 |
| L3 | Tier 1: T1 | 37.93 / 39.00 | 5 / 35.71% | 8 / 57.14% | 100.00% | 4.89 / 3.13 |
| L3 | Tier 2: A | — / — | 0 / — | 0 / — | — | — / — |
| L3 | Tier 3: C | 45.71 / 46.00 | 0 / 0.00% | 1 / 14.29% | 100.00% | 7.38 / 8.32 |

Causal combined prefixes (first actual entry across enabled tiers; a later Tier 1 cannot replace it):

| Ladder | Enabled families | Union calls | Union coverage | Union accuracy | Mean ASK ¢ | Mean minutes | First half | Second half |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | T1 | 14 | 6.42% | 8/14 (57.14%) | 37.93 | 4.89 | 4/8 (50.00%) | 4/6 (66.67%) |
| L1 | T1 + A | 14 | 6.42% | 8/14 (57.14%) | 37.93 | 4.89 | 4/8 (50.00%) | 4/6 (66.67%) |
| L1 | T1 + A + B | 23 | 10.55% | 14/23 (60.87%) | 41.26 | 6.88 | 8/14 (57.14%) | 6/9 (66.67%) |
| L2 | T1 | 14 | 6.42% | 8/14 (57.14%) | 37.93 | 4.89 | 4/8 (50.00%) | 4/6 (66.67%) |
| L2 | T1 + B | 23 | 10.55% | 14/23 (60.87%) | 41.26 | 6.88 | 8/14 (57.14%) | 6/9 (66.67%) |
| L2 | T1 + B + C | 27 | 12.39% | 14/27 (51.85%) | 41.56 | 7.09 | 9/15 (60.00%) | 5/12 (41.67%) |
| L3 | T1 | 14 | 6.42% | 8/14 (57.14%) | 37.93 | 4.89 | 4/8 (50.00%) | 4/6 (66.67%) |
| L3 | T1 + A | 14 | 6.42% | 8/14 (57.14%) | 37.93 | 4.89 | 4/8 (50.00%) | 4/6 (66.67%) |
| L3 | T1 + A + C | 21 | 9.63% | 9/21 (42.86%) | 41.33 | 6.22 | 6/12 (50.00%) | 3/9 (33.33%) |

The largest fixed union is **T1+B+C: 27/218 = 12.39% coverage**, **14/27 = 51.85% accuracy**, mean ASK **41.56¢**, mean time **7.09m**. B adds nine contracts beyond Tier 1; C adds four beyond both. B’s incremental accuracy is 6/9; C’s is 1/4. Neither meets the 30-incremental-call floor or the accuracy/economics gates.

Retrospective Tier-1-priority attribution would misleadingly show 15/27 winners for L2; causal first-entry scoring correctly shows 14/27. Six Tier-1 contracts receive earlier lower-tier calls in L2, with three side disagreements. L1 attribution and causal accuracy are both 14/23; L3 changes from 10/21 attributed to 9/21 causal. The report does not present retrospective precedence as deployable behavior.

## Accuracy / coverage frontier and recorded-price ceiling

The measured high-quality point remains only the August Tier-1 replay: 94.74% accuracy at 19.10% coverage. The September bounded tournament has no 93% point. T1+B reaches 60.87% at 10.55% coverage; T1+B+C reaches 51.85% at 12.39%. These are measured points from the preregistered policies, not an exhaustive optimized frontier.

For a strategy with one call per contract, let W be the number of contracts whose eventual winner ever had a recorded ASK≤50¢ in the allowed window. Even hindsight cannot supply more than W correct entries. At 93% required accuracy, calls≤floor(W/0.93). This generous ceiling ignores all predictive-feature and signal-quality restrictions.

| Cohort | Entry window | Winner ever ≤50¢ / eligible | Maximum calls at ≥93% | Maximum coverage |
| --- | --- | --- | --- | --- |
| august_replay | 2–10m | 97/199 | 104 | 52.26% |
| august_replay | 4–10m | 94/199 | 101 | 50.75% |
| september_observed | 2–10m | 113/218 | 121 | 55.50% |
| september_observed | 4–10m | 105/218 | 112 | 51.38% |

For 70% coverage, the August sample requires at least 140 calls and September at least 153. With only 97 and 113 available winners respectively, even perfect hindsight caps accuracy at 69.29% and 73.86% at those call counts. At 80% coverage, the corresponding upper accuracy bounds fall to 60.63% and 64.57%. For these recorded windows, 70–80% coverage cannot coexist with 93–95% settlement accuracy and ≤50¢ ASK.

This does not prove a universal market impossibility. Prices between recorded observations, earlier entries outside the frozen window, other dates, or different data quality are untested. No post-result earlier-entry experiment was added.

## Decision and protected systems

**NO STABLE HIGH-COVERAGE EARLY LADDER. No new actionable tier or candidate is frozen for clean validation.** Tier 1 remains exactly protected; its existing forward validation continues unchanged. FINAL remains later confirmation/danger assessment; this study did not create a late BUY ladder. No WATCH signal is counted as approved actionable coverage. All expanded-union figures above are hypothetical research entries, not certified BUY states.

Production, protected EARLY and FINAL, SCALP, BRTI, Kalshi plumbing, quote provenance, contract timing, running clean EARLY observer, running clean SCALP collector, and Directional Position Manager work were not modified. No Railway or live-dashboard calls were made; no clean-forward data were read or scored. Only a new research branch/directory was written. **SIGNAL ONLY / NO ORDERS.**

## Verification and reproducibility

Eight focused tests passed. Independent audit checked 1358 per-policy entry records (77 distinct source rows), raw entry ASK values, all official labels, exact target alignment, chronological membership and the oracle bounds. Both protected August reference results reproduce exactly. No outcome-conditioned retuning occurred.

Implementation corrections: initial CSV timestamp parsing required mixed fractional-second handling before scoring; a pandas assignment warning was removed without changing values; the target audit was corrected to explicitly account for the two missing zero-gap derived targets. None changed the frozen rules, calls, or sample selection.

From the repository root on this branch, run:

```bash
python research_review/early_coverage_ladder_v1_20260921/reproduce.py
```

The command uses pinned repository inputs and saved evidence; no network is needed. It rebuilds features, runs the tournament, runs the eight tests and independent audit, then checks result hashes. `prepare.py --fetch-labels` is optional historical-label recovery only; it is not used by reproduction.

Files: `PREREGISTRATION.md`, `source_manifest.json`, `prepare.py`, `score.py`, `test_study.py`, `audit.py`, `report.py`, `reproduce.py`, `boundary_receipt.json`, `verification.json`, `reproduction_hashes.json`, and `evidence.zip`. The evidence archive contains `metrics.csv`, `per_call.csv`, `membership.csv`, `labels.csv`, `results.json`, data-quality/label-retrieval receipts and all 420 official market responses. `metrics.csv` includes full UP/DOWN counts and accuracies, price bands, medians, confidence intervals and chronological-half metrics for every family, incremental tier and union prefix.
