# BTC15 EARLY Value-Entry Research

September 29, 2026 | Frozen cohort research | Signal-only/manual execution | No orders

**Decision C - CURRENT FEATURE SET CANNOT SUPPORT THE TARGET RELIABLY.** The tested, interpretable family provides no defensible route to 85% reliability at ASK <=50c. This is an empirical rejection of these recorded-feature rules, not a proof that every possible model or future dataset must fail. No candidate advances; no production qualification is claimed.

## Direct answers, 1-6

**1. What distinguishes affordable eventual winners from losers?** No stable, validated separator emerged. In development, winners sometimes had more stable model sides, larger ASK pullbacks and lower sampled recent BTC ranges. These relationships weakened or reversed later. Higher raw fair and edge did not reliably distinguish cheap winners. At first affordable observations, the 60-75% fair bucket won only 18/42 (42.9%) across the cohort.

**2. Which current gates are useful, redundant, contradictory or mistimed?** The ASK cap enforces the economic objective, but is not itself predictive. The 8-point edge gate is mathematically redundant with fair >=75% and ASK <=45c: those imply at least 30 points of raw edge. Price, large absolute gap and timing are empirically incompatible here: no <=45c plus $25-gap observation occurred with 2-10 minutes remaining. The $25 gate's predictive usefulness at cheap prices is unproven. The time window suppresses observation coverage; relaxing it has not shown useful reliability.

**3. Is the current window suppressing useful early opportunities?** It excludes 376/788 affordable, >=5-point-edge observations across 97 contracts. But first qualifying observations during the first five minutes won only 39/97 (40.2%; Wilson 31.0-50.2%). It suppresses affordable observations, not demonstrated high-quality signals.

**4. Do trajectories, persistence or context improve discrimination?** Not robustly in this study. Eight frozen research rules testing elapsed stability, persistence, pullbacks, edge growth, convergence, gap reclaim and sampled context produced pooled accuracies of 26.5-35.0%. No later-data retuning was allowed. A promising-looking development direction frequently reversed in validation or the final segment.

**5. What is the strongest defensible candidate?** None. The development selection gate rejected every rule before validation. T1, the only research rule with at least 30 development events, scored 11/33. T7 was retained solely as a pre-validation diagnostic reference, based on the highest development Wilson lower bound among rules with at least 20 events. It is not a recommendation.

**6. Accuracy, sample size, uncertainty, coverage, economics and timing?** T1 scored 28/84 (33.3%; Wilson 24.2-43.9%), at mean ASK 47.19c, covering 41.6% of the 202 numerically scoreable contracts. T7 scored 15/47 (31.9%; 20.4-46.2%), at mean ASK 46.98c and 9.88 minutes remaining, covering 23.3% of observed contracts or 18.9% of all 249 settlements. Only 1/47 T7 events was in the 25-35c band. The negative control remains exactly 52/130 = 40.0%.

<!-- PAGE -->
## Direct answers, 7-12

**7. How does it perform chronologically?** T7: development 9/24 (37.5%), validation 3/13 (23.1%), final chronological segment 3/10 (30.0%). T1: 11/33, 5/22 and 12/29. No rule passed the predeclared development reliability gate. The entire cohort had already been inspected before this mission; the final segment is a held-apart comparison in this run, not newly untouched prospective validation.

**8. What are the losing patterns?** Every one of T7's 32 losing origins later had a model-side disagreement and a sampled BTC gap against the original side. Eight began with an absolute gap below $5. Losses were not confined to tiny gaps: 22/31 events in the signed $5-25 bucket lost. Some large gap/range ratios came from a nearly flat sampled BTC series, which can be misleading without source-update provenance. Seven of T7's 15 winners also experienced later disagreement; disagreement cannot be turned into a reliable automatic EXIT.

**9. Does the result survive ablations and nearby perturbations?** The negative conclusion does. Removing either T7 component and changing stability, gap/range, ASK and edge one at a time produced 25.0-44.6% pooled accuracy. The best number includes a 52c cap that violates the <=50c objective. No variant was selected after seeing later outcomes. Small final-two-minute slices such as 3/5 are explicitly insufficient.

**10. Does it depend on unavailable live evidence?** The tested numerical features can in principle be derived from an admitted history of protected publications; no missing TradingView, seconds bars, native volatility or V2 witness was fabricated. However, this journal lacks the quote/source/receipt/publication identities and clock bounds needed to certify those historical observations as live-admissible. BRTI age telemetry was never converted into a clock. Fully evidence-qualified entries remain UNAVAILABLE.

**11. What BUY/HOLD/PROTECT behavior follows?** There is no surviving EARLY candidate and no authentic protected FINAL/origin linkage in this snapshot, so actual BUY/HOLD/PROTECT replay is UNAVAILABLE. The output contains immutable research proposals, never fills or actual bot signals. Later held-side probabilities and same-side BID paths are descriptive only. No EXIT rule was added or inferred; SCALP was not merged with directional research.

**12. What remains unproven?** 85% or 90% reliability at attractive prices; net executable economics; useful ideal-band frequency; performance across independent market regimes; source-qualified persistence; and actual protected lifecycle management. New source-qualified data and a fresh preregistered prospective sample are needed before any successor could be promoted. Infrastructure candidates and their unresolved live admission/clock gates remain separate.

**Scope confirmation.** No deployment, Railway action, live cohort access, production edits, orders, threshold changes, model changes, freshness changes or cadence changes occurred. Only offline research files were created. Both frozen candidate Git heads and trees remained unchanged and clean.

<!-- PAGE -->
## Frozen evidence and accounting

The authoritative PDF and evidence ZIP were retrieved and the snapshot inside the ZIP was byte-compared with the frozen local input. The original settlement scorer was reused unchanged. Snapshot SHA-256:

`bb7a4ff9be99115aa2085ff02af8663225a7dc91bcdc58f6c8c1003887cea227`

| Accounting category | Count | Treatment |
| --- | --- | --- |
| All JSONL rows / malformed | 33,623 / 0 | Original bytes retained |
| Rows at or after boundary | 32,900 | Timestamp view only |
| Official complete settlements | 249: 134 UP / 115 DOWN | Contract open >= 2026-09-26T04:00:00Z |
| Settled with ordinary observations | 202; 32,401 rows | Numerical research scoreable; source qualification unavailable |
| Settled, closeout-only | 47 | Evidence-incomplete; never PASS or loss |
| Expired, outcome unavailable | 1 | Excluded from accuracy; retained in accounting |
| Not yet settled at snapshot end | 1 | Excluded from accuracy; retained in accounting |
| Missing expired 15-minute slots | 28 | No journal evidence; cause unavailable |
| Certified actionable entries | UNAVAILABLE | No reconstructed native BUY/fill |
| True strategy PASS classification | UNAVAILABLE | Zero numeric intersections is not complete live PASS evidence |

The older 250-settlement timestamp view includes the contract that closed exactly at the boundary. It is excluded from the official 249-contract analysis. The 278 expected expired slots reconcile as 249 complete, one expired without closeout and 28 absent. The active slot is additional. Missing-slot accounting reuses the audited 15-minute schedule assumption, not a new exchange query.

Within settled decision histories, there are 239 adjacent observation gaps above 10 seconds across 126 contracts; the longest is 78.652050s. These are missing observation intervals, not attributed strategy failures or proven downtime. Eight rows show explicit BRTI WAIT/out-of-range source-age evidence. History resets across gaps/WAIT. The 47 settlement-only contracts and missing slots never contribute false losses or PASS observations.

<!-- PAGE -->
## Causal event and feature construction

Each policy takes the first observed causal qualification in a contract, at most once. The immutable research origin records policy hash, contract, side, exact timestamp, original ASK and original input line. Subsequent rows cannot revise it. A policy can trigger after a genuine change even when an earlier point failed; it cannot choose among past origins using settlement, future prices or future probability. Policy alternatives overlap and must not be summed into a combined strategy.

Episode exports are diagnostics, not additional trades. First affordable events and first edge>=5 events with a 30-second history are the winner/loser sample units. Long contracts do not receive extra statistical weight.

For 15/30/60-second changes, the anchor is the last observation at or before timestamp minus the requested horizon, no more than 10 seconds older than that anchor. Every intervening adjacent gap must be <=10 seconds, with the same contract and target and no known WAIT. Exact microsecond timestamps are preserved. No interpolation or invented observations are used.

All deltas hold the candidate's side fixed. If an earlier row preferred the other side, its complementary probability is used from the recorded binary model definition, and its corresponding same-side ASK/BID is read directly. Stored preferred-side deltas are not used across flips. Stability/persistence is elapsed time between observed compatible states, not evaluation-count hits and not proof of continuous unobserved market stability.

| Feature | Recorded source / transformation | Qualification limitation |
| --- | --- | --- |
| Fair, preferred side, raw edge | early.preferred_fair / preferred_side; fair minus ASK | Observational fair; no per-row protected acceptance witness |
| ASK, BID, spread, changes | Original up/down ASK and BID; held-side past differences | Quote source/receipt clocks unavailable |
| BTC gap and change | early.btc_price / btc_gap; same target and prior rows | Underlying spot freshness not certified |
| Persistence, flips, stability | Exact elapsed journal times within intact observed segments | No inferred events between samples |
| 60s sampled range and gap/range | Past recorded BTC max minus min; zero range => unavailable | Not native vol5/range5; not seconds bars |
| BRTI agreement/readiness | Recorded side/ready; source timestamp when explicit | No receipt or clock certificate; not an alpha gate |
| Protected FINAL, Flip Risk, 5M/3M | Unavailable in authoritative ordinary journal | No reconstructed confirmation/protection |
| Native V2 clocks/decision IDs | Unavailable | Never invented from age or receipt telemetry |

Thirty-second features exist at 667/788 affordable-edge observations across 117 contracts; 60-second sampled range exists at 585/788 across 104. Missing histories remain unavailable, not zero-valued features. Full per-feature counts are in feature_availability.csv.

Only currently recorded evidence is used for entry selection. Future probabilities, BID paths and settlement are isolated to outcome scoring. Removing or poisoning future rows and changing outcome labels cannot move an earlier origin; the tests verify this.

<!-- PAGE -->
## Winner-versus-loser evidence

In the development sample, first affordable events won 18/57. Median recorded fair was 52.95% for winners versus 53.52% for losers; median raw edge was 5.61 versus 8.23 points. A larger raw edge was not a trustworthy value signal in this cheap-price regime.

For first edge>=5 events with at least a 30-second history, development contained 15 winners and 31 losers. Winner/loser median preferred-side stability was 34.97/15.03 seconds. Median 30-second ASK change was -6/-1 cents. For the smaller 60-second-history subset (10 winners, 18 losers), sampled BTC range medians were $18.58/$34.60 and gap/range medians 0.225/0.047. These were hypotheses for the frozen family, not established effects.

| Feature | Dev rank AUC | Validation | Final segment |
| --- | --- | --- | --- |
| Preferred-side stability, elapsed | 0.647 | 0.326 | 0.604 |
| Same-side ASK change, 30s | 0.363 | 0.577 | 0.497 |
| Same-side edge change, 30s | 0.596 | 0.810 | 0.330 |
| Past sampled BTC range, 60s | 0.328 | 0.673 | 0.656 |
| Signed gap / sampled range, 60s | 0.672 | 0.469 | 0.225 |

Rank AUC here is the chance that a randomly selected winner has a larger feature value than a loser, with half-credit for ties. 0.5 is no rank separation; below 0.5 favors smaller values. It is descriptive and not a fitted prediction model. The comparable 30-second event samples are 46 development, 34 validation and 37 final; 60-second availability is smaller still.

The direction reversals matter: lower sampled range appeared favorable in development but higher sampled range ranked winners later; the gap/range rank fell from 0.672 to 0.469 to 0.225. Edge growth looked strong in validation (0.810) but reversed in the final segment (0.330). No sign was flipped after seeing these results.

At first affordable events across all partitions, the 50-60% fair bucket won 42/111 (37.8%), the 60-75% bucket 18/42 (42.9%), and the >=75% bucket 0/1. The last bucket is far too small for inference. These are conditional calibration observations, not a global model calibration verdict.

There is no demonstrated side-specific rescue. The cheap-edge control was 24/56 UP (42.9%) and 28/74 DOWN (37.8%), with broad overlapping intervals. No side-exclusive rule was selected. T7 was heavily DOWN-weighted (41/47), so its small UP subset cannot support a separate conclusion.

<!-- PAGE -->
## Gate interactions and entry timing

| Current protected condition | Finding | Research conclusion |
| --- | --- | --- |
| ASK <=45c | Preserves attractive economics; not directional evidence | Keep economics explicit; cheap alone fails |
| Fair >=75% | Only 11 <=45c observations across 5 contracts at any time | Rare and unsupported as a cheap-price reliability filter |
| Edge >=8 points | Fair >=75% and ASK <=45c already imply >=30 points | Mathematically redundant within the full intersection |
| Absolute BTC gap >=$25 | No <=45c plus $25-gap rows in the 2-10m window | Empirical affordability conflict; useful predictive effect unproven |
| 2-10 minutes remaining | Excludes 376 affordable-edge rows in first five minutes | Coverage restriction; no reliable early-window rescue demonstrated |
| All protected numeric gates | 0 rows / 0 contracts | No tuning or manufactured signals |

At ASK <=50c, only two price/gap observations survive inside 2-10 minutes, and the larger fair is 70.9248%, below 75%. Thus raising only the cap to 50c still cannot restore the protected intersection. This is an observed interaction, not a claim that fair, price and gap are logically incompatible in every market.

For timing diagnostics, each band uses its first qualifying cheap-edge event per contract. A contract can appear in more than one band's descriptive table; bands must not be summed or retrospectively selected as trades.

| Minutes remaining | First cheap-edge event | Wilson 95% | Mean ASK (c) |
| --- | --- | --- | --- |
| >10-15 | 39/97 (40.2%) | 31.0-50.2% | 47.7 |
| >5-10 | 21/55 (38.2%) | 26.5-51.4% | 47.3 |
| 2-5 | 9/33 (27.3%) | 15.1-44.2% | 43.3 |
| >0-2 | 7/18 (38.9%) | 20.3-61.4% | 30.5 |

The first-five-minute result is not superior reliability hidden by the current window. Later bands also fail. Among all recorded preferred-side observations, only 11 contracts ever reached 25-35c (28 rows). The first such observation won 3/11 (27.3%; Wilson 9.7-56.6%): development 2/7, validation 1/3, final 0/1. This fixed-price-band diagnostic was computed after family selection and is not a new candidate.

Some tiny late subsets look better by chance: T7's final-two-minute diagnostic is 3/5 (60%; Wilson 23.1-88.2%), far below the required sample size and not evidence for 85% reliability. No late threshold was selected from these outcomes.

<!-- PAGE -->
## Frozen candidate family

All T-rules require a numerically available preferred-side ASK <=50c and raw edge >=5 points. Timestamps can span the full observed contract. Known WAIT/out-of-range explicit BRTI age blocks numerical availability; missing full provenance still prevents action qualification. N0 preserves the original raw negative control definition exactly.

| ID | Additional rule / role |
| --- | --- |
| C0 | Unchanged protected numeric gates: ASK45, fair75, edge8, 2-10m, absolute gap25. |
| N0 | First ASK<=50c and edge>=5 points. Preserved negative control, never a candidate. |
| B0 | First affordable preferred-side observation; no edge floor. Benchmark. |
| B1 | Base cheap-edge setup plus fair>=65%. Static benchmark. |
| T1 | Preferred side stable for at least 30 elapsed seconds. |
| T2 | Cheap-edge setup persists for at least 15 elapsed seconds. |
| T3 | Side stable 30s; ASK falls >=3c over 30s; fair falls <=2 points; signed gap>0. |
| T4 | Side stable 30s; edge grows >=2 points over 30s; fair falls <=2 points. |
| T5 | ASK rises >=1c, held-side BTC gap improves >=$5 and fair does not fall, over 30s. |
| T6 | Held-side gap now positive, touched zero/below in past 30s, improves >=$5. |
| T7 | Side stable 30s; signed BTC gap / past 60s sampled BTC range >=0.20. |
| T8 | Side stable 30s; sampled BTC range over past 60s <=$25; signed gap>0. |

These twelve rules were frozen as a limited interpretable family after development description, not a brute-force grid. Their thresholds are offline research contrasts only; no protected strategy parameter was edited. Full conditions are in FAMILY_FROZEN.json.

Before validation, the protocol selected T1 as the only research rule meeting the >=30-event development sample floor. Its 11/33 was nowhere near 85%. No rule advanced. T7's 9/24 was the diagnostic reference under a separate >=20-event rule; it also failed reliability and was never promoted.

Protocol SHA-256: `df1d3048bd832693811ad9e0b73e8492a2f179f8cf808dc6e2dd4f621c94b587`

Family SHA-256: `08def5f3b1af83d5952c4f2b04af4cba11f6e9fe0acc6b6cb57e068623dc89aa`

<!-- PAGE -->
## Candidate comparison: reliability and coverage

| Rule | Correct / events | Wilson 95% | Coverage / 202 | Coverage / 249 |
| --- | --- | --- | --- | --- |
| C0 Protected | 0 signals | - | 0.0% | 0.0% |
| N0 Cheap edge | 52/130 (40.0%) | 32.0-48.6% | 64.4% | 52.2% |
| B0 Any cheap | 60/154 (39.0%) | 31.6-46.8% | 76.2% | 61.8% |
| B1 Fair 65% | 17/44 (38.6%) | 25.7-53.4% | 21.8% | 17.7% |
| T1 Side stability | 28/84 (33.3%) | 24.2-43.9% | 41.6% | 33.7% |
| T2 Setup persistence | 9/26 (34.6%) | 19.4-53.8% | 12.9% | 10.4% |
| T3 Pullback | 12/42 (28.6%) | 17.2-43.6% | 20.8% | 16.9% |
| T4 Edge growth | 16/50 (32.0%) | 20.8-45.8% | 24.8% | 20.1% |
| T5 Convergence | 21/60 (35.0%) | 24.2-47.6% | 29.7% | 24.1% |
| T6 Gap reclaim | 22/65 (33.8%) | 23.5-46.0% | 32.2% | 26.1% |
| T7 Sampled context | 15/47 (31.9%) | 20.4-46.2% | 23.3% | 18.9% |
| T8 Low chop | 9/34 (26.5%) | 14.6-43.1% | 16.8% | 13.7% |

Every nonzero event count is also the unique-contract count for that rule. Incorrect counts are events minus correct, explicitly retained in the CSV. Coverage includes all 202 observed contracts, not only affordable ones; a second denominator retains all 249 settlements. Operationally incomplete contracts are visible but are not labeled losses or strategy PASS.

![Accuracy and Wilson intervals](candidate_accuracy.png)

All eight research rules fall far below the 85% target. The pooled chart combines already-viewed development and later data for description only. It is not independent validation, and the rules overlap in contracts. No rule is recommended simply because it has the largest number in this table.

<!-- PAGE -->
## Chronological development, validation and final comparison


Official contracts were ordered by native close and the previous 125/62/62 chronological split was frozen before this mission's outcome-guided family construction. Ordinary-evidence counts are 78/62/62. Development ends September 27 at 18:30 UTC; validation ends September 28 at 10:00 UTC; the final segment ends September 29 at 01:30 UTC.

The 723 preboundary rows contain zero ordinary decision histories. Older repository CSVs were inventoried but not pooled: their historical labels/features are not bound to compatible corrected lineage and evidence identities. Thus no compatible pre-prospective trajectory-development set was available in the authoritative input.

The protocol was fixed before development description; the 12-rule family and selection were frozen before validation/final scoring in this run. Development advancement required at least 30 events, >=85% accuracy and Wilson lower bound >=70%. Validation required at least 20, >=85% and lower bound >=70%; final comparison at least 20 and >=85%, with combined later lower bound >=75% for a merely promising research candidate. None reached the first gate.

Wilson intervals are nominal binomial intervals over unique contracts, not row-level intervals. Serial market dependence and model selection can make these intervals optimistic. They do not establish an independent prospective population rate. No multiple-testing victory or newly untouched holdout is claimed.


| Rule | Development | Validation | Final segment |
| --- | --- | --- | --- |
| C0 Protected | 0 signals | 0 signals | 0 signals |
| N0 Cheap edge | 16/50 (32.0%) | 18/38 (47.4%) | 18/42 (42.9%) |
| B0 Any cheap | 18/57 (31.6%) | 23/52 (44.2%) | 19/45 (42.2%) |
| B1 Fair 65% | 6/20 (30.0%) | 3/9 (33.3%) | 8/15 (53.3%) |
| T1 Side stability | 11/33 (33.3%) | 5/22 (22.7%) | 12/29 (41.4%) |
| T2 Setup persistence | 7/17 (41.2%) | 2/7 (28.6%) | 0/2 (0.0%) |
| T3 Pullback | 7/17 (41.2%) | 2/13 (15.4%) | 3/12 (25.0%) |
| T4 Edge growth | 8/19 (42.1%) | 3/16 (18.8%) | 5/15 (33.3%) |
| T5 Convergence | 5/23 (21.7%) | 9/20 (45.0%) | 7/17 (41.2%) |
| T6 Gap reclaim | 5/23 (21.7%) | 9/20 (45.0%) | 8/22 (36.4%) |
| T7 Sampled context | 9/24 (37.5%) | 3/13 (23.1%) | 3/10 (30.0%) |
| T8 Low chop | 7/19 (36.8%) | 2/10 (20.0%) | 0/5 (0.0%) |

The negative control reproduces 16/50, 18/38 and 18/42, totaling 52/130. T7 falls from 37.5% development to 23.1% validation and 30.0% final. T1 falls to 22.7% validation before recovering only to 41.4% final. The 53.3% final result for B1 is 8/15, below both reliability and sample-size requirements and preceded by 30.0% and 33.3%.

No validation rule was substituted for the failed development choice. No final-tail result was used to change a threshold, select a side, choose a timing band or select an earlier event. All chronological tables and the frozen selection artifact remain in the package.

No statistical story here supports a 90%+ claim. The sample comprises a short, already-inspected market period with serially related contracts and nonuniform evidence coverage. Even a much higher small-sample score would not overcome those limits.

<!-- PAGE -->
## Entry economics and timing

| Rule | ASK mean / median (c) | 25-35c n (%) | Minutes left mean / median | Gross arithmetic / event (c) |
| --- | --- | --- | --- | --- |
| C0 Protected | - / - | 0 (-) | - / - | - |
| N0 Cheap edge | 46.6 / 48.0 | 1 (0.8%) | 11.60 / 12.77 | -6.63 |
| B0 Any cheap | 47.6 / 49.0 | 1 (0.6%) | 12.17 / 13.73 | -8.64 |
| B1 Fair 65% | 46.5 / 49.0 | 1 (2.3%) | 10.64 / 12.03 | -7.89 |
| T1 Side stability | 47.2 / 48.0 | 2 (2.4%) | 10.07 / 11.29 | -13.86 |
| T2 Setup persistence | 44.4 / 47.0 | 1 (3.8%) | 10.85 / 11.73 | -9.79 |
| T3 Pullback | 45.9 / 47.0 | 3 (7.1%) | 10.48 / 11.42 | -17.29 |
| T4 Edge growth | 46.5 / 47.5 | 3 (6.0%) | 10.95 / 11.68 | -14.54 |
| T5 Convergence | 47.0 / 48.0 | 0 (0.0%) | 9.46 / 10.16 | -12.05 |
| T6 Gap reclaim | 44.8 / 48.0 | 1 (1.5%) | 8.94 / 9.84 | -10.91 |
| T7 Sampled context | 47.0 / 48.0 | 1 (2.1%) | 9.88 / 10.62 | -15.06 |
| T8 Low chop | 46.3 / 46.5 | 1 (2.9%) | 9.93 / 10.35 | -19.85 |

All original-family events have ASK <=50c (100%). The immutable origin is the first recorded qualification, not an outcome-selected minimum ASK. Exact first timestamps, side and price are in candidate_events_NOT_TRADES.csv and contract_event_audit.csv. Rounded report values never feed signal selection.

Gross settlement arithmetic is **100 x (direction correct - original ASK)** cents per hypothetical one-contract unit. It ignores fees, spread execution uncertainty, slippage and manual action. It is not realized P&L or evidence of a fill. Every nonzero rule has negative pooled gross arithmetic; T7 is -15.06c/event and the negative control -6.63c/event before costs.

| Rule | <25c | 25-35c | >35-45c | >45-50c |
| --- | --- | --- | --- | --- |
| N0 Cheap edge | 2 | 1 | 20 | 107 |
| B0 Any cheap | 1 | 1 | 16 | 136 |
| B1 Fair 65% | 1 | 1 | 6 | 36 |
| T1 Side stability | 0 | 2 | 11 | 71 |
| T2 Setup persistence | 1 | 1 | 7 | 17 |
| T3 Pullback | 0 | 3 | 8 | 31 |
| T4 Edge growth | 0 | 3 | 7 | 40 |
| T5 Convergence | 0 | 0 | 16 | 44 |
| T6 Gap reclaim | 3 | 1 | 16 | 45 |
| T7 Sampled context | 0 | 1 | 5 | 41 |
| T8 Low chop | 0 | 1 | 6 | 27 |

The ideal band remains sparse. T7's sole ideal-band proposal lost; its other five proposals at >35-45c also lost, while 15/41 at >45-50c won. This is a failure description, not permission to optimize a new price cutoff on those labels.

<!-- PAGE -->
## Ablations and parameter neighborhood

T7 was frozen as the diagnostic reference before later partitions were opened. These are one-factor changes from that reference, not a second candidate search. The base setup, contract-level first-event rule and source-availability handling remain fixed except for the explicitly labeled ASK/edge diagnostic changes.

| T7 one-change diagnostic | Correct / events | Wilson 95% | Validation / final correct-events |
| --- | --- | --- | --- |
| Remove side stability | 19/60 (31.7%) | 21.3-44.2% | 5/17 / 3/13 |
| Stability 15s | 16/50 (32.0%) | 20.8-45.8% | 3/13 / 3/11 |
| Stability 45s | 13/43 (30.2%) | 18.6-45.1% | 3/13 / 2/8 |
| Stability 60s | 11/40 (27.5%) | 16.1-42.8% | 2/12 / 2/8 |
| Remove gap/range | 28/84 (33.3%) | 24.2-43.9% | 5/22 / 12/29 |
| Gap/range 0.10 | 18/55 (32.7%) | 21.8-45.9% | 4/16 / 4/15 |
| Gap/range 0.30 | 13/42 (31.0%) | 19.1-46.0% | 3/12 / 3/9 |
| Gap/range 0.40 | 9/36 (25.0%) | 13.8-41.1% | 2/11 / 1/7 |
| ASK cap 48c | 12/38 (31.6%) | 19.1-47.5% | 3/12 / 1/6 |
| ASK cap 52c (outside objective) | 29/65 (44.6%) | 33.2-56.7% | 8/21 / 8/18 |
| Edge floor 3 points | 16/51 (31.4%) | 20.3-45.0% | 3/13 / 4/11 |
| Edge floor 7 points | 13/40 (32.5%) | 20.1-48.0% | 3/13 / 3/7 |

Removing gap/range returns the T1 stability rule; it does not reveal reliable performance. Removing stability also fails. Nearby stability and context thresholds remain poor. The 52c version has 29/65 (44.6%) and includes economically out-of-scope entries; it cannot qualify and was not adopted.

Because nothing passed development, robustness does not rescue or select a survivor. Its purpose is to test whether failure was confined to one arbitrary threshold. It was not. All variant results, including development/validation/final sample sizes and uncertainty, are retained in parameter_robustness_NO_RESELECTION.csv.

## Failure interpretation

The data do not support a simple missing static threshold. Stable model preference can persist on the eventual wrong side. Larger apparent edge can be caused by the market moving against the model. A large normalized gap can arise from a tiny sampled denominator. Reclaim/convergence conditions can identify short-lived reversals rather than correct settlement direction. These mechanisms are consistent with the results; the journal cannot establish underlying microstructure causes or certify spot staleness.

<!-- PAGE -->
## Losing-contract audit

T7 has 32 losses across 47 unique proposed origins. All 32 later show both model-side disagreement and a sampled BTC gap against the original side. Eight have entry absolute gap <$5, but losses are widespread: 22/31 entries in the positive $5-25 signed-gap bucket lose, as do 2/3 at >=$25. The high-gap subset is too small to estimate a stable rate.

These are the first four T7 losses chronologically, not hand-picked extremes. The full 32-row T7 loss audit and all losing events for every family member are supplied.

| Contract suffix | Entry UTC (exact) | Side / ASK | Fair | Signed gap ($) |
| --- | --- | --- | --- | --- |
| 26SEP261345-45 | 2026-09-26T17:33:32.235469Z | DOWN / 50.0c | 55.2% | 11.37 |
| 26SEP261415-15 | 2026-09-26T18:03:20.288655Z | UP / 50.0c | 60.0% | 7.06 |
| 26SEP261530-30 | 2026-09-26T19:22:11.418632Z | DOWN / 49.0c | 54.2% | 4.39 |
| 26SEP261600-00 | 2026-09-26T19:46:14.377944Z | DOWN / 46.0c | 53.4% | 3.34 |

For the first two examples, prior sampled side stability was 134.987545s and 60.012029s, yet both lost. Their gap/range ratios were 4.53 and 7.20. In the fourth example, the ratio was about 334 because the past sampled BTC range was only about one cent. This illustrates a fragile denominator, not confirmed fresh low-volatility context. The recorded data cannot distinguish genuinely calm spot from a stale/flat source without the missing source provenance.

The negative control loses 78/130. All 78 losers later disagree with the original model side, but so do 40/52 winners. T7 likewise has disagreement in 7/15 winners. A hindsight filter requiring future agreement would erase legitimate earlier signals and would leak future evidence. No such filter is used.

Prior side-flip, entry-gap, price-band, time-band and BRTI logged-agreement clusters are exported for every policy. BRTI logged agreement is diagnostic only and never promoted into a source-qualified feature. Small side/time/price cells are not treated as independent discoveries.

## Executable-chronology limits

Original same-side ASK is compared only with strictly later, recorded same-side BID, including after model-side flips. A fixed 180-second descriptive horizon and symmetric +/-10c marks expose ordering. The first observed stop takes precedence over a later target; exact decimal price arithmetic handles equality. These marks are diagnostic and do not add a strategy target, stop, SCALP or EXIT rule.

| Rule | Observed target first | Observed stop first | Neither | 170s sampled path without known gap |
| --- | --- | --- | --- | --- |
| N0 Cheap edge | 60 | 61 | 9 | 104 |
| T1 Side stability | 44 | 38 | 2 | 57 |
| T7 Sampled context | 23 | 23 | 1 | 32 |

The 170s column only says the sampled path reaches at least 170 seconds without a known >10s gap or explicit WAIT; it does not certify continuous market availability. For T7, the mean sampled maximum/minimum BID-minus-original-ASK over the horizon are +16.39c/-14.42c. Picking the maximum would be look-ahead. With no quote receipt/source clocks and unobserved intervals, true executable ordering, fees, fill probability, profit protection and realized results remain UNAVAILABLE. These 23 target-first and 23 stop-first paths are not scalp trades.

<!-- PAGE -->
## Lifecycle research and provenance limits

No family member survived reliability selection. Independently, the cohort's ordinary FINAL fields are the previously audited startup PASS/NONE variables, not protected continuous FINAL. No actual accepted EARLY-origin identity or FINAL-to-origin linkage is recorded. Thus a faithful manager replay cannot be supplied by replacing its inputs with raw probability trajectories.

For all research proposals, actual BUY/HOLD/PROTECT classification is **UNAVAILABLE**, not zero genuine HOLD or PROTECT occurrences. The exported zero protected-FINAL counts mean no captured protected-FINAL evidence; they do not prove the running protection state was inactive. Research proposals preserve immutable side/time/ASK, but are not bot signals, positions or fills.

Descriptively, T7 has later model disagreement in 39/47 contracts and ever reaches 90% probability on its original side in only 1/47. T1 reaches 90% on its original side in 3/84; the negative control in 9/130. Later preferred-side accuracy cannot automatically confirm an earlier origin because the preferred side can change. These future measurements never enter acceptance.

Locked semantics remain intact: EARLY alone owns BUY; FINAL manages an existing origin; disagreement alone cannot force EXIT; WAIT/UNAVAILABLE preserves the origin and suspends guidance; PROTECT is not silently converted into EXIT; no validated executable EXIT rule exists; SCALP remains independent. No lifecycle or admission implementation was edited.

| Evidence item | Research use | Live qualification |
| --- | --- | --- |
| Exact journal row time | Preserved; prefix ordering and elapsed differences | Not relabeled source/receipt/publication time |
| Explicit BRTI source timestamp | Known >5s/future timestamp excluded from numeric availability | Receipt/clock bound still unavailable |
| brti_age_seconds | Telemetry only; not a synthetic clock | Cannot certify original source time |
| Contract and target | Original identity plus audited schedule for grouping | Not an invented official-window witness |
| Quote timing and protected publication | Missing in native cohort snapshot | UNAVAILABLE |
| Native V2 witness, runtime/build identity | Missing at required historical seam | UNAVAILABLE |
| Research origin hash | Offline deterministic event identifier | Not a native shared decision ID |
| Manual fill / actual order | Absent | UNAVAILABLE; no orders |

The frozen infrastructure references remain dcc44cc858eb745953c48860bbe1e2e847860326 and b02577151b392c91e93d9f373e130ebfea89a594. Qualified native source reference is abe212b513827c8cec28a2f64e0161e79296bd82. Repository identity verifies preservation of these artifacts; it does not retrospectively bind every cohort row to a build. Future research promotion must still clear live artifact-acquisition and clock-admission qualification.

<!-- PAGE -->
## What would change the decision?

Do not loosen the current protected gates to manufacture entries. The observed failure is substantive even before full provenance requirements: the attractive-price first events and the causal trajectory family do not approach 85%. No replacement threshold set is proposed.

For a later research mission, collect a **new**, fixed prospective period from an already-approved protected publication path after its independent artifact access and clock admission qualify. Preserve complete protected EARLY/FINAL snapshots, executable same-side quote source and receipt times, native/publication identity where it really exists, explicit BRTI source and qualification evidence, and operational WAIT/gaps. Preserve authentic context fields only when actually emitted; do not fabricate TradingView/seconds/native range histories.

Keep first-five-minute coverage and full-contract trajectories. In a separate development corpus, determine whether recorded context identifies persistent model/market miscalibration, source-stale flat series or transitory reversals. Compare any new discriminator on development only, freeze one event policy and its evidence requirements, and then evaluate a newly unviewed chronological sample. No rule in this report is nominated for that validation.

Require meaningful unique-contract counts and independent market regimes. As a scale illustration, 180 correct out of 200 independent signals gives a two-sided Wilson lower bound of about 85.06%; 90% on a much smaller sample does not establish true >=85% reliability. Correlation, selection and operational omissions require additional discipline; 200 is not a universal sufficiency guarantee. Report coverage over all scheduled eligible contracts alongside scoreable accuracy, including WAIT, gaps and settlement-only observations.

## Verification and reproducibility

**26/26 research integrity tests and 36/36 unchanged manager controls passed.** The research tests cover snapshot/official accounting, the exact 52/130 negative control, zero protected intersection, prefix invariance, future-poison resistance, label-independent event timing, held-side deltas, elapsed persistence, duplicate timestamp rejection, gap/WAIT resets, BRTI clock handling, exact timestamp boundaries, rollover, one origin per contract, causal anchors, split/family hashes, incomplete-evidence accounting, later same-side BID chronology, stop-first equality and no invented FINAL/fills.

An independent temporary-directory rerun regenerated the analysis and reran both test suites. **31 artifacts matched exactly** (gzip compared on decompressed content), including policy results, contract events, chronology, robustness, diagnostics and frozen selection. Reproduction logs and per-file hashes are supplied.

Two initial verification failures are retained: a copied manager test initially lacked its unchanged fixture module; a rollover test fixture accidentally reused the same contract ID. The dependency and test fixture were corrected, with no strategy or event-policy changes. Analysis review also made paths portable, explicitly rejected duplicate timestamps, separated settled from unlabelled setup counts, clarified a sampled-path label and used Decimal price differences for descriptive threshold equality. Candidate comparisons remained byte-identical before and after these integrity edits.

The original audit PDF and ZIP, frozen protocol/family/selection, raw derived features without outcomes, separate outcome labels, every event and rejected-contract audit, chronological results, robustness tables, failure clusters, observed BID paths, test logs and reproduction script are included. CSV metrics are unrounded; display rounding never changes order or branch decisions.

**Final decision: C - CURRENT FEATURE SET CANNOT SUPPORT THE TARGET RELIABLY.** No candidate advances. No production qualification, deployment, execution, model change, gate change, five-second BRTI-limit change or native-cadence change is claimed or performed.
