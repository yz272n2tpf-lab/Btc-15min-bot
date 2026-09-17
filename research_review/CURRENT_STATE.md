# CURRENT STATE — upstream storage diagnosis

Checked 2026-09-17; Early state captured at 01:23:06 UTC. This Work thread remains the sole engineering/control authority.

- **CONTROL:** All frozen collectors remain untouched. Railway still reports 50 services. No service edits, deletions, restarts, volume changes, orders or promotions were performed.
- **NEW SHADOW:** Existing V2 experiment and undeployed review tools unchanged. Added the read-only incident report `UPSTREAM_STORAGE_INCIDENT_20260917.md`; no new Early rule or recovery was deployed.
- **BLOCKED:** The original upstream `Btc-15min-bot` is CRASHED and logged `No space left on device`. Disk usage is approximately 0.498 GB; configured capacity is not yet verified. Early and Final source polls have been stale since September 16 at 02:37 UTC. Early remains at 22 eligible contracts / 2 settled calls, requiring both 30 / 12 for its initial review. Its existing two calls are already settled.
- **NEXT STEP:** Seek explicit approval for storage-only recovery of the already-crashed upstream under the user's no-production-change lock. Confirm the existing `/data` allocation, expand only if the confirmed capacity is below the proposed 1 GB, and restore the same upstream revision without touching any frozen collector. Verify resumed data and preserve the outage boundary; do not backfill the missed live sample.

Deployment SUCCESS and a responsive observer watchdog do not establish fresh market input. The previous snapshot milestone remains valid for its recorded V2 capture time; it was not a health certification of the other ladders.

## Historical milestone — single-snapshot evidence pack

Market evidence captured 2026-09-17 at 00:24:35 UTC (September 16, 8:24 PM Eastern). This Work thread remains the sole engineering/control authority.

- **CONTROL:** All 50 Railway services retain the same deployment IDs and statuses as this work session's baseline; no staged changes were reported. Frozen V1 collectors, the accepted V2 deployment, and the replacement feed remain untouched. No collector edits, restarts, new services, orders or promotions.
- **NEW SHADOW:** Added an undeployed one-command checkpoint runner with exact offline replay verification. All 93 regression tests pass, including 23 new pack tests. The accepted V2 service remains SUCCESS. The new pack contains one coherent snapshot: 7 full contracts / 11 serial opportunities, all 28 comparisons, six consistent historical checkpoints, and 6,952 separately labeled synthetic mechanism checks with zero failures.
- **BLOCKED:** 93 contracts / 89 signals remain to the initial overall review floor; no lane-specific sufficiency or winner is established. Raw live quote paths, individual quiet-contract IDs and exact missing-entry reasons remain unavailable from the current exports. Hashes/replay do not prove source authenticity, live causality, manual-fill performance or certification.
- **NEXT STEP:** At the next requested review, use the same checkpoint command with the five archived historical bundles plus `checkpoints/20260917T002405Z/bundle.json` as explicit history, capturing into a new directory. Compare the next completed-contract evidence without modifying any policy. There is no new background schedule. Any candidate still requires a separately frozen prospective certification window.

## New build and observations

`nextgen_v2_checkpoint.py` makes one coherent read-only capture and feeds that exact bundle into the comparison, decision-ledger, cost and longitudinal reports. It separately invokes the unchanged frozen-source synthetic audit. The pack archives inputs, outputs, experiment identity, runtime version and six tool-source hashes, writes `COMPLETE` last, then independently re-renders the reports offline. Tampered/resealed reports, mixed identities, unsafe inventories, source/runtime drift, partial writes and accidental overwrites fail closed. JSON object key ordering is normalized to make saved report bytes reproducible. No existing collector or policy file changed.

Evidence: `checkpoints/20260917T002405Z/` contains 20 files, including complete JSON and readable Markdown reports. All market reports use the 00:24:35 UTC snapshot; cumulative histories are not summed and synthetic tests are not counted as market samples. The full regression suite passes 93 tests.

Early observations remain descriptive:

- SCALP-2: all three V2 filters entered 0 of 3 control opportunity-2 records. Two control records have observed positive one-lot fee-net protected exits (+16 and +1 cents); the third has no observed protected exit.
- Dynamic Verify: 4 entries versus 11 immediate-control entries. Newly added entries are 36 cents and 97.1 cents, both `IMMEDIATE_STRONG`, neither with an observed protected exit. Only one matched protected-exit pair exists versus the immediate/5/10/15-second controls, with zero net delta. The 30-second comparison has no pair of observed protected exits. Expensive entries and omissions remain review evidence, not reasons to alter the live frozen rule.
- Selective Pullback: Balanced entered 5 of 11 opportunities; Price-disciplined entered 3. Matched prices equal the immediate control in this snapshot; no entry-price improvement is demonstrated against that control. Coverage loss remains explicit.
- Watch: confirmed half-cent warning remains about 0.96 seconds later than V1 1-cent on two paired warned exits; it is about 29.05 seconds earlier on average than the 2/3-cent controls on those same two pairs. It now has two unresolved warnings. Falling-trend still has no warnings. Frozen exit timestamps/economics remain identical; no economic credit is assigned merely for warning earlier.

## Historical milestone — decision ledger

Market evidence captured 2026-09-16 at 23:59:48 UTC (7:59 PM Eastern). This Work thread remains the sole engineering/control authority.

- **CONTROL:** Frozen V1 collectors and the running V2 experiment remain untouched. No source/start-command/variable edits, restarts, additional services, orders or promotions. All 50 deployment IDs were checked against the work-session baseline.
- **NEW SHADOW:** The same accepted V2 deployment remains SUCCESS. Latest reviewed evidence: 5 full contracts / 8 serial opportunities; snapshot integrity passes and five chronological checkpoints validate without rewritten history. Added the undeployed per-opportunity decision/omission ledger, with 28 comparisons and 16 new tests. All 70 regression tests pass.
- **BLOCKED:** 95 contracts / 92 signals remain to the initial review floor; no lane-specific sufficiency or winner is established. Exact skip reasons, raw quote paths and individual quiet-contract IDs are not exported by the current audit.
- **NEXT STEP:** Review a later coherent completed-contract snapshot using the unchanged history, comparison, cost and omission checks. Record expensive entries and coverage losses without adjusting frozen rules or inferring missing reasons. Any future candidate still requires a separate prospective certification window.

## New ledger and observations

`nextgen_v2_decision_ledger.py` records every family-anchor opportunity against all relevant lanes. Exact IDs join the records; the same opportunity across families is never counted as a new sample. Entry absence, no warning, no observed protected exit, missing fee net and observed zero net are distinct states. Available decision reasons are retained; unknown ones stay `NOT_EXPORTED`. Markdown shows 40 of 46 experiment/anchor cases and explicitly points to untruncated JSON.

This checkpoint has 26 family-anchor rows but only 8 unique serial opportunities over 5 full contracts; no quiet contracts in this snapshot. Dynamic Verify recorded 2 entries and omitted 6 relative to the immediate control. Its accepted records show `IMMEDIATE_STRONG` at 52 cents and `EVENT_CONFIRMED` at 85 cents. The 85-cent entry has no observed protected exit, so its realized/replay net is not filled in. The frozen policy permits this result; this is evidence to review, not a live fix or a new policy failure verdict.

Among the 6 Dynamic Verify control-only opportunities, the one-lot frozen replay has 2 negative-net protected exits (-3 and -9 cents), 1 positive-net protected exit (+1 cent), and 3 without observed protected exits. These are post-hoc descriptions, not proof of filtering skill. Both SCALP-2 control opportunities had positive-net protected exits (+16 and +1 cent), and all three V2 filters omitted them. Balanced Pullback retained 3 of 8; Price-disciplined Pullback retained 2 of 8. None of these small subsets justify selection or promotion.

New evidence: `decision_ledgers/20260916T235948Z/`, `captures/20260916T235948995478Z/`, and `scorecards/20260916T235948Z/`. The previous execution-cost report remains timestamped 23:49 UTC; it is not silently relabeled as this capture.

## Historical milestone — synthetic causal audit

Latest market evidence captured 2026-09-16 at 23:49:00 UTC (7:49 PM Eastern). This Work thread is the sole engineering/control authority.

- **CONTROL:** All frozen V1 collectors and the accepted V2 experiment remain untouched. The deployment, start command, source code and variables were not changed. No new Railway slot was used.
- **NEW SHADOW:** V2 remains on accepted deployment `17cac03e-20a2-46be-b535-c31f63aaf6fa`. The latest coherent snapshot has 5 full contracts and 8 serial opportunities with no integrity errors. Four chronological checkpoints pass history validation. Added an undeployed synthetic causal/boundary audit: 6,952 checks passed, zero failures; the entire regression suite now passes 54 tests.
- **BLOCKED:** 95 more full contracts and 92 more signals are needed for the overall review floor. Per-lane efficacy and manual-fill performance remain unestablished. Synthetic mechanism tests cannot prove live provider timestamps, candidate-feature causality, raw path history or cutoff eligibility.
- **NEXT STEP:** Capture another coherent post-contract checkpoint and rerun the unchanged longitudinal/cost reports. Keep all policies and collectors frozen. A promising hypothesis still requires a separately frozen prospective certification window; do not treat this engineering-test pass as certification.

## Work completed

New `nextgen_v2_causal_audit.py` invokes only unchanged fingerprint-pinned local core functions. It checks clean event-time prefixes, altered future suffixes, poisoned outcome labels, duplicate events, 30/60-second and price boundaries, SCALP-2 selection membership, pre-entry peak exclusion, input immutability and independent frozen-exit arithmetic. Twelve new regression tests prove the harness detects injected in-memory look-ahead, changed exits, source drift and input mutation. No frozen file is edited and no service loop is started.

The 6,952 checks use 40 deterministic synthetic tapes, not new market contracts. They provide no efficacy, live-causality or execution guarantee. Audit evidence is in `causal_audits/first_pinned_run/`.

The fresh market snapshot, four-checkpoint scorecard and unchanged execution-cost grid are saved under timestamp `20260916T234900Z` (capture directory `captures/20260916T234900184881Z/`). New entries remain sparse: SCALP-2 filters 0 against 2 control opportunity-2 entries; Dynamic Verify 2 against 8 immediate-control opportunities; Balanced Pullback 3; Price-disciplined Pullback 2. These counts and conditional outcomes are not a winner ranking.

## Historical milestone — execution-cost sensitivity

Evidence captured 2026-09-16 at 23:31:57 UTC (7:31 PM Eastern). Archive: `captures/20260916T233157908004Z/`. This Work thread remains the sole engineering/control authority.

- **CONTROL:** Frozen V1 controls and the V2 experiment remain untouched. No source branch, deployment, environment variable, shared collector, or order handling was changed. The 50-service Railway environment had no staged changes; V2 remains on accepted deployment `17cac03e-20a2-46be-b535-c31f63aaf6fa`.
- **NEW SHADOW:** Existing V2 reports 3 eligible full contracts and 6 serial opportunities. All snapshot integrity checks pass. Three chronological checkpoints pass the longitudinal history check. New cost tooling and reports are saved only on the undeployed review branch; all 42 review tests pass.
- **BLOCKED:** 97 more full contracts and 94 more signals remain to the overall review floor. No lane-specific sufficiency, actual-fill performance, or winner is established. Summary audit endpoints still cannot independently re-prove raw quote paths or contract first-seen timing.
- **NEXT STEP:** Capture a later coherent snapshot after additional full contracts close, append it explicitly to the longitudinal review, and repeat the unchanged cost grid. Do not alter the frozen experiment based on these observations. Any future certification requires a separate frozen prospective window.

## New work and early cost observations

Added `nextgen_v2_execution_costs.py` and 15 tests. It applies an extra 0/1/2/5 cents at each side to fixed-entry/fixed-exit fee-net values, separately for the existing 1-lot and 10-lot models. It reports all 24 lanes and 28 paired comparisons, explicit missing exits/fee scores, distinct contracts, and observed-exit sign counts. It makes no network calls, changes no fees or exits, and selects no winner.

The one-lot immediate control has four fee-scored protected exits across two contracts, with a conditional mean of +1.25 cents. Adding 1 cent at entry and 1 cent at exit reduces this to -0.75 cents. Two further opportunities lack an observed protected exit and are excluded, not valued at zero. This is a cost-sensitivity illustration, not total portfolio profit.

Balanced Pullback has two scored exits in two contracts: +3.50 cents conditional mean at baseline, +1.50 cents under 2-cent extra round-trip cost, and -0.50 cents under 4-cent cost. Dynamic Verify has only one scored exit (+16 cents) and one entry without an observed protected exit. These different subsets cannot be ranked by their headline averages. All three SCALP-2 filters still have zero entries against two control opportunity-2 entries. No optimization or promotion is justified.

The confirmed half-cent Watch warning is approximately 0.96 seconds later than V1 1-cent on the two paired warned exits, although earlier than the V1 2/3-cent thresholds on one pair; it also has one unresolved warning. Falling-trend V2 has no paired warned exits. The frozen exit timestamps and economics remain identical across Watch lanes.

Reports: `execution_costs/20260916T233157Z/` and `scorecards/20260916T233157Z/`. Cost scenarios hold fees fixed and do not simulate manual reaction delay, execution feasibility, changing spreads, liquidity or path-dependent exits.

## Historical milestone — first completed-contract checkpoint

Captured 2026-09-16 at 22:55:13 UTC (6:55 PM Eastern). Archive: `captures/20260916T225513444136Z/`.

Longitudinal tooling milestone: `nextgen_v2_longitudinal.py` now accepts explicit chronological bundle archives, rejects experiment/window drift and rewritten history, and never sums cumulative checkpoints. The first scorecard in `scorecards/first_contract/` accepted both frozen checkpoints and reports the latest totals of 1 contract / 2 signals. The complete read-only review suite passes 27 tests.

- **CONTROL:** All 49 pre-existing deployment IDs match the accepted deployment receipt; no staged Railway changes. Frozen V1 collectors remain untouched.
- **NEW SHADOW:** Combined V2 remains SUCCESS on the accepted deployment and fingerprint listed below. One full eligible contract, two serial opportunities, all four families present, and no review integrity errors. This milestone adds evidence and documentation only to the undeployed review branch.
- **BLOCKED:** 99 more full contracts and 98 more signals are needed to reach the overall manual-review floor. One contract cannot establish an advantage, false-warning rate, or lane-specific sufficiency. No winner is selected.
- **NEXT STEP:** Capture and compare the next coherent snapshot after further full contracts close, while preserving the existing code, cutoff, controls, and exit rule. Continue toward the 100-contract / 100-signal review floor; a separate prospective certification window is still required before production consideration.

## First observations — one contract only

- **SCALP-2 economics:** All three filters skipped the second opportunity at 52 cents. The V1 replay recorded a 72-cent protected exit, or +16 cents after the frozen one-lot taker/taker fee model. This is a missed profitable replay, not evidence that the new filters improve economics.
- **Dynamic Verify:** Confirmed that second opportunity immediately at 52 cents (`IMMEDIATE_STRONG`). The 30-second control entered at 77 cents and had no observed protected exit. Immediate and 5/10/15-second controls entered at the same 52 cents; there is no paired economics improvement against those controls. Dynamic Verify skipped the first opportunity, whose V1 one-lot net replay was -3 cents. These are observations, not proof of prospective filtering skill.
- **Watch:** The confirmed half-cent rule warned 29.079 seconds before the unchanged exit, 0.920 seconds later than V1 on that same opportunity, and did not warn on the other opportunity. Falling-trend V2 warned on neither. Frozen exit timestamps and economics match exactly. No materially earlier warning was demonstrated.
- **Selective Pullback:** Balanced V2 used its immediate-entry path for the same 52-cent opportunity, matching the immediate control's price and protected economics. Price-disciplined V2 and all six fixed-price V1 pullback policies took no entries. No improved pullback entry price was demonstrated.

All economics are shadow replay estimates from observed protected exits, not executed profits or total portfolio P&L. Source paths and first-seen timestamps remain outside the summary audit.

## Previous milestone — review tools

Checked 2026-09-16 at 22:34 UTC (6:34 PM Eastern). This Work thread remains the sole engineering/control authority.

- **CONTROL:** All frozen V1 services remain unchanged. A read-only Railway comparison against this work session's baseline found the same 50 services, zero changed deployment IDs, zero removed services, and no staged changes. The replacement `v81-30-45-live-feed-v2` remains SUCCESS on deployment `ae6976a2-fb93-449a-a05d-f45dc32bd478`.
- **NEW SHADOW:** `scalp-nextgen-shadow-v2` remains SUCCESS on deployment `17cac03e-20a2-46be-b535-c31f63aaf6fa`, commit `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`. Its four experiment families and 24 policy lanes remain frozen. The new `research_review/` tool belongs only to the undeployed `scalp-nextgen-v2-review-tools` branch; no service or deployment was created for it.
- **BLOCKED:** No complete post-cutoff contracts or eligible signals were present in the archived 22:30:13 UTC checkpoint. There are no performance conclusions. The exported audit also lacks full raw quote paths and contract first-observation timestamps, so independent causal/cutoff verification needs additional source evidence before later certification.
- **NEXT STEP:** Read a fresh coherent snapshot after the first full post-cutoff contract closes (around 22:45 UTC / 6:45 PM Eastern, then allow the next collector poll). Compare outcomes without modifying the frozen service. The overall 100-contract / 100-signal floor permits manual review, not promotion or a claim of lane-specific sufficiency.

## Work completed

Added a standalone, standard-library reviewer; an explicit frozen manifest; 21 passing tests; documentation; and an immutable checkpoint bundle with reproducible JSON/Markdown reports. It validates exported identity/integrity and computes 28 direct policy comparisons, with paired economics, omissions, coverage, warning lead time, and unresolved outcomes kept explicit. It never chooses or promotes a winner.

The executable makes HTTPS GET requests only to the existing shadow service. No collector code, production logic, order handling, deployment configuration, or shared source was changed.

## Accepted experiment identity

- Service: `46b79a18-0fc2-46f0-8f12-d6bac63eecad`
- Code fingerprint: `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f`
- Prospective cutoff: `2026-09-16T22:30:00+00:00`
- Window: `00e73c80479a5ec5d482d33429e5f2115513dcddd93babdf38a7e38c6b7cac67`
- Archived capture: `2026-09-16T22:30:13.718240+00:00`
- Capture result: `WAITING_FOR_FULL_CONTRACT`, 0 full contracts, 0 serial signals, no integrity errors.

Signal-only/manual trading remains mandatory. No orders, production changes, automatic promotion, or same-sample promotion. Any prospective candidate needs a separately frozen future certification window.
