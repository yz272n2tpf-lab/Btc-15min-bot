# BTC15 completion audit — baseline before corrections

Baseline main: 662873c41fde364a994b6a22dc0bb18f21d43fdc. Owner: 98cb9e538d584ad326d19af10924960dbff42672. Audit date: 2026-09-23 UTC. SIGNAL ONLY / NO ORDERS. This is a release blocker register, not production acceptance.

## Scope and evidence boundaries

Inspected the repository inventory, production launch closure including decoded installer payloads, all 43 Railway service configurations and serving deployment revisions, variable names, selected source revisions, baseline regressions, live production/owner/research logs and published scorecards. Raw Railway variable values/reference expressions are not exposed by the connector. Historical Git object retrieval is incomplete where network policy blocks lazy fetch; connected GitHub retrieved targeted files. Do not infer that every historical branch has been executed or every dependency resolved.

Accepted external evidence: obsolete multi-hop owner credentials through a deleted service were replaced with references directly to current production bot credentials; no key exposure/rotation; owner cold-start SUCCESS, PRIMARY_OK, clean=True, reported age about 1.6s. Browser authentication cancelled and must not be retried. Main uses shared=1, legacy_shared_http. Owner poll 2s, qualification 5s, 429 backoff 30s. Prior staged handoff +2.849s is established.

## Dependency map

Kalshi GET authentication → exact KXBTC15M discovery → staged eligible snapshot captured before observe advances staging → official open/close selection → fixed official target → ticker-bound quote provenance → Coinbase/BTC rolling features and target-aware fair model → BRTI authority/final60 → parallel EARLY / FINAL / SCALP gates → publication gates and manual action display → CSV/state/rescue/protection → external scorecards.

Main launch: INLINE_SCALP_DIAG_V2 → installer/embedded runner and dashboard → full_validation → rescue/parity supervisor + final-position-protection → rescue supervisor → core bot. Dashboard additionally fetches v81-live-diagnostics /state; this service is currently a real production dependency despite its diagnostic name. Scalp-move-shadow-v1 owns generalized serial research data, consumed by ladder/entry/exit/reversal evaluations. Shared BRTI owner is a separate revision/service. Consumers must never fall back to authenticated upstream calls when shared mode is enabled.

Railway service IDs, branches, deployed revisions, domains, entrypoints, mounts and variable names are in railway_inventory.md. Config names such as BTC15_DASH_V13_Z1..Z5 require launch-payload parity verification before replacing environment configuration. Main /data persists; several scorecards and the clean collector have no volume and restart with new-run/no-restore behavior. Child process death is reported but supervisors do not uniformly restart it. HTTP health is not full data readiness.

## Complete known blocker register before source changes

1. Owner strips CF source timestamps and stamps successful polling time. Reported age proves receipt liveness, not source freshness. Repeated old responses can appear fresh. Preserve source time, reject malformed/future/conflicting data and never relax 5s.
2. Legacy consumer omits source_ts_ms; parity dereferences it and live logs show KeyError/WAIT. Align owner, consumer and parity schema together.
3. Legacy collector ingests one latest point per 2s, not true publication history. Live closeouts repeatedly failed at 30/60. Recover actual per-second publications from the same owner response; no interpolation or extra upstream consumer polling.
4. Exactly-one-owner requirement fails: v81-final-isolated-test, v81-live-diagnostics and scalp-move-shadow-v1 have live direct BRTI activity. v81-immutable-test has zero CPU/memory across61 samples in the refreshed one-hour window, but its restart entrypoint remains a latent owner. The isolated-test park variable is not read by its loop. Preserve useful diagnostic/scalp behavior while migrating ownership; parking a dependent service alone breaks production.
5. Owner 429 instability remains: saved heartbeat 947/969 successes, 22 429 errors; a later62-heartbeat sample reached143.871s (53/62 reported clean); latest1,666/1,693 upstream successes and27HTTP429s. These are request/receipt statistics, not true-source availability. Attribute combined traffic before selecting cadence; preserve 2/5/30 settings.
6. Main baseline regressions: 168 run, 167 pass, 1 failure. Canary path scanner does not recognize newly frozen readonly training artifact and reports it before the intended unreviewed-child failure. Preserve immutable training input; do not redirect it to mutable runtime data.
7. Publication/scoring mismatch: FINAL collector counts raw ready/anchor state while UI additionally requires parity/source freshness. Live aggregate 263/278=94.6043%, 278/595=46.7227% coverage, mean 5.1445 min left, mean ask92.016c/median92.8c. This is mixed-revision raw-anchor evidence, not proof of qualified published live accuracy. A retained failed DOWN anchor had fair .92483 / ask .81 and eventual UP.
8. EARLY newest 7–10min slice: 0 calls/95 completed slices (96 eligible observed), not whole 2–10min policy. Historical protected 20/22 and fresh OOS P45 15/20 are different cohorts, not combinable. Need complete frozen forward entry odds/timing/MFE/MAE/FINAL relationship.
9. Three-ladder incremental contribution, common-universe overlap and calibration not established on current qualified data. Do not tune gates on contaminated or previously opened holdouts. Numeric flip-risk candidate failed its forward review; retain qualitative protection, do not present unvalidated probability.
10. SCALP serial research is not equivalent to main V8.1 display; main says no V8.1 stop rule connected. Both directional opportunity and existing profit-protection must be preserved. Holdout outcome metrics use signal/eligible-contract denominators and fees=false; cannot assert whole-market coverage or realized net profitability. Entry-profit/reversal services show CRASHED deployment state despite retained historical result logs.
11. Downstream target/publication readiness trails staged handoff: observed target-ready delays include 24.882s,27.165s,17.673s,13.074s,4.602s. Handoff timing is not full readiness. Preserve staged ordering; do not synthesize target while official target is missing.
12. Restart/recovery incomplete: owner restartPolicy NEVER, memory-only data/history; non-durable research evidence; supervisors can leave child dead. Need local fault tests plus approved production restart acceptance.
13. CI triggers only old diagnostic branches; main/PR acceptance does not run whole regression suite. Add an offline comprehensive check without starting bot/network/order paths.
14. Historical syntax defects in parked scripts and old URLs remain in repository. Classify instead of blindly deleting. Raw references inaccessible: cannot certify ZERO dead/temp dependencies across secrets. Externally confirmed direct owner credential repair closes that specific chain only.
15. Several consecutive staged rollovers are observed, but no corrected whole-system forward run exists. Clean cold start, interruption/recovery, publication/scoring and current-source 5s stability must be accepted together after approved coordinated deployment.

## Three ladders: preserve definitions

These are parallel action families, not three interchangeable votes. FINAL uses preferred fair>=.90, <=8min left, target-side agreement, distance>=75 above6min otherwise50, distance/range5>=1 plus authority/quote/publication gates. It contributes eventual outcome anchoring; high asks and target proximity create coverage/timing tradeoffs. EARLY uses preferred side, ask<=.45, fair>=.75, edge>=.08,2–10min, abs gap>=25 plus safety gates: its unique purpose is affordable entry ahead of FINAL. SCALP/reversal is path-dependent, both directions; deployed V8.1 diagnostic entry band30–45c must be distinguished from core strong-scalp gates and newer serial research. Serial research protected candidate: aligned BTC30>=15, >=120s left, no price filter, +5c arm/4c giveback, no pre-arm stop; subsequent ladder slots require prior EXIT, not just a later row. No threshold/weight change is justified by this audit.

Historical SCALP holdout context: RUNNER_10_4 237 signals/160 baseline contracts,70.04% positive exit, mean entry49.31c/exit gain8.76c; PROTECT_5_2 301/160,74.086%,49.008c/9.263c. Reversal113signals/84eligible contracts,+10c58.407%,meanentry50.303c,MAE−5.811c,MFE18.856c; conditional protected exits50,72% positive;58same/55opposite-side. These are frozen research reports, not authorized replacement strategy. Developing-move forward8signals/7contracts had zero +10/+20 successes: do not promote.

## Cleanup decision

KEEP: main bot, durable shared owner, useful live diagnostic/scalp data owners until migrated, immutable model inputs, persistent evidence, required scoring/publication components. PARK: legacy/isolated research execution after dependency migration is proven; retain files and historical evidence. REMOVE LATER: obsolete services/domains and dead scripts only after production acceptance and explicit destructive approval. No deletion authorized or performed.

## Coordinated correction scope and acceptance

First candidate: timestamp-preserving owner/history, matching strict legacy consumer, both history consumers, exact readonly canary training allowance, regressions and CI. No strategy, fixed target, timing or settlement changes. Further candidates require duplicate-owner migration, restart supervision, publication-qualified scoring and frozen forward acceptance. Owner-first schema rollout must be approved; old owner cannot satisfy new strict consumer. Do not merge/deploy a consumer-only change. Deployment approval is required only after concrete tested diffs are ready. No production restart, variable mutation or deploy performed by this audit.

## Evidence qualification details recorded before promotion

Reproducing the Sep6 union script gives FINAL30/56,EARLY4/56 and SCALP0, but the committed scalp rows after its17-row cutoff cover Sep4–5, not Sep6. The zero cannot establish SCALP contribution; the three-way union is not a valid common-universe result.

The entry-profit reviewer at14ef7cf calls freeze.audit(policy_grid) during each refreshed ladder.analyze(rows). freeze.audit re-selects roles from validation summaries; changing source hashes and role choices are visible across hourly logs. Preserve those reports as research and require an immutable cohort/policy manifest before claiming a frozen holdout. This refines blocker9(scoring/split integrity); no strategy promotion or retuning was performed.
