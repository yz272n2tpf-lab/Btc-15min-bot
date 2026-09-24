# Continuation checkpoint — September 24, 2026

Resume from this checkpoint and `JOINT_LADDER_DIAGNOSIS_20260924.md`. Do not repeat the audit, the 822-configuration search, or completed PR32 release tests. SIGNAL ONLY / NO ORDERS.

## Current production and evidence

- Main: PR32 merge `1730ceff180394fbd2ebae7a5fddc4acd1e76194`, Railway deployment `454f53ad-b269-4133-b0f5-60098978db71`, SUCCESS. Startup September 24 at 12:54:43.752856839 UTC confirms NO STARTUP FIT.
- Frozen model weights: `95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6`. Artifact: `1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816`. Restart closes the old runtime identity even though these hashes are unchanged.
- Rollback: main commit `d54321927626529612b7309576d7dc90b84fe224`, deployment `0b2ef3ff-1499-432a-ac70-52b997bb2e26`. Existing archives preserved. No credential, owner, V8.1, collector, strategy threshold or weight changes were made in this correction.
- Clean collector: run `clean-source-v2-1s-20260923`, commit `e98576f23e247349b90717aea3a3ad832d409354`, deployment `df8385ff-46a2-4dfb-af0a-07c25e5382aa`. Never combine the old five-second run. Persistent mounts: main 10 GB, clean 50 GB.
- Verified raw export prefix ends at byte **410496309**, SHA256 `decabbc24c8ec0fedcd7b4eb1f0b538c38d07249d977bebd0d20e8d7b4726bde`. Resume bounded export from this offset only after verifying run identity and unchanged prefix; validate every range SHA256/offset and every gzip CRC. Export URL remains the clean collector's `/research/common-export` endpoint. The immutable analysis inputs and official-label responses are preserved in this evidence branch; the full raw prefix remains in the existing scratch evidence and collector retention, not committed into git.
- Exact model feature vectors now append to `/data/kalshi_fair_input_frames_v1.jsonl`. Preserve its separate BTC source, receipt and decision timestamps. Do not reconstruct missing pre-correction vectors as if they were observed.

## Completed diagnosis

The 00:15–12:15 UTC old-runtime slice has 43,194 observations per service, maximum sampling gap 1.203 seconds, zero observed HTTP failures. This is sampled coverage, not continuous availability. Twenty-six tuning contracts and thirteen internal-validation contracts were kept separate. Eight missing-official validation slots and one purged calendar slot were retained in the common universe.

EARLY is suppressed chiefly by the favorable-price gate and the model's confidence limits. FINAL's 90% threshold is near the calibrated model's maximum; observed calls were sparse, expensive and sometimes late. Core SCALP adds coverage but shows substantial adverse excursions. V8.1's impulse, route, persistence and near-static quote conditions rarely coincide. No validated strategy improvement emerged from 822 tuning configurations and the separately evaluated locked candidates. Do not promote a runner-up after viewing validation results.

PR32 corrects a demonstrated timing defect: the model excluded the newest BTC tick because its cutoff preceded the HTTP receipt while other gates used that tick. Post-release, 22 distinct producer frames showed median mismatch $0 and maximum rounding residual $1.42e-14. Hosted CI and 208 runtime tests, 29 audit tests, three static gates passed; diagnosis tests passed 40/40.

## Frozen next evaluation

Manifest: `COHORT_CAUSAL_CUTOFF_20260924.json`; canonical SHA256 `fc61b525e2c50e0d6023a2ddb9be8d1bfceb9ad930564236e34a79c66f3681a7`.

| Partition | Fixed UTC window |
|---|---|
| Corrected-runtime tuning | September 24, 13:15–17:00 |
| Purge, retained in calendar | September 24, 17:00–17:15 |
| Internal development validation | September 24, 17:15–21:15 |
| Original reserved validation | September 24, 21:15–September 25, 21:15 |
| Untouched final holdout | September 25, 21:15–October 9, 21:15 |

Keep 12:45–13:00 as mixed/late join and 13:00–13:15 as transition in the parent calendar. Do not slide windows, pool changed runtime identities, tune on validation, inspect holdout outcomes early, or claim the uncertified 263/278 scoreboard as acceptance.

Next monitor the corrected cohort without changing production: verify exact ticker, official target/window, timestamped contiguous book, true BRTI age ≤5 seconds, V8.1 publication ≤3.5 seconds, fail-closed behavior, source recovery, retention and NO ORDERS. Record first readiness events separately. At 13:00, handoff was +0.675s, true target readiness +15.911s, contiguous quotes +26.135s and first logged parity PASS +32.123s. This is only a partial transition contract. Four complete corrected cohort contracts could first close at 14:15 UTC; elapsed clock time alone is not acceptance.

After tuning closes, quantify corrected input parity, each gate, shared failures, unique lane contribution, qualified publication availability, price/timing, missing intervals and executable ask-to-bid paths. Freeze any new shortlist before opening its validation outcomes. Obtain the exact model-input journal through an authorized read-only export before attempting causal feature/weight attribution; preserve the existing journal if export is unavailable. Do not fit a replacement on approximate old vectors.

## Remaining acceptance scorecard

| Area | Current result / blocker |
|---|---|
| Infrastructure / Kalshi / fixed target | New main startup and sampled parity PASS; broader acceptance remains open. |
| BRTI | Old-runtime slice: 43,180 PRIMARY_OK and 14 error samples; zero 429s, recovered historical errors; median source age 1.906s, p95 3.074s. No continuous-availability claim. |
| Rollover / downstream readiness | First corrected transition boundary measured separately; ≥4 complete corrected contracts pending. |
| Model / three ladders | Input-timing correction deployed; no threshold/weight promotion; fresh contribution and calibration validation pending. |
| EARLY | Internal development validation: 1/13 official, 1/21 scheduled, 1/1 correct, 33c, 7.229 minutes left; insufficient sample. |
| FINAL | Internal development validation: 2/13 official, 2/21 scheduled, 2/2 correct, median 99.8c and 1.324 minutes left; does not establish the product goal. |
| Core SCALP | Internal development validation: 7/13 official, 7/21 scheduled, 6/7 eventual-direction wins; median 68c; sampled mean MFE +19.96c, MAE −20.29c. Exits/profits not certified. |
| V8.1 / exits / reversal | Zero actual qualified entries in the analyzed slice. Hypothetical exit comparisons remain research; prospective connected protection and both-direction acceptance pending. |
| Restart / logging / retention | Startup reused exact frozen model without fit; append-only features added and existing archives preserved. Long-run recovery/retention and effective restart-policy visibility limits remain. |
| Dead / temporary dependencies | No service restarted or dependency changed except the authorized main release. Prior raw-reference visibility and historical research-crash questions remain; no new ZERO-dependency certification. |
| Signal-only / NO ORDERS | PASS in deployed code, startup and observed runtime evidence. |

Fresh corrected-runtime evidence is the next dependency for defensible performance selection. It does not erase the remaining engineering and acceptance work. Stop active waiting; Chat can monitor the fixed windows and resume evaluation when the evidence exists. Do not create a new automation or alter another task.

## Structural completion and clarified ladder roles — September 24, 14:15 UTC checkpoint

This section extends the existing checkpoint. The original replay, manifests, 822-configuration search and release tests were reused, not recreated. EARLY is the value-entry ladder; SCALP is the bid-path movement ladder in either direction; FINAL is primarily high-accuracy confirmation and EARLY-position protection. A high FINAL quote is not itself a failure. Earlier/cheaper confirmation remains a secondary opportunity, subordinate to reliability, calibration and useful coverage.

The new experiments are in `structural_batch.py`, `structural_lead_lag.py`, `structural_path_alignment.py`, `structural_interactions.py`, `structural_value_head.py` and `structural_position_protection.py`. Results use the matching `STRUCTURAL_*.json` names. No production source, model weight, threshold, credential or service was changed. The old-runtime challenge was already opened: these are development findings, not untouched validation. The registered corrected-runtime and final-holdout identities/windows above remain unchanged.

### Structural findings and coordinated tests

1. **Outcome model/gate overlap:** the same calibrated flip model supplies all core lanes. Its recorded calibration maps a raw [0,1] flip probability to about [0.093,0.671]; stay confidence cannot exceed about 0.907. EARLY reversal confidence >=0.75 is unreachable through that calibration branch; FINAL >=0.90 lies near its ceiling. This is a probability-output limit, not a mathematical bound on achieved directional accuracy. Absolute-distance gates duplicate part of the confidence information and tend to select expensive quotes.
2. **Six fixed outcome architectures:** existing-predictor control, horizon-scaled diffusion, distance-only, distance/momentum, market-price control and market-residual model. Chronological tuning folds selected the existing predictor (Brier 0.1222 versus diffusion 0.1297 and market 0.1251). No replacement survived the coordinated comparison. Labels were available before each fold's first eligible test decision by at least 295 seconds.
3. **EARLY-specific cheap-domain heads:** train only on both-side 25–50c opportunities, preserving existing 75% confidence, 8c edge, <=45c preference and timing gates. Fixed shallow interactions improved tuning-fold Brier from 0.1935 to 0.1844 and opened-challenge Brier from 0.2179 to 0.2073, but produced zero qualified calls. The prior-residual head failed calibration and produced zero challenge calls. Better average scoring without coverage is not a product improvement.
4. **SCALP impulse/quote-lag conflict:** sequence impulse before lagged entry, steady velocity instead of acceleration-only triggering, probability-scaled quote response and BTC/BRTI basis dislocation were tested as fixed hypotheses. The sequence route produced one tuning target and no challenge entries. Quote-response residual p95 was only about 6.27c on the challenge, below the existing 8c target plus spread. The basis-dislocation challenge call stopped at -13c before later favorable movement; later MFE must not be counted as a win.
5. **Separate SCALP path objective:** native timestamped quote paths recovered 149 decisive tuning labels versus 80 independently confirmed labels. These are same-feed observed bid marks, not fills or independent confirmation. The linear first-passage model stopped on both challenge calls. Fixed nonlinear interactions performed worse than the constant control on chronological folds; the forest challenge had two targets and two stops, mean -1.25c before fees. No promotion.
6. **FINAL must track the original position:** the existing research protection collector begins only after FINAL and records preferred-side confidence. The new tested research kernel instead retains the original ticker/target/side, maps confidence to that side, distinguishes initial opposition from a subsequent flip, and exposes confirmation, deterioration, 5m caution, 3m guard and profit-warning flags independently of new-entry qualification. It rechecks true BRTI age at the joined quote time and reports unavailable evidence instead of a stale HOLD/EXIT. It does not emit production advice or orders.

### Measured frontier, not a claim of maximum possible performance

All challenge coverage below uses **13 official / 21 scheduled contracts**, including eight missing-official slots. Training used 26 earlier contracts. No old/new runtime pooling occurred.

| Role / fixed research candidate | Opened-challenge result | Decision |
|---|---|---|
| Actual EARLY baseline | 1/13 official, 1/21 scheduled; 1/1 correct; 33c; 7.229m left | Too few calls for certification; retain baseline. |
| Actual FINAL baseline | 2/13 official; 2/2 correct; median 1.324m left | High reliability goal remains unproven; late confirmation has not demonstrated EARLY protection. |
| Diffusion FINAL architecture | 8/13 official; 7/8 correct; median 4.811m left, 89.5c | Earlier/broader, but 87.5% is below the desired goal; also removed the sole EARLY call. Reject joint promotion. |
| Distance/momentum FINAL | 4/13 official; 4/4 correct; median 3.827m left, 88.3c | Poor tuning-fold calibration and tiny challenge sample; no validated improvement. |
| Market-residual FINAL | 5/13 official; 5/5 correct; median 4.383m left, 92.6c | Small sample and weak tuning performance; not 93–95% certification. |
| Nonlinear first-passage SCALP | 4/13 official; 2 targets / 2 stops; median 35c, 9.360m left; -1.25c mean observed exit mark | Reject. Both directions retained. |

The cheap-price control's 12/17 target-first native marks across 11 challenge contracts are an opportunity diagnostic, not a promoted strategy: only 6/17 ultimately won settlement, illustrating why SCALP and EARLY need different objectives. Independent-tape confirmation was incomplete. Fees, available size, manual reaction latency and actual fills are not established.

### EARLY → FINAL protection result

Use `STRUCTURAL_POSITION_PROTECTION_V2_20260924.json`. V1 remains preserved but its initial-opposition counts are not flip counts; V2 explicitly requires prior support and excludes already-underwater warnings from positive warning-lead calculations.

For the sole actual EARLY call (`KXBTC15M-26SEP240800-00`, UP 33c), unchanged FINAL never qualified a confirming call in the observed path. A model-plus-BRTI opposition rule would warn at breakeven about 4.97s after entry; the position nevertheless settled UP. The fixed profit-warning probe marked +10c at 40.97s after entry, about 14s before a later observed loss of breakeven. Treating that warning as a mandatory exit would also surrender eventual settlement upside. There were 405 qualified native quote observations but only 94 contemporaneously source-qualified probability joins; no continuous-monitoring claim is justified.

In the separate cheap-control stress universe, model-plus-BRTI post-support flips warned on 14/17 challenge positions, including five eventual winners and nine eventual losers. Profit warnings appeared on 13/17, including six eventual winners. The observed 11.6c average mark on those 13 is conditional and not whole-policy profit. These tests support preserving separate CAUTION/PROTECT flags rather than installing unconditional exits. Actual EARLY losing-thesis recall and useful-warning sensitivity cannot be measured from one winning EARLY contract.

### Next executable checkpoint

- Evaluate the already registered corrected-input tuning window when it closes at **17:00 UTC**, lock any candidate before the **17:15–21:15** internal validation, and leave original reserved validation / October 9 holdout protected. No survivor from the old-runtime structural batches is authorized for promotion on these results alone.
- First priority is the corrected causal input/model trajectory and the original-side protection lifecycle, including missing-source intervals and manual bid realization. Use the existing exact-feature journal where accessible; never reconstruct its unobserved pre-correction vectors. Its read-only export remains an access/engineering dependency for exact 20-feature refitting; timestamped common telemetry can still evaluate the fixed telemetry-based hypotheses without it.
- If corrected-input evidence still lacks cheap predictive edge, the next distinct feature hypothesis is timestamped book depth / imbalance / queue depletion from the **existing** Kalshi WS book. The current reader already maintains quantities; this historical replay lacks those depth features. Preserve a new prospective feature identity before evaluation, use no new authenticated BRTI polling, and do not claim depth will improve performance before testing it. Do not repeat the exhausted momentum/gap/threshold families.
- Live read-only Railway status at about **14:06 UTC** reconfirmed main deployment `454f53ad-b269-4133-b0f5-60098978db71`, owner and clean collector SUCCESS, main 10 GB / clean 50 GB. No restart/configuration change was made. This status check is not four-complete-contract acceptance.
- Verification: the existing/new audit suite passed **58/58**, followed by **18/18** focused protection/source tests (including nine additional distinct cases, **67 distinct tests** in total). One initial invocation omitted the repository from PYTHONPATH and failed import discovery; the corrected invocation passed. No runtime regression gate was repeated because production code did not change. `git diff --check` passed. Hosted evidence CI is assessed on the review PR.

No strategy thresholds/weights were promoted. Research accounting and original-side protection code are implemented and tested. Remaining empirical promotion work requires fresh separated evidence; the feature-export/depth instrumentation and whole-system acceptance items above must not be mislabeled as already complete.
