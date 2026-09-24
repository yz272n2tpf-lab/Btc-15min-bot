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
