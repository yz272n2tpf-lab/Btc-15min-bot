# BTC15 Railway cost resolution — final read-only pass

Decision date: 2026-09-25. **No Railway or GitHub mutation was performed. SIGNAL ONLY / NO ORDERS.**

**Recommendation: retain ten services; archive and retire the other 33 deployments. The supported CPU+RAM run rate falls from $130.77 to $56.26/month, a $74.51/month reduction. Approximately $20/month is not supported by the measured footprint while preserving required runtime and evidence.** This is a proposed cleanup, not an executed result.

Production remains PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`, deployment `f82466d0-70ab-4779-a0fd-58832ad31513`. Approved candidate `06261dbfbe6d8336a6886a4f2b349f33b06b6202` remains undeployed; its qualification evidence checkpoint is `ca03e4cd85037116a866d2b9108df0ad2365e738`.

The existing resource evidence is `completion_audit/TWO_CLOCK_LIVE_RESOURCE_PREFLIGHT_20260925.json` at checkpoint `852e9a4638eb487ffe5a307b79d039d2a9b747c1`, tree `b7e8d779a53d78fede725a3ea02f8597a8bb4ce0`. Its SHA-256 is `531ce2fbc3c90068c0aefa4c493f5e9f45c92547f16aafff963c00062167d8f5`. The saved survey contains six-hour means sampled every 60 seconds, 361 samples per series, collected at `2026-09-25T02:39:35.830Z`. This pass did not repeat it or rerun qualification/tests.

Read-only work in this pass: current inventory/configuration and deployed identities for all 43 services; exact deployed source/entrypoint and dependency reads; one main health/page read; focused unarmed and old V8.1 deployment-log reads. No authenticated market polling was added. All classifications below derive from actual code/dependency/configuration evidence, not names, age or SUCCESS status.

## Current measured run rate

Published rates reused from the preflight: **$20/vCPU-month + $10/GB-month**. Per-service calculation is `20 × six-hour mean CPU cores + 10 × six-hour mean memory GB`. GB here is Railway's decimal GB metric, not GiB. This is a 30-day-equivalent resource extrapolation if those means persist, not invoice precision.

| SCOPE | MEAN CPU CORES | MEAN RAM GB | CPU+RAM / MONTH |
| --- | --- | --- | --- |
| scalp-unarmed-live-tape-v1 | 0.479335 | 5.418637 | $63.77 |
| Btc-15min-bot | 0.939079 | 0.899013 | $27.77 |
| scalp-move-shadow-v1 | 0.127191 | 0.988577 | $12.43 |
| scalp-finalprod-clean-v1 | 0.073762 | 0.811078 | $9.59 |
| All remaining 39 services combined | 0.246505 | 1.227556 | $17.21 |
| Current project: all 43 | 1.865871 | 9.344861 | $130.77 |
| Recommended ten retained services | 1.240692 | 3.144274 | $56.26 |
| 33 proposed retirements / savings | 0.625179 | 6.200587 | $74.51 |

The account preflight reported effective **PRO** tier. Its `includedUsageDollars=0` tool field conflicted with public Pro included-usage documentation; it was not treated as an invoice. Actual credits, cycle charges and projected invoice remain unavailable. Under standard published Pro billing, included usage counts toward the $20 minimum; it is not a further $20 subtraction from these resource totals. Storage, network, tax, special credits/discounts and other projects are excluded. Retained storage and egress can increase the total; configured volume capacity is not a measure of used/billable data.

The 39-service remainder is fully itemized below, rather than being an unexplained residual. Zero means the saved survey returned zero; it does not prove a service is stopped.

## Service decision table

Aliases: **M** = Btc-15min-bot/PR36; **V** = v81-live-diagnostics; **B** = brti-shared-feed-v1; **G** = scalp-move-shadow-v1; **C** = scalp-finalprod-clean-v1; **D1** = combined-dashboard-shadow-v1; **D6** = scalp-display-bridge-v6. D11/D13/D14 refer to the corresponding shadow dashboards.

Dependency flags **P/V/B/I** answer, in order, whether PR36, V8.1, shared BRTI, and the approved informational candidate require that service. `Y` = required; `S` = the owner itself; `–` = no runtime dependency found. PR36's V dependency is the preserved dashboard/V8.1 product connection, not V writing native EARLY/FINAL state. G/C are retained for required prospective evidence even though the information calculation does not call them.

“No retained consumer” means none among the inspected project services and frozen entrypoints; it does not assert that nobody outside the project has ever opened a research URL. Variable values/reference expressions are redacted by Railway. Therefore this plan keeps every service object and its variables/credentials/reference definitions, including retired services. It does not assume hidden credential references are absent.

**REQUIRED:** retain owner/runtime/evidence function. **CONSOLIDATABLE:** logically removable only after lossless state preservation is proven; KEEP in this plan. **ARCHIVAL-ONLY:** no required ongoing runtime consumer, but capture the stated evidence before retirement. **SAFE-TO-STOP:** affirmative stateless/parked/test-only evidence and dependency closure support stopping; retain configuration and any historical outputs. No service or volume deletion is proposed.

| SERVICE | PURPOSE | DEPENDENCIES P/V/B/I | UNIQUE DATA/STATE | CLASSIFICATION | MEASURED COST / MO | PROPOSED ACTION | EVIDENCE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| scalp-unarmed-live-tape-v1 | Repeated blueprint/unarmed research calculation | –/–/–/–; reads: G export; D1 timer status (URL override hidden); feeds: No retained runtime consumer | Latest RAM summary/logs; inputs remain in G; deterministic research rerunnable | ARCHIVAL-ONLY | $63.77 | Archive summary/logs; stop first | [E01](#e01) |
| Btc-15min-bot | PR36 native owner + dashboard, Rescue, parity, protection and observer | S/–/–/Y; reads: B; Kalshi; Coinbase; frozen local model/history; feeds: G; C; scorecards; shadow UIs. M browser consumes V, not the converse | /data: BTC history, strategy state, journals, native scoring/evidence | REQUIRED | $27.77 | Keep exact PR36; no changes | [E02](#e02) |
| scalp-move-shadow-v1 | G: generalized frozen V2 tape + serial V5 bridge | –/–/–/–; reads: B; Kalshi/Coinbase; M for combined state; feeds: C common observer; unarmed; incremental cache; combined scorecard; display/shadow UIs; holdouts | Unique generalized tape and serial state on /data | REQUIRED | $12.43 | Keep: C explicitly reads G/state | [E03](#e03) |
| scalp-finalprod-clean-v1 | C: clean frozen V2 collector + durable common observer | –/–/–/–; reads: M; B; V; G; Kalshi/Coinbase; feeds: Developing-move research; future ladder evidence | /data: run manifests, clean event/state files, cross-lane common JSONL.gz | REQUIRED | $9.59 | Keep; do not merge its cohort with G | [E04](#e04) |
| scalp-developing-move-v1-forward | Fixed-filter research pass over clean tape | –/–/–/–; reads: C/path-export; feeds: No retained runtime consumer | Local forward_state.json and logs; underlying candidate/result rows remain in C | ARCHIVAL-ONLY | $2.78 | Archive state/logs; stop repeated calculation | [E05](#e05) |
| scalp-incremental-disk-v2 | Disk cache/delta API for G export | –/–/–/–; reads: G export via configured URL; feeds: Research export clients; none in retained production closure | /tmp/scalp_path_export.csv + manifest; copy of G, not original owner | ARCHIVAL-ONLY | $1.65 | Archive manifest/cache; stop after research clients | [E06](#e06) |
| v81-live-diagnostics | V: actual V8.1 entry/position owner exposed to main dashboard | Y/S/–/Y; reads: B; Kalshi/Coinbase; frozen V8.1 modules; feeds: M browser panel; C common observer | Current V8.1 lifecycle/diagnostic state and records | REQUIRED | $1.61 | Keep existing owner; not a disposable diagnostic | [E07](#e07) |
| scalp-coverage-audit-v1 | Frozen flip-risk V2 research collector | –/–/–/–; reads: M; historical source/chart input and public settlement; feeds: Scoreboard/review research only | RAM prediction/cohort/settlement detail; API returns aggregates, not full prediction store | CONSOLIDATABLE | $1.61 | KEEP evidence holder; no lossless export proved | [E08](#e08) |
| v81-live-diag-shared-brti-shadow | Disposable shared-BRTI V8.1 comparison copy | –/–/–/–; reads: B through BRTI_SHARED_URL; Kalshi/Coinbase; feeds: No retained consumer | Independent comparison logs/current state; not production V owner | ARCHIVAL-ONLY | $1.25 | Archive comparison evidence; stop copy | [E09](#e09) |
| v81-30-45-live-feed-v2 | Superseded V8.1 feed, still executing in deployed image | –/–/–/–; reads: Kalshi/Coinbase and legacy feed modules; feeds: No retained consumer; live main HTML names V instead | Independent old feed state/logs; current parking config not yet its running behavior | ARCHIVAL-ONLY | $1.08 | Archive /state and runtime outputs; stop actual deployment | [E10](#e10) |
| brti-shared-feed-v1 | B: shared causal BRTI owner | Y/Y/S/Y; reads: Authenticated Kalshi; existing credentials/reference configuration; feeds: M; V; G; C; disposable shared copy | Current source/history buffer; essential source ownership | REQUIRED | $1.03 | Keep poll/freshness/backoff and credentials unchanged | [E11](#e11) |
| rollover-alt-discovery-probe-v1 | Alternate market discovery research probe | –/–/–/–; reads: Public Kalshi market API; feeds: No retained consumer | Probe log observations; integrated PR36 owns actual rollover | ARCHIVAL-ONLY | $1.03 | Archive probe logs; stop duplicate probe | [E12](#e12) |
| combined-forward-scorecard-v1 | Union scorecard + old rollover probe | –/–/–/–; reads: G combined/state; M indirectly; public Kalshi; feeds: Research score display/reports | RAM original contract/entry/scalp records; exported contract_rows are reduced | CONSOLIDATABLE | $0.63 | KEEP evidence holder; aggregate API insufficient | [E13](#e13) |
| final-forward-scorecard-v1 | Legacy FINAL forward scorecard V4 | –/–/–/–; reads: M; public Kalshi settlement; feeds: Scoreboard and review hub | RAM cohort/late-exclusion/first-seen state; API exposes calls but not full cohort state | CONSOLIDATABLE | $0.60 | KEEP evidence holder; preserve original sample | [E14](#e14) |
| early-final-handoff-v1 | EARLY→FINAL observational handoff collector | –/–/–/–; reads: M; settlement via local helper; feeds: Scoreboard and review hub | RAM early_records/final_records/cohort/settlements; summary API only | CONSOLIDATABLE | $0.54 | KEEP evidence holder; do not mistake summary for backup | [E15](#e15) |
| early-excursion-forward-v1 | EARLY path/excursion observational collector | –/–/–/–; reads: M; public Kalshi settlement; feeds: Scoreboard and review hub | RAM entry/path extrema, target-hit timing, cohort/settlements; aggregate API | CONSOLIDATABLE | $0.44 | KEEP evidence holder; do not discard paths | [E16](#e16) |
| combined-dashboard-shadow-v11 | Older combined UI V12 wrapper | –/–/–/–; reads: M; D6→G; feeds: No retained consumer | Stateless presentation; source states live elsewhere | SAFE-TO-STOP | $0.42 | Stop before D6; preserve code/config/logs | [E17](#e17) |
| rollover-prediscovery-shadow-v1 | Prediscovery timing research probe | –/–/–/–; reads: Public Kalshi market API; feeds: No retained consumer | Probe logs; PR36 has integrated discovery/handoff | ARCHIVAL-ONLY | $0.39 | Archive logs; stop probe | [E18](#e18) |
| scalp-display-bridge-v6 | D6: display-latch adapter for G | –/–/–/–; reads: G/state and G/combined-state; feeds: D11/D13/D14 shadow UIs only | Display latch/cache, no native strategy ownership | SAFE-TO-STOP | $0.37 | Stop after D11/D13/D14; preserve diagnostic snapshot | [E19](#e19) |
| combined-dashboard-shadow-v1 | D1: old combined UI V10 wrapper | –/–/–/–; reads: M; G/combined-state; feeds: Unarmed worker's timer-status read | Presentation/timer diagnostic only; no strategy/history writes | SAFE-TO-STOP | $0.33 | Stop only after unarmed worker | [E20](#e20) |
| early-forward-scorecard-v1 | EARLY V2 research collector | –/–/–/–; reads: M; public Kalshi settlement; feeds: Scoreboard and review hub | /state exposes call_records, settled_records, first_protected_calls, contract_audit, pending and checkpoints | ARCHIVAL-ONLY | $0.29 | Archive full /state and logs; stop after consumers | [E21](#e21) |
| combined-dashboard-shadow-v14 | Candidate UI V14, not installed native dashboard | –/–/–/–; reads: M; D6→G; feeds: No retained consumer | Stateless presentation of upstream state | SAFE-TO-STOP | $0.27 | Stop before D6; preserve code/config | [E22](#e22) |
| authoritative-scoreboard-v1 | Read-only report aggregator; name grants no action authority | –/–/–/–; reads: FINAL/EARLY/handoff/excursion/flip scorecards; feeds: Research report viewers only | No collector/model state; no-cache report composition | SAFE-TO-STOP | $0.25 | Snapshot /viewmodel and /state; stop before EARLY collector | [E23](#e23) |
| final-v4-review-tooling-v1 | Read-only review hub | –/–/–/–; reads: FINAL/EARLY/handoff/excursion scorecard endpoints; feeds: Research report viewers only | Pure review composition; upstream evidence retained | SAFE-TO-STOP | $0.24 | Snapshot /reviews; stop before EARLY collector | [E24](#e24) |
| combined-dashboard-shadow-v13 | Candidate UI V13 wrapper | –/–/–/–; reads: M; D6→G; feeds: No retained consumer; native PR36 embeds its own dashboard payload | Stateless presentation | SAFE-TO-STOP | $0.22 | Stop before D6; preserve code/config | [E25](#e25) |
| v81-final-isolated-test | Parked isolated V8.1 research executable | –/–/–/–; reads: Current command signal.pause(); credentials retained; feeds: No retained consumer | Historical logs/files, not active V8.1 ownership | SAFE-TO-STOP | $0.09 | Preserve existing files/logs; disable autodeploy and stop idle instance | [E26](#e26) |
| scalp-v81-sub30-shadow | Parked old sub-30 V8.1 worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.04 | Archive existing outputs; stop idle instance | [E27](#e27) |
| scalp-lead-v6-main | Parked V6 worker on main branch | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer; production uses V | Historical V6 outputs; source not deleted | SAFE-TO-STOP | $0.04 | Disable autodeploy first; stop idle instance | [E28](#e28) |
| scalp-lead-shadow | Parked lead research worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy; stop if running | [E29](#e29) |
| scalp-lead-qualified | Parked qualified lead worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy; stop if running | [E30](#e30) |
| scalp-lead-v4 | Parked V4 lead worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy; stop if running | [E31](#e31) |
| scalp-lead-v5-live | Parked V5 lead worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy; stop if running | [E32](#e32) |
| scalp-lead-v5-main | Parked V5 worker on main branch | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy first; stop if running | [E33](#e33) |
| scalp-lead-v6 | Parked duplicate V6 worker | –/–/–/–; reads: Current command sleep only; feeds: No retained consumer | Historical research files/logs | SAFE-TO-STOP | $0.00 | Disable autodeploy; stop if running | [E34](#e34) |
| scalp-v81-sub30-shadow-v2 | Finished/parked sub-30 test | –/–/–/–; reads: Current command print then exit; feeds: No retained consumer | Test logs and repository evidence | SAFE-TO-STOP | $0.00 | Disable autodeploy; leave down if already exited | [E35](#e35) |
| v81-immutable-test | Parked immutable V8.1 research executable | –/–/–/–; reads: Current command signal.pause(); feeds: No retained consumer | Historical immutable-run files/logs | SAFE-TO-STOP | $0.00 | Preserve evidence; disable autodeploy and stop if running | [E36](#e36) |
| v81-30-45-dashboard-validation-v3 | One-shot dashboard self-test configuration | –/–/–/–; reads: Configured --self-test; file absent in reported deployed commit; feeds: No retained consumer; no public provider | Test logs; deployment/config mismatch retained explicitly | ARCHIVAL-ONLY | $0.00 | Archive logs/config; disable reruns; do not redeploy to inspect | [E37](#e37) |
| scalp-entry-profit-holdout-v1 | Crashed entry/profit holdout review | –/–/–/–; reads: Generalized tape via research source module/configured URL; feeds: No retained consumer | Holdout files/logs; never relabel as new validation | ARCHIVAL-ONLY | $0.00 | Archive available files/logs; leave crashed/down; disable reruns | [E38](#e38) |
| scalp-reversal-reentry-holdout-v1 | Crashed reversal/reentry holdout review | –/–/–/–; reads: Generalized tape via research source module/configured URL; feeds: No retained consumer | Holdout files/logs; frozen provenance required | ARCHIVAL-ONLY | $0.00 | Archive available evidence; leave down; disable reruns | [E39](#e39) |
| rollover-regression-v1 | One-shot rollover regression runner | –/–/–/–; reads: Repository fixtures/generated runtime; feeds: No retained consumer | Test logs/results; integrated regression remains in repo | ARCHIVAL-ONLY | $0.00 | Archive results; disable automatic reruns | [E40](#e40) |
| rollover-core-integration-live-shadow | Crashed pre-production rollover integration copy | –/–/–/–; reads: Legacy network feeds; separate shadow runtime; feeds: No retained consumer; PR36 owns live rollover | Crash/diagnostic files and logs | ARCHIVAL-ONLY | $0.00 | Archive available evidence; leave down; disable reruns | [E41](#e41) |
| rollover-canary-predeploy-check | One-shot compile/import canary check | –/–/–/–; reads: Repository canary module; feeds: No retained consumer; actual canary runs inside PR36 | Test logs; source retained | SAFE-TO-STOP | $0.00 | Disable automatic reruns; leave down if exited | [E42](#e42) |
| rollover-handoff-predeploy-check | One-shot handoff tests | –/–/–/–; reads: Repository fixtures/native source; feeds: No retained consumer; handoff runs inside PR36 | Test logs; source retained | SAFE-TO-STOP | $0.00 | Disable automatic reruns; leave down if exited | [E43](#e43) |

## Minimum safe topology — services that must remain

Retain the following ten **without restart, configuration changes, cadence changes or ownership changes**:

| SERVICE | WHY IT MUST REMAIN | CPU+RAM / MONTH |
| --- | --- | --- |
| Btc-15min-bot | Keep exact PR36; no changes | $27.77 |
| scalp-move-shadow-v1 | Keep: C explicitly reads G/state | $12.43 |
| scalp-finalprod-clean-v1 | Keep; do not merge its cohort with G | $9.59 |
| v81-live-diagnostics | Keep existing owner; not a disposable diagnostic | $1.61 |
| scalp-coverage-audit-v1 | KEEP evidence holder; no lossless export proved | $1.61 |
| brti-shared-feed-v1 | Keep poll/freshness/backoff and credentials unchanged | $1.03 |
| combined-forward-scorecard-v1 | KEEP evidence holder; aggregate API insufficient | $0.63 |
| final-forward-scorecard-v1 | KEEP evidence holder; preserve original sample | $0.60 |
| early-final-handoff-v1 | KEEP evidence holder; do not mistake summary for backup | $0.54 |
| early-excursion-forward-v1 | KEEP evidence holder; do not discard paths | $0.44 |

The five owners M/V/B/G/C cost **$52.43/month**. The five evidence holders cost **$3.83/month**. Their combined **$56.26/month** is the lowest supported retirement plan with the preservation mechanisms presently demonstrated. $52.43 is not an executable safe total while the five RAM evidence holders remain unarchived.

The retained topology preserves M's existing embedded dashboard, Rescue, parity, FINAL/protection telemetry, observer/supervisor chain and storage. V remains the actual separate V8.1 owner. B remains the shared source. G and C retain their separate tapes; C's durable common observer samples M, B, V **and G**. Scorecard collectors remain observational and own no actionable strategy state.

The future approved two-clock worker belongs inside the already-qualified main application topology, not an additional Railway service. The information namespace remains INFORMATIONAL_READ_ONLY; the original native loop remains AUTHORITATIVE_ACTION_STATE. Core stays NOT_LINKED; FINAL stays shadow_only=True and shadow_protection_used_as_action=False. This cleanup does not deploy that worker or change lifecycle policy.

## Why the largest consumers differ

1. **Unarmed research ($63.77): archive and stop.** Its supervisor repeatedly launches the one-shot analysis worker, which downloads generalized G evidence and computes derived blueprint/unarmed summaries. It also reads D1 timer status. It is not the canonical tape owner and no retained runtime consumes its output. Preserve its cutoff/latest summary, logs and source identity; the underlying generalized tape remains on G's volume. Future research can use a saved cohort instead of leaving this repeated analysis deployed.
2. **PR36 ($27.77): retain.** This is the actual native strategy and product owner. At its saved means, CPU contributes $18.78 and RAM $8.99. Its fixed behavior alone exceeds the approximate $20 objective; no information-layer optimization can remove that baseline.
3. **Generalized SCALP G ($12.43): retain.** The clean collector's exact deployed `btc15_common_observer_v1.py` explicitly requests G `/state`; the retained combined scorecard also consumes G. G owns a distinct historical event tape. Similar detector code does not make its live serial state or historical cohort interchangeable with C.
4. **Clean SCALP C ($9.59): retain.** It owns clean run manifests, causal source/provenance capture, events/state and durable cross-lane observations. Its tape is not a replacement for all G history, nor can G recreate past clean/common observations after the fact. Preserve both without merging cohorts.

The five small retained evidence holders are not merely interchangeable UIs. Coverage holds prediction/cohort/settlement detail; combined holds original contract/entry/scalp records; FINAL holds cohort/first-seen/late-exclusion detail; handoff holds original early/final/settlement records; excursion holds path extrema and hit timing. Their exposed APIs omit some of this state. Summary downloads, code checkouts and filesystem copies are not lossless backups of those RAM stores. Therefore no shutdown savings are booked for them.

Two configuration traps are explicitly accounted for: old `v81-30-45-live-feed-v2` says PARKED in current configuration but its deployed logs still show V8.1 activity/Coinbase requests; it must be retired as an actual old running feed after evidence capture. Conversely, the dashboard-validation service's configured self-test filename is absent at its reported deployed commit. Preserve that mismatch and its available logs; do not redeploy it to investigate. Neither service supplies the actual main dashboard: exact source and the live served HTML name V instead.

## Estimated safe run rate and assumptions

Measured arithmetic: retained mean **1.240692 CPU cores × $20 + 3.144274 GB × $10 = $56.26/month** CPU+RAM. Proposed savings **$74.51/month (57.0%)**.

Assumptions: all 33 retirement preservation gates succeed; retained service means remain like the saved six-hour survey; no new service/candidate workload is added; no special credit offsets are assumed. Fewer retired clients may lower retained server work, but this plan books **zero speculative savings** from that. The two-clock information layer's future live increment is unmeasured and must be added when actually qualified; stress maxima are not steady-state billing assumptions. Any unarchivable service stays up and its row's cost must be added back. No new long resource survey is needed to make this decision.

Even M+V+B alone measure **$30.42/month**, before the two required tapes and evidence holders. Reaching $20 therefore requires a separately authorized change outside infrastructure retirement—such as proven optimization of required workload or a different operating-cost arrangement—not deletion of required evidence, reduced source freshness, reduced native cadence, or invented two-clock savings. This pass makes no such change.

## Data and volumes that must be preserved

Keep all three attached volumes, existing mount paths, ownership and data. None of the proposed retirement services owns an attached Railway volume in the inspected topology.

| OWNER | VOLUME ID | MOUNT / CONFIGURED CAPACITY | PRESERVATION |
| --- | --- | --- | --- |
| M | `6ced6b1a-3755-4518-a240-c895e936d443` | `/data`, 10 GB | Native state, BTC history, journals, scoring and prospective evidence; no truncation/migration |
| G | `656da4af-6a3f-4907-95da-2c0c0000cf29` | `/data`, 5 GB | Generalized event tape, including `scalp_move_shadow_v1_events.csv`, serial/source provenance |
| C | `93e974dc-b8bb-4658-bed5-dc4815308396` | `/data`, 50 GB | `scalp_<run_id>_events.csv`, state JSON, manifest JSON, common JSONL.gz and all cohort identities |

Also preserve the five RAM evidence holders by leaving their processes running. Preserve retired workers' distinct results, snapshots and historical logs off their ephemeral containers before stopping them. Archive metadata must identify UTC capture/cutoff, service/deployment/source identity, row/byte counts, SHA-256, run/cohort identity and open/unsettled status. Verify readback/JSON parsing or archive listing and checksums. Preserve original validation-only labels, including September 24 20:15–21:15 UTC; do not pool or relabel old holdouts, development cohorts or interrupted observations.

## Exact order of operations — later authorized cleanup only

Project `noble-warmth`: `baea4e22-d004-4434-b2c5-81a7fbc05086`. Environment `production`: `61775c5d-c583-4dfc-af41-f25578856fd9`.

1. **Approve only the 33 listed retirements.** Treat the ten retained IDs in the identity appendix as a protected denylist. Do not merge/deploy the two-clock candidate, touch retained variables, remove service objects, delete volumes or change the plan. Match each current service/deployment to the appendix before acting. If an item has drifted, skip that item instead of applying an old instruction blindly; this is an identity guard, not a request to repeat the investigation.
2. **Preserve rollback configuration before stopping.** Save each retirement's deployment/snapshot ID, effective deployed image/start command, source commit, current configured start command, branch, restart policy and present autodeploy setting. Current configured command alone is insufficient for old V8.1. Keep all service variables/reference expressions and credentials in Railway; do not print secrets into this report or archives. Save existing public/private URLs. No service/variable deletion is authorized by this plan.
3. **Complete the archive gates below.** Use existing authenticated Railway access. Public routes can be read directly; private/loopback routes and ephemeral files can be copied through existing Railway SSH. Do not create public domains, deploy an exporter, restart a collector, or register a new SSH key merely to obtain an archive. If access or preservation fails, leave that service running and exclude its savings. Crashed jobs must not be restarted just to recover files.
4. **Disable GitHub autodeploy on the 33 retirement services only**, using each service's source settings → Autodeploy → Disable. Record the former setting for recovery. Do not disconnect/delete the repository integration or change any retained service. Parked clones tracking `main` otherwise remain able to redeploy on future commits. This step must not itself deploy a new image; do not apply unrelated staged changes.
5. **Stop in the exact sequence below**, only after the corresponding archive gate passes. Use service UUIDs, not similarly named services. Already exited/crashed services need no restart or removal of an unrelated older deployment: leave them down and disable reruns. For a running, matched SUCCESS deployment, Railway's `down` command removes the deployment, not the service object. It targets the latest SUCCESS deployment, so first confirm that is the matched active deployment; otherwise stop by the exact deployment in the UI.
6. **Verify after each logical group**, and immediately after the unarmed worker: retained main/source/V8.1/collectors remain healthy, source data keeps advancing and no retained endpoint reports a missing retired provider. Do not wait for long prospective performance data. If a retained function regresses, stop the cleanup sequence and recover the last retired provider from its saved identity.

The following CLI forms are provided for the later authorized operator; none was executed in this pass:

```bash
railway link --project baea4e22-d004-4434-b2c5-81a7fbc05086 --environment 61775c5d-c583-4dfc-af41-f25578856fd9
railway down --service SERVICE_UUID_FROM_TABLE --environment 61775c5d-c583-4dfc-af41-f25578856fd9 --yes
```

Use `railway ssh -p PROJECT_UUID -s SERVICE_UUID -e ENVIRONMENT_UUID -- COMMAND` only for the existing permitted archival access. SSH key registration is not part of this cleanup. `railway unlink` only removes a local link; it is not the autodeploy control.

### Required archive gates

| SERVICES | EXACT PRESERVATION GATE BEFORE RETIREMENT |
| --- | --- |
| E01 unarmed | Capture `/health`, the latest available analysis summary and deployment logs; identify G export/tape cutoff, source commit and analysis parameters already used. Preserve any local result files. G tape remains live and retained. No rerun/tuning. |
| E05 developing | Copy `/app/scalp_developing_move_v1_forward_state.json` and logs; record C run manifest, tape identity and cutoff. If runtime uses an override path, copy the effective state path recorded by that deployment. Underlying clean observations remain in C. |
| E06 incremental | Capture `/health`, `/research/path-manifest`, and `/tmp/scalp_path_export.csv` (effective configured path if overridden); verify cached prefix identity against G. Stop only after its research clients. Do not delete G data. |
| E21 EARLY scorecard | Capture complete `/state`, `/plumbing` and logs. Verify `call_records`, `settled_records`, `first_protected_calls`, `contract_audit`, pending records and checkpoints are present. Declare the archive's exact observation cutoff and preserve unsettled status; do not claim later settlement or continuous collection after that cutoff. Stop only after E23/E24. |
| E09/E10 old V8.1 copies | Capture available `/state`, runtime-generated CSV/JSON records and logs, plus effective deployed identity. Preserve old independent observations as comparison evidence. Do not touch V's actual owner or B. |
| E17/E20/E22/E25 UIs; E19 adapter | Save configuration/source and diagnostic state/view snapshots; D6's latch is display-only. Retire E17/E22/E25 before E19; retire E01 before E20. Main's installed UI remains intact. |
| E23/E24 research presenters | Capture `/viewmodel` and `/state` for E23, `/reviews` for E24, plus source/config. Their upstream evidence remains with owners; these snapshots do not replace the five retained RAM collectors. |
| E12/E18 probes | Save all available observation logs/results and source/config. No new probe run. Actual rollover remains in PR36. |
| E26–E43 excluding already named items | Preserve existing runtime-generated results/files and available deployment logs, exact source and configuration; retain holdout/validation labels and crash provenance. Do not revive completed/crashed jobs. For E37, preserve the command/source mismatch explicitly. |

If an endpoint is private, use existing Railway SSH to read its loopback HTTP route, with its already-configured PORT; do not expose it publicly. Copy generated files off the service and verify their checksum before retirement. Do not archive secrets. A snapshot closes an observational cohort at its recorded cutoff; it is not a promise to resume RAM state or preserve later, uncollected outcomes. The five known incomplete-export collectors are deliberately absent from these shutdown gates.

### Retirement sequence — services that can be stopped

All rows are contingent on their archive gate; **none are to be deleted**. Zero-cost rows receive no claimed savings. Status is the read-only deployment snapshot, not proof that a process is currently doing work.

| ORDER | SERVICE | SERVICE UUID | DEPLOYMENT STATUS | ACTION / DEPENDENCY ORDER |
| --- | --- | --- | --- | --- |
| 1 | scalp-unarmed-live-tape-v1 | `cc7ca702-ddbc-4f61-8205-873e34b7d740` | SUCCESS | Archive summary/logs; stop first |
| 2 | scalp-developing-move-v1-forward | `fcfb3a93-f007-4061-9cb8-bdae28f72cc2` | SUCCESS | Archive state/logs; stop repeated calculation |
| 3 | final-v4-review-tooling-v1 | `56b8496c-8dea-409b-a236-9e139a9c2e96` | SUCCESS | Snapshot /reviews; stop before EARLY collector |
| 4 | authoritative-scoreboard-v1 | `6c0ec9d5-2187-4623-97ec-44c3304b8074` | SUCCESS | Snapshot /viewmodel and /state; stop before EARLY collector |
| 5 | combined-dashboard-shadow-v11 | `87801206-d705-43d6-8aa2-bfb1b11c1ff6` | SUCCESS | Stop before D6; preserve code/config/logs |
| 6 | combined-dashboard-shadow-v13 | `b210d5f0-0616-4e39-9812-ce7b41b73d67` | SUCCESS | Stop before D6; preserve code/config |
| 7 | combined-dashboard-shadow-v14 | `c1db8b80-f656-4295-ade8-812c129f6c72` | SUCCESS | Stop before D6; preserve code/config |
| 8 | combined-dashboard-shadow-v1 | `142e0fe5-13ce-4cb7-a08b-d4a65539fb47` | SUCCESS | Stop only after unarmed worker |
| 9 | scalp-display-bridge-v6 | `90046a79-3f57-493f-b473-18d0031e8f0d` | SUCCESS | Stop after D11/D13/D14; preserve diagnostic snapshot |
| 10 | early-forward-scorecard-v1 | `efb56ace-8c0e-4672-a772-6dd3b8633078` | SUCCESS | Archive full /state and logs; stop after consumers |
| 11 | scalp-entry-profit-holdout-v1 | `4a7f7942-7701-4441-8061-d1c6148d0e81` | CRASHED | Archive available files/logs; leave crashed/down; disable reruns |
| 12 | scalp-reversal-reentry-holdout-v1 | `a0f417fe-9bfe-4d80-bcd0-5647a582a1e7` | CRASHED | Archive available evidence; leave down; disable reruns |
| 13 | scalp-incremental-disk-v2 | `f4d0996f-9dd1-47ba-a237-67353acd5bec` | SUCCESS | Archive manifest/cache; stop after research clients |
| 14 | v81-live-diag-shared-brti-shadow | `84f579fc-36d0-4170-8a28-6d26c01bb364` | SUCCESS | Archive comparison evidence; stop copy |
| 15 | v81-30-45-live-feed-v2 | `afd8f1f0-65f6-46f0-a79b-ef582f35293f` | SUCCESS | Archive /state and runtime outputs; stop actual deployment |
| 16 | rollover-alt-discovery-probe-v1 | `5a3eda51-3074-42aa-9e46-06695d47a378` | SUCCESS | Archive probe logs; stop duplicate probe |
| 17 | rollover-prediscovery-shadow-v1 | `9a566a85-0b12-4ab7-9c95-cced457e3bf5` | SUCCESS | Archive logs; stop probe |
| 18 | v81-final-isolated-test | `10045980-cdd0-485a-a827-b50a3f0b4943` | SUCCESS | Preserve existing files/logs; disable autodeploy and stop idle instance |
| 19 | scalp-v81-sub30-shadow | `2e63484b-e726-41fc-980a-a117b5efdcfd` | SUCCESS | Archive existing outputs; stop idle instance |
| 20 | scalp-lead-v6-main | `568716be-9c96-446e-aecb-0fcd16158b8e` | SUCCESS | Disable autodeploy first; stop idle instance |
| 21 | scalp-lead-shadow | `90d3435e-c98c-43ae-880f-cd629b9606e2` | SUCCESS | Disable autodeploy; stop if running |
| 22 | scalp-lead-qualified | `f6e62c87-ac2a-4340-8be2-72932ad4c486` | SUCCESS | Disable autodeploy; stop if running |
| 23 | scalp-lead-v4 | `ca605c00-4608-4b32-b0bb-d1ca9c6b42a5` | SUCCESS | Disable autodeploy; stop if running |
| 24 | scalp-lead-v5-live | `7e643823-456a-414b-a369-0ee40462223f` | SUCCESS | Disable autodeploy; stop if running |
| 25 | scalp-lead-v5-main | `2b0060ac-e0d1-49a2-a2f6-b577fd9ac478` | SUCCESS | Disable autodeploy first; stop if running |
| 26 | scalp-lead-v6 | `ea6e520b-fa94-49bb-abf9-094817ae3d6b` | SUCCESS | Disable autodeploy; stop if running |
| 27 | scalp-v81-sub30-shadow-v2 | `b883a5e1-7cef-4d3d-b3f6-cffccde53053` | SUCCESS | Disable autodeploy; leave down if already exited |
| 28 | v81-immutable-test | `0bda3f3d-90b7-4934-8636-d16a45a3dc32` | SUCCESS | Preserve evidence; disable autodeploy and stop if running |
| 29 | v81-30-45-dashboard-validation-v3 | `43e53181-102a-4759-a7cd-70875c605cf0` | SUCCESS | Archive logs/config; disable reruns; do not redeploy to inspect |
| 30 | rollover-regression-v1 | `331072c6-1ab4-47dc-a6b4-c3af053e4975` | SUCCESS | Archive results; disable automatic reruns |
| 31 | rollover-core-integration-live-shadow | `ab491df9-2b75-43f2-92da-bc2a6db1cf6d` | CRASHED | Archive available evidence; leave down; disable reruns |
| 32 | rollover-canary-predeploy-check | `fd54c023-b855-4ccb-90ca-4cbf772bdf4a` | SUCCESS | Disable automatic reruns; leave down if exited |
| 33 | rollover-handoff-predeploy-check | `cf307d3c-064f-4675-a2d5-c61ec0429f62` | SUCCESS | Disable automatic reruns; leave down if exited |

## Post-cleanup verification checklist

- All ten protected services still have their original active deployment identities, variables, owner roles and attached volumes; no unexpected deployment/restart was triggered. Retired service objects and credentials/reference definitions still exist, with autodeploy disabled.
- PR36 main health and native decision timestamps continue; dashboard, Rescue, parity, FINAL/protection telemetry, logging/scoring and observer/supervisor behavior remain available. The main V8.1 panel still reads `https://v81-live-diagnostics-production.up.railway.app/state`.
- B source timestamps and provenance continue advancing; reject stale/future observations and retain the ≤5.0-second BRTI rule. No added authenticated upstream poller appears. V retains its original independent lifecycle owner.
- G tape and serial state continue; C manifests/events/common archive continue appending under their original run identities. C's common observer still receives M, B, V and G. Do not trigger rollover or collect a new validation cohort solely for cleanup verification.
- Five RAM evidence holders remain up with their prior records/cohort identity. Verify their counts/health have not reset. Retired research outputs are archived with cutoffs, checksums and explicit unresolved settlements.
- Core remains NOT_LINKED; FINAL remains shadow_only=True and shadow_protection_used_as_action=False. No external report or information output acquires action authority. No orders are submitted.
- Each of the 33 retirements is either confirmed stopped/exited or explicitly recorded as skipped. A stopped service's old URL may become unavailable; no retained runtime may depend on it. Confirm no automatic redeploy immediately recreates it.
- All three volume UUIDs, mount paths and data remain; no truncation, migration, deletion or resize occurred. All archives are readable outside the retired ephemeral container.
- Record completed/failed retirement IDs and apply only achieved row savings to the estimate. Billing and resource graphs may lag; no six-hour resurvey, ladder test, tuning or long wait is required by this plan.

## Rollback / recovery requirements

Keep every service object, public/private URL, source reference, variable/reference definition and all three volumes. Before stopping a running item, retain its exact deployment/snapshot identity and available image/redeploy path. Railway image retention/rollback availability is finite; do not promise indefinite one-click restoration. If its effective deployed configuration cannot be recovered—especially E10's PARKED-config/running-image mismatch—skip the retirement until that recovery record is secure.

If a retained dependency regresses after an individual retirement, restore **that last retired provider** from its recorded deployment image/snapshot, not the current branch head. Restore the former autodeploy setting only as needed. Recheck the retained consumer, then stop the sequence and record the failed assumption. Do not restart PR36, change the approved candidate, or alter source freshness/strategy thresholds to compensate.

Source commit plus saved effective configuration provides the longer-term rebuild recipe if the hosted image expires; rebuild only in a separately authorized recovery. Ephemeral RAM is not restored by redeploying code. Archived research cohorts remain immutable closed records; any resumed research worker starts a clearly new epoch, without fabricating continuity. The five non-exportable RAM collectors remain running precisely to avoid this problem.

PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77` remains the native production baseline throughout. No native rollback deployment is needed for the proposed cleanup because the native deployment is never changed. Candidate `06261dbfbe6d8336a6886a4f2b349f33b06b6202` remains approved but undeployed.

## Final cost verdict
