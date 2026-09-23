# BTC15 BOT COMPLETION SCORECARD — approval checkpoint, 2026-09-23 UTC

**NOT PRODUCTION-READY YET.** Coordinated corrections are reviewable and tested; production remains at662873c41fde364a994b6a22dc0bb18f21d43fdc. No deploy, restart, variable change, deletion, trade, key creation or rotation was performed. Railway browser authentication was not resumed. The externally completed credential-chain repair is accepted.

FAIL below means the production acceptance requirement is unmet or unproven, not that every function in that subsystem is broken.

| Area | Result and evidence |
|---|---|
| Infrastructure | FAIL: duplicate authenticated BRTI pollers, latent restart dependencies and non-durable research state remain in production configuration. All43 services inventoried. |
| Kalshi | Auth/discovery PASS: balanceHTTP200, exactKXBTC15M handoffs, official contract metadata observed. Full quote/data acceptance FAIL until corrected forward run proves freshness and publication together. |
| BRTI | FAIL: receipt age currently substitutes for source age; legacy parity KeyError; final60 repeatedly30/60.62 owner heartbeats:53 clean flags/62=85.48%, maximum reported age143.871s; latest1,666/1,693 requests succeeded=98.41%,27HTTP429s. These are receipt/status observations, NOT true-source availability. Credentials/cold-start success accepted. |
| 15-minute alignment | PASS for observed exact ticker/open/close and fixed-target behavior; no strategy/timing/settlement changes proposed. Missing official target correctly delays readiness. |
| Rollover | PASS for current production:10 consecutive handoffs00:30–02:45UTC, median2.0785s, min0.816s,max4.511s. Prior+2.849s remains established. Candidate live acceptance pending. |
| Downstream readiness | FAIL: full publication latency not proven; observed official target-ready delays4.602–27.165s. Handoff is not data-ready latency. |
| Ladder1 / FINAL | Historical Sep6 raw-gate replay30/56 contracts. Unique eventual-outcome anchor function retained. Current incremental contribution/calibration unproven on qualified common-universe forward data. |
| Ladder2 / EARLY | Same Sep6 raw-gate replay adds4/56 contracts, no overlap with FINAL in that slice. Affordable-entry function retained; this is historical replay, not holdout accuracy. |
| Ladder3 / SCALP-reversal | Both directions and existing true-scalp/V8.1/serial layers preserved. Sep6 union script cannot measure SCALP contribution: its committed scalp file actually covers Sep4–5. No ladder removed or threshold tuned. |
| EARLY | Latest7–10min slice:0calls/95 completed slices; accuracy, entry odds and call timing undefined. This is not whole2–10min policy coverage. Earlier protected cohort20/22=90.9%,mean31.9c,about6.09min remains historical context only. MFE/MAE and FINAL relationship require a common valid cohort. |
| FINAL | Raw mixed-revision scoreboard263/278=94.6043%,278/595=46.7227% coverage;mean5.1445min,median5.147min remaining;mean entry92.016c,median92.8c,0calls≤50c. Publication-gate mismatch invalidates claiming the live93–95%goal achieved. Calibration not established. |
| SCALP | Historical clean export169signals(84UP/85DOWN),81/126observed contracts=64.29%;mean entry51.35c,median84c;mean3.918min/median3.285min remaining;meanMFE+2.53c,MAE−1.39c,horizon gain+0.61c;8/169 reached+10c. Descriptive baseline signals, fees excluded, not a new holdout or integrated exit result. Main V8.1 exit/profit protection remains unconnected. |
| Reversal research | Last report113signals/84serial-eligible contracts,+10c58.407%,mean entry50.30c,MFE18.86c,MAE−5.81c;58continuation/55opposite-side.72%positive applies only to50protected exits. Conditional research denominators, not all-contract production coverage. |
| Restart/recovery | FAIL for full production acceptance. Local owner cold-state/429/interruption/source aging and telemetry restart tests pass. Production/container restart not executed. |
| Consecutive live rollovers | PASS:10 on existing build;0 on unapproved candidate. |
| Logging/scoring | FAIL for qualified production performance proof. Candidate adds persistent raw/eligible/source-qualified observations without overwriting historical evidence. Browser delivery and complete recall of brief signals are not claimed. |
| Signal-only / NO ORDERS | PASS: retained throughout, no order capability added, mutation-method scan passes. |
| Temporary/dead dependencies | NOT ZERO: main still needs v81-live-diagnostics; it and scalp-move-shadow-v1 directly poll BRTI; v81-final-isolated-test actively polls despite ineffective park flag. v81-immutable-test is inactive(61zero CPU/memory samples) but has a latent direct-polling restart entrypoint. Raw secret reference expressions remain inaccessible. |

## Changes, tests and review links

Main draftPR15, branch`audit/btc15-completion-20260923`, tested code commit`5cf28653172110eac5861ee7b3bcdea04a97803c`:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/15

Owner draftPR16, branch`fix/brti-source-history-20260923`, commit`018ad22efa8dec964ffc8ccb047cfdab3b00ea75`:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/16

V8.1 draftPR17, branch`fix/v81-single-brti-owner-20260923`, commit`2e505542e73d751c1bdc26237c798400fd113338`:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/17

GeneralizedSCALP draftPR18, branch`fix/scalp-single-brti-owner-20260923`, commit`51ea67baa083370dd49edd5c9b3f27be3459d2f0`:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/18

Clean collector draftPR19, branch`fix/clean-scalp-shared-source-20260923`, commit`18a142c6af43476fdc8a7ed388099b5d6db8a6c0`:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/19

- Baseline:168 regressions,167pass/1fail.
- Candidate:190/190 local tests pass in15.131s; hosted GitHub run35813501341 passes190/190 in14.263s using pinned repository requirements.
- Hosted owner source-integrity run35813310953:PASS;11/11 standalone tests also pass locally.
- Hosted V8.1/scalp migration runs35813362132/35813365423:PASS;2guard regressions each, including existing OFF-mode self-tests. Full detector-service live acceptance remains pending.
- Clean shared-consumer tests:3/3pass locally; no complete clean-service hosted/runtime acceptance claimed.
- Three explicit static gates PASS(canary paths,parity publication measurement,main authority); two wrapper self-tests PASS.
- Real localhost owner→HTTP→consumer→collector→parity ingestion confirms60source publications, no extra upstream reads, stale/future/conflict failure and429recovery.
- Initial hosted main CI failed because the new workflow omitted pandas; corrected to install the pinned repository requirements. The successful rerun above is the acceptance result.
- No model weights, ladder thresholds, entry prices, target definition, contract clock or settlement semantics were changed. No deployment made.

## Exact remaining blockers and next authorization

1. Approve and perform coordinated owner-first deployment, migrate both useful direct pollers, park only obsolete isolated execution and verify exactly one upstream owner. Keep all evidence/services; no deletion.
2. Verify any inaccessible raw configuration references externally or from permitted API evidence. In particular clean collector transport/URL and latent restart entrypoints; the repaired owner credential chain itself is already accepted.
3. Prove real-source≤5s availability and429behavior after traffic consolidation; test cold container start, interruption/recovery, child restart and several corrected consecutive rollovers. Do not fake age or loosen5s.
4. Prove exact target/quote freshness and downstream publication latency together. Candidate0live-rollovers remains a release gate.
5. Collect publication-qualified, frozen forward contract cohorts. Measure accuracy/coverage/timing/entry distributions/calibration, EARLY excursions/FINAL relationship, and ladder overlap/incremental contribution. No defensible threshold tuning yet.
6. Complete SCALP exit/profit-protection integration with measured forward evidence; preserve both directions and serial rules. Research conditional exits do not establish main display behavior.
7. Preserve and provide durable clean/research evidence. Two holdout services have CRASHED deployment state; retained logs contain results but no explicit crash cause. They are research/PARK candidates, not production dependencies to revive blindly.
8. Research split integrity: entry-profit reviewer re-fetches changing datasets hourly and recomputes validation-selected roles on each refresh; logs show role-policy changes. Its freeze label is not proof of an immutable policy/cohort. Require fixed split and policy/source manifests before using those numbers for promotion. The Sep6 union script also combines non-overlapping source dates. Neither report can justify current three-ladder optimization.
9. Full-system production acceptance and meaningful fresh held-out/live performance remain outstanding.93–95%accuracy is not certified. Final visual app/dashboard work remains separate.

Eric's next required action is explicit approval of the coordinated rollout in RELEASE_PLAN.md. This is an infrastructure/data-integrity acceptance stage, not a claim that performance completion is done. Historical evidence has been retained; destructive cleanup requires separate approval.
