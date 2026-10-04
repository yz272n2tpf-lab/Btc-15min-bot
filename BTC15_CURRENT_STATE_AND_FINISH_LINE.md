# BTC15 current state and finish line

Updated: 2026-10-04T05:00:35.182260+00:00. Transition: VERIFIED_PRODUCTION_UNCHANGED → OFFLINE_V2_SCORING_BRIDGE_VERIFIED → PRODUCTION_SCORING_BLOCKED.

**V2 production is deployed and serving. Do not redeploy or repeat qualification.** The former STAGED / AWAIT APPROVAL state at documentation commit `677200b3ad1a40c555e50394b485d6445887a909` is superseded by the user's dashboard application of patch `bac367fe-44f2-4d94-b5e2-d2e623340f46` and the successful live readbacks below. Deployment initiation was not accepted as completion. No assistant deployment, restart, runtime edit, threshold change or order was performed.

This is the authoritative operational document on `ops/btc15-v2-qualification-20261003`. [Consolidated operating checklist](BTC15_V2_OPERATING_CLOSEOUT_20261004.md) contains every VERIFIED / PENDING / BLOCKED item and exact next action. [Receipts and evidence](qualification/v2_production_20261004) accompany this transition. The [unchanged pre-deployment state](qualification/v2_production_20261004/previous_state_677200b.md) is historical evidence only; its old approval/deployment instructions must not be replayed.

## Exact deployed identities

Candidate: `BTC15_LADDER_COMPLETION_20261003_V2`. Project `baea4e22-d004-4434-b2c5-81a7fbc05086`; environment `61775c5d-c583-4dfc-af41-f25578856fd9` (production).

| Lane | Exact SHA | Production deployment | Railway SUCCESS at UTC |
|---|---|---|---|
| MAIN | de4f3e20b8657eb8cfee91bd4e525c103b5bf513 | ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa | 2026-10-04 04:13:47.294 |
| V8.1 | 60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1 | 2051e772-bd39-4dea-a77d-52fea0a07c02 | 2026-10-04 04:13:35.525 |

MAIN service `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`; V8.1 service `6025e83e-a41c-4e0a-8c16-f71120bd501b`. Both source pins and frozen runtime branch refs were read back at these exact SHAs. The frozen manifest remains `9333eff3c5db1783a533d484b5c3dd14045f33d3a711729e084603dc86cb69f5`. Product authority is `BTC15_PRODUCT_LOGIC_V2_20261003.md` at frozen MAIN. PR #53 remains draft/unmerged; it is not the deployment trigger or a request to redeploy. The previous baseline SHAs are historical, not current production.

Startup logs contain `FROZEN V2 IDENTITY PASS | main | SIGNAL ONLY | NO ORDERS` at 04:13:43.522706327Z and the V8.1 equivalent at 04:13:32.229576236Z. The exact reviewed volume-guarded start commands are applied. MAIN's existing volume `6ced6b1a-3755-4518-a240-c895e936d443` (10,000 MB) and V8.1's applied volume `d5eeafca-e0fc-42f0-b7d1-4705907720c6` (2,048 MB) are mounted at `/data`. Mounted journal writing and SQLite coverage readback are verified; no production restart was performed to repeat the earlier qualification durability test.

## Production operation — verified scope

At the saved readback around **2026-10-04 04:18:46–47 UTC**, both health, `/ladders` and `/ladders/coverage` returned HTTP 200. MAIN serves the frozen panel with the production V8.1 URL substituted exactly: `https://v81-live-diagnostics-production.up.railway.app/ladders`. V8.1 allows cross-origin reads and uses no-store. This verifies served dashboard wiring; it does not claim a new visual browser acceptance test.

Both lanes and the independent official Kalshi response matched `KXBTC15M-26OCT040030-30`, open 04:15 UTC, close 04:30 UTC, fixed target **84804.99**. BRTI ages at publication/read were MAIN **2.462/4.698s**, V8.1 **1.773/2.694s**. Quote and Coinbase source timestamps were causal and fresh in those samples. These are time-stamped point checks, not a claim of continuous uptime or freshness. MAIN's independent FINAL was AVAILABLE / UNLOCKED / PASS, UP 0.4899765966, DOWN 0.5100234034; no EARLY origin was invented. Both lanes asserted signal_only=true, manual_execution_only=true, orders=false.

## Fixed sixteen-capability finish line

All sixteen capabilities remain BUILT/DONE and briefly functionally QUALIFIED, and are now **DEPLOYED TO PRODUCTION** at the exact frozen versions. The original qualification evidence and 91/91 frozen functional gate were reused, not repeated. LIVE below denotes prior observed qualification publications/readback unless the production section above explicitly names production evidence. FIXTURE is deterministic branch evidence, not a market event. Live origin-linked protection/EXIT/handoff were not observed in saved production samples.

| Capability | BUILT / DONE | SHADOW-ONLY | QUALIFIED evidence | CURRENTLY V2 PRODUCTION DEPLOYED |
|---|---|---|---|---|
| 1. Finished EARLY | YES | NO | LIVE eligibility/PASS reasons; FIXTURE qualified ENTER, immutable origin and recovery | YES — exact frozen source |
| 2. Independent FINAL | YES | NO | LIVE UP/DOWN probabilities, direction, confidence, publication ID, UNLOCKED/PASS; FIXTURE qualified call | YES — exact frozen source |
| 3. FINAL → EARLY helper/protection | YES | NO | FIXTURE explicit origin linkage, confirmation, strengthening, weakening, MIXED, opposition/flip, clearance and latched PROTECT; LIVE no false linkage without origin | YES — exact frozen source |
| 4. Actionable SCALP lifecycle | YES | NO | LIVE V8.1 eligibility/PASS/provenance; FIXTURE ENTER/HOLD/WATCH/CAUTION/PROTECT/EXIT and serial ownership | YES — exact frozen source |
| 5. Recovered profit protection | YES | NO | FIXTURE frozen +5¢ arm / 4¢ giveback; risk-policy evidence status preserved | YES — exact frozen source |
| 6. Latched EXIT | YES | NO | FIXTURE actual-bid terminal, recovery, no repricing, handoff/re-entry/reversal | YES — exact frozen source |
| 7. Executable prices | YES | NO | LIVE accepted timestamped executable book; FIXTURE immutable origin ask, strictly later same-contract/same-side bids and actual EXIT bid | YES — exact frozen source |
| 8. 5M CAUTION | YES | NO | FIXTURE causal weakening/conflict/pullback caution; no timer EXIT authority | YES — exact frozen source |
| 9. 3M guard rails | YES | NO | FIXTURE limited-runway caution; stronger PROTECT/EXIT preserved | YES — exact frozen source |
| 10. Flip-risk | YES | NO: informational | LIVE percentage and MODEL_INFORMATION_ONLY authority; FIXTURE cannot independently invoke EXIT | YES — exact frozen source |
| 11. PASS / UNAVAILABLE | YES | NO | LIVE fresh PASS and SOURCE_EXPIRED UNAVAILABLE; FIXTURE future/nonfinite/mismatched/stale fail-closed branches | YES — exact frozen source |
| 12. Permanent bounded journal | YES | NO | LIVE both lane publications, SQLite coverage readback, volume restart recovery and official pending-result receipts; FIXTURE event/checkpoint atomicity, origin/terminal recovery and bounds | YES — exact frozen source |
| 13. Exact Kalshi alignment | YES | NO | LIVE both lanes match official ticker, 900-second window and unchanged target before/after restart; FIXTURE target/identity mutation rejection | YES — exact frozen source |
| 14. BRTI ≤5 seconds | YES | NO | LIVE true source ages at publication and read; accepted quote/Coinbase freshness and causal timing; FIXTURE future/rollback rejection | YES — exact frozen source |
| 15. SIGNAL ONLY | YES | NO | LIVE signal_only=true, manual_execution_only=true; frozen UI/fixture enforcement | YES — exact frozen source |
| 16. NO ORDERS | YES | NO | LIVE orders=false; unchanged certified source/manifest, no order placement/routing/object or credential expansion introduced | YES — exact frozen source |


Prior qualification detail remains in [qualification/v2_live_20261004](qualification/v2_live_20261004) and the historical state snapshot. Deployment does not establish statistical reliability, FINAL calibration, SCALP profitability or increased frequency.

## Actual V2 recording start and scoring status

| Lane | First production journal observation UTC | Initial contract |
|---|---|---|
| MAIN | 2026-10-04 04:14:21.909025 | KXBTC15M-26OCT040015-15 |
| V8.1 | 2026-10-04 04:13:31.705281 | KXBTC15M-26OCT040015-15 |

These are lane-specific recording starts, not complete-window statistical cohort starts. At the saved read, the startup 04:00–04:15 window and the 04:15–04:30 window were MISSING_OR_PARTIAL in both lanes. Their data remain separate from complete cohorts, qualification, older versions and missing outcomes. MAIN had an authoritative finalized DOWN receipt for the startup contract; V8.1's sampled receipt remained pending. No pending result is promoted to settled.

**Recording is VERIFIED; end-to-end V2 production scoring is BLOCKED.** The [read-only scoring bridge](ops/btc15_v2_scoring/README.md) is now implemented and passes **11/11 focused offline tests**, including a second later contract without schema repair. It reuses the unchanged established scorer classifiers and retains V2 official finalized receipts; it does not fabricate old native JSONL/60-sample closeout semantics. Snapshot acquisition, exact source/service/deployment/build checks, raw event hashes, immutable origins, separate FINAL/helper behavior and later same-side bid chronology are covered. Fixtures remain explicitly separate and cannot be marked production VERIFIED.

No full production SQLite snapshot pair was acquired. A bounded scoring-coverage read at **2026-10-04 04:48:43–48 UTC** showed four observed windows in each lane, **all missing/partial**. MAIN had three authoritative receipts; V8.1 had two, with its 04:30–04:45 result still pending in that sample. None is a proven complete scoreable contract. Coverage summaries are not event snapshots. No production accuracy, P&L or calibration result was calculated, and the exact complete V2 production cohort start remains PENDING.

Evidence: [bridge verification and acceptance status](qualification/v2_scoring_bridge_20261004). **One precise next action:** acquire both detached production SQLite backups and generated receipts through the existing authorized runtime file/exec route, then run the committed bridge once. Existing-account sign-in is required for that route; no new authentication attempt, exporter, account, credential or alternate route was created during this scoring mission. If the snapshots still contain only partial windows, keep BLOCKED with those missing reasons. No deployment, strategy change, cleanup or new multi-day pre-launch requirement is authorized by this step.

## Alerts, cleanup and handoff

The existing daily scorecard and hourly integrity watch are enabled and their saved prompts are V2-aligned. They were not duplicated or rewritten. The existing daily task accepted one immediate run request after the deployed-state handoff was committed; its schedule and prompt were unchanged. Execution completion and notification delivery remain PENDING; see `alert_test_request.json` in the evidence directory and the consolidated checklist. Do not create a duplicate or repeat the test request.

Archive cleanup is BLOCKED at shared-browser authentication. The user's existing Codespace is reported running, but the one bounded access check still required GitHub sign-in. The Railway UI also required the user's existing-account sign-in. No more authentication attempts or alternate routes were tried. No Codespace, service, deployment, volume, credential or evidence was retired/deleted. All 33 old candidate service UUIDs still exist among 53 current services; that does not imply all are running or that all should retire. Six volumes remain. Current bills and all-platform totals are unverified; the old $52.43/$56.26 numbers were projected Railway CPU+RAM only.

Both qualification services (`e6101c69-18df-4522-99d8-94e363ad8b92`, `725e8200-656a-4576-a62a-0b84fedf9ffd`) and their volumes (`b6304c46-7027-4bfd-932d-94bb9c67da8e`, `97cc9dcd-ef90-495e-a1be-ffda31eac1b3`) remain protected until an explicit archive-verified cleanup decision.

## Permanent anti-drift rules

- SIGNAL ONLY. MANUAL EXECUTION ONLY. NO ORDERS. Guidance assumes no actual manual fill.
- Preserve both frozen runtime branches and exact deployed SHAs. Documentation commits must not trigger a redeployment.
- Recover existing packages before building. No Ground Zero redevelopment, threshold/weight/ladder tuning, strategy changes, new exporter or repeated qualification.
- Ground Zero and both failed Oct. 3 intervals stay excluded from scoring, tuning and validation. Older Rescue V2 is a different system.
- Keep incomplete windows, missing outcomes, qualification, fixtures and older versions outside the complete V2 production denominator; disclose each exclusion.
- Bounded journals need a verified consistent snapshot and compatible offline scorer before claiming a working scorecard. Do not mistake logging, a task run request or projected savings for completed scoring, delivery or billing evidence.
- Preserve uncommitted Codespace work, unique RAM/ephemeral evidence, all volumes and credentials before any specifically reviewed retirement. Do not replay the old 33-service list.
- Stop before unreviewed production changes. No additional multi-day pre-launch requirement.
- Update this authoritative state and its evidence together at each material transition.
