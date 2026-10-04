# BTC15 current state and finish line

Updated: 2026-10-04 02:48 UTC. Transition: USER_APPLIED_EXACT_V2_QUALIFICATION_PATCH → BRIEF_FUNCTIONAL_QUALIFICATION_PASS → AWAIT_SEPARATE_PRODUCTION_APPROVAL.

This is the authoritative operational state document, on documentation-only branch ops/btc15-v2-qualification-20261003. The frozen runtime branches and PR #53 head are unchanged. This document and its evidence are committed transactionally. BUILT, QUALIFIED, qualification DEPLOYED, and production DEPLOYED are distinct.

## Authoritative identities

| Item | Exact identity |
|---|---|
| Candidate | BTC15_LADDER_COMPLETION_20261003_V2 |
| MAIN candidate | de4f3e20b8657eb8cfee91bd4e525c103b5bf513 |
| MAIN tree | 9103a8d16bfd84f7c13bb4fe82f4001c09697247 |
| V8.1 candidate | 60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1 |
| V8.1 tree | a082eb5486d32defba89010e9fa964394d1ce90d |
| Frozen manifest SHA256 | 9333eff3c5db1783a533d484b5c3dd14045f33d3a711729e084603dc86cb69f5 |
| Product authority | BTC15_PRODUCT_LOGIC_V2_20261003.md at frozen MAIN SHA |
| PR #53 | DRAFT / DO NOT DEPLOY; not merged; exact MAIN candidate head |
| Production MAIN baseline | abe212b513827c8cec28a2f64e0161e79296bd82 |
| Production V8.1 baseline | b05723ec622f901a05402ecf27f4d33505753ef1 |

The prior exact commit/tree/blob verification and accepted recovery audit remain authoritative. No recovery, ladder development, strategy change, threshold/weight change, historical sweep or capture work was repeated.

## Fixed sixteen-capability finish line

All sixteen capabilities are BUILT/DONE and deployed on the two isolated qualification services. All pass the frozen functional gate. “Qualified” below means brief functional qualification, not statistical performance qualification. Every row remains **NOT DEPLOYED TO PRODUCTION**.

LIVE means an observed live publication/readback. FIXTURE means the existing exact frozen deterministic/adversarial branch gate. A fixture is not represented as an observed market event. No accepted live EARLY/SCALP origin or EXIT was present in the saved before/after restart samples.

| Capability | BUILT / DONE | SHADOW-ONLY | QUALIFIED evidence | DEPLOYED |
|---|---|---|---|---|
| 1. Finished EARLY | YES | NO | LIVE eligibility/PASS reasons; FIXTURE qualified ENTER, immutable origin and recovery | Qualification only |
| 2. Independent FINAL | YES | NO | LIVE UP/DOWN probabilities, direction, confidence, publication ID, UNLOCKED/PASS; FIXTURE qualified call | Qualification only |
| 3. FINAL → EARLY helper/protection | YES | NO | FIXTURE explicit origin linkage, confirmation, strengthening, weakening, MIXED, opposition/flip, clearance and latched PROTECT; LIVE no false linkage without origin | Qualification only |
| 4. Actionable SCALP lifecycle | YES | NO | LIVE V8.1 eligibility/PASS/provenance; FIXTURE ENTER/HOLD/WATCH/CAUTION/PROTECT/EXIT and serial ownership | Qualification only |
| 5. Recovered profit protection | YES | NO | FIXTURE frozen +5¢ arm / 4¢ giveback; risk-policy evidence status preserved | Qualification only |
| 6. Latched EXIT | YES | NO | FIXTURE actual-bid terminal, recovery, no repricing, handoff/re-entry/reversal | Qualification only |
| 7. Executable prices | YES | NO | LIVE accepted timestamped executable book; FIXTURE immutable origin ask, strictly later same-contract/same-side bids and actual EXIT bid | Qualification only |
| 8. 5M CAUTION | YES | NO | FIXTURE causal weakening/conflict/pullback caution; no timer EXIT authority | Qualification only |
| 9. 3M guard rails | YES | NO | FIXTURE limited-runway caution; stronger PROTECT/EXIT preserved | Qualification only |
| 10. Flip-risk | YES | NO: informational | LIVE percentage and MODEL_INFORMATION_ONLY authority; FIXTURE cannot independently invoke EXIT | Qualification only |
| 11. PASS / UNAVAILABLE | YES | NO | LIVE fresh PASS and SOURCE_EXPIRED UNAVAILABLE; FIXTURE future/nonfinite/mismatched/stale fail-closed branches | Qualification only |
| 12. Permanent bounded journal | YES | NO | LIVE both lane publications, SQLite coverage readback, volume restart recovery and official pending-result receipts; FIXTURE event/checkpoint atomicity, origin/terminal recovery and bounds | Qualification only |
| 13. Exact Kalshi alignment | YES | NO | LIVE both lanes match official ticker, 900-second window and unchanged target before/after restart; FIXTURE target/identity mutation rejection | Qualification only |
| 14. BRTI ≤5 seconds | YES | NO | LIVE true source ages at publication and read; accepted quote/Coinbase freshness and causal timing; FIXTURE future/rollback rejection | Qualification only |
| 15. SIGNAL ONLY | YES | NO | LIVE signal_only=true, manual_execution_only=true; frozen UI/fixture enforcement | Qualification only |
| 16. NO ORDERS | YES | NO | LIVE orders=false; unchanged certified source/manifest, no order placement/routing/object or credential expansion introduced | Qualification only |

Additional classifications:

- **DONE:** exact deployment/configuration readback, frozen-byte startup verification before and after controlled restarts, required persistent storage, staged MAIN→V8.1 URL/CORS, source/official alignment, readable independent FINAL, journal readback/recovery, existing 91-test functional gate and official receipt-path functional check.
- **MISSING:** no blocking product implementation or brief functional qualification item identified. Live origin-linked protection/EXIT/handoff events and finalized live journal outcomes were not observed; their fixture coverage is explicit. Both lanes did receive and persist real official pending-result receipts. Production promotion approval and production V8.1 persistent storage remain outstanding.
- **SHADOW-ONLY / observational:** historical alternative exit policies and +8/+10/+15/+20/+30¢ target / −10¢ comparison-stop telemetry have no additional execution authority. Legacy shadow wrappers remain research/informational; they do not replace the active V2 product endpoint.
- **QUALIFIED:** exact V2 for brief signal-only functional/wiring operation, with the LIVE/FIXTURE distinction above. Not qualified for an 85%/90% reliability claim, FINAL calibration, profitable SCALP execution or increased signal frequency.
- **DEPLOYED:** exact V2 on qualification MAIN and V8.1 only. Production still runs the older frozen baseline.
- **REJECTED/SUPERSEDED:** V1 qualification obsolete; Ground Zero retired and both failed Oct. 3 intervals excluded. Unsupported EARLY automatic EXIT and fixed SCALP target/stop promotion remain absent. Rejected historical entry families retain their accepted audit dispositions. No supported additional EARLY alpha expansion was established (frozen completion outcome B).

## Actual qualification evidence

Evidence directory: [qualification/v2_live_20261004](qualification/v2_live_20261004). Raw JSON contains source timestamps, original responses, deployment IDs and fixture output. The original approval payload [BTC15_V2_RAILWAY_STAGED_20261003.json](qualification/BTC15_V2_RAILWAY_STAGED_20261003.json) is unchanged; SHA256 2c6165d819d7e2db8813b95af59d0490a0e3762e716ce8677e586112fc7fe5e7.

The user applied the exact 57-field / four-resource patch in Railway's dashboard. The old connector cancellation was an authorization-path failure, not a rejection of the candidate. No connector deployment attempt was repeated in this mission. Readback now shows the services/volumes LIVE and no pending environment patch.

Project noble-warmth / baea4e22-d004-4434-b2c5-81a7fbc05086; environment named production / 61775c5d-c583-4dfc-af41-f25578856fd9. Only the two isolated qualification services were restarted. Environment naming does not imply production service promotion.

| Lane | Service / ID | Deployed instance | Persistent volume |
|---|---|---|---|
| MAIN | btc15-v2-main-qualification / e6101c69-18df-4522-99d8-94e363ad8b92 | 49b15e63-fdf8-4dd6-9589-de222bbe5fdf; exact de4f3e20… | b6304c46-7027-4bfd-932d-94bb9c67da8e; btc15-v2-main-journal; 2,048 MB; iad; /data |
| V8.1 | btc15-v2-v81-qualification / 725e8200-656a-4576-a62a-0b84fedf9ffd | 39c95226-fff1-4f5f-8ce4-606c5e446a70; exact 60e6ebdd… | 97cc9dcd-ef90-495e-a1be-ffda31eac1b3; btc15-v2-v81-journal; 2,048 MB; iad; /data |

Both deployments were created 2026-10-04 02:29:13 UTC. Initial startup logs report FROZEN V2 IDENTITY PASS at 02:30:19. MAIN's controlled restart reported PASS at 02:37:40; V8.1 at 02:38:18. Restart reused the same images/deployment IDs; no rebuild or configuration change. Both services subsequently returned healthy HTTP 200.

Live source pins, start commands, variable-name sets and two volume configurations match the reviewed snapshot. OAuth redacts variable values; no secret values were requested or copied. The applied approval snapshot plus successful source connections, mounted-volume guard, journal recovery and rendered dashboard URL establish the relevant wiring. Both journal roots are /data/btc15_ladders_v2; lane files are main.sqlite3/main.json and v81.sqlite3/v81.json.

The served MAIN panel resolves V8.1 to https://btc15-v2-v81-qualification-production.up.railway.app/ladders. V8.1 responds HTTP 200 with Access-Control-Allow-Origin: * and Cache-Control: no-store. Existing frozen DOM/expiry fixtures passed.

### Official alignment and causal freshness

Both lanes matched official market KXBTC15M-26OCT032245-45, open 2026-10-04 02:30:00 UTC, close 02:45:00 UTC, target **84822.76**. Target, ticker and window were unchanged after restart. Independent official GET is saved in official_current.json.

| Lane/sample | BRTI age at publication / read | Quote age at publication / read | Coinbase age at publication / read |
|---|---|---|---|
| MAIN before restart | 1.292s / 3.800s | 0.075s / 2.583s | 1.242s / 3.750s |
| MAIN after restart | 2.580s / 4.046s | 0.081s / 1.547s | 0.541s / 2.007s |
| V8.1 before restart | 1.640s / 2.348s | 0.037s / 0.745s | 0.643s / 1.351s |
| V8.1 after restart | 2.016s / 2.334s | 0.039s / 0.357s | 2.160s / 2.478s |

MAIN's causal feature cutoff and health checks passed. V8.1 preserved qualified BRTI source time/owner epoch/sequence and contiguous accepted quote source/validation timestamps, market ID/ticker and executable book. All saved accepted samples had source times no later than publication and remained within source limits at read time. Expired MAIN responses correctly suppressed actionable guidance as UNAVAILABLE; no gate was loosened.

Independent FINAL before restart: UP 0.4834328815, DOWN 0.5165671185, DOWN preferred, UNLOCKED/PASS, final_status AVAILABLE. After restart: UP 0.2537132002, DOWN 0.7462867998, also independently readable. No EARLY origin existed, and early_origin_id remained null rather than being invented.

### Journal durability and denominator

| Lane | Pre-restart sampled sequence | Post-restart sequence / process writes | Persisted record count at process startup | Original contract first_at | Coverage observations before / after |
|---|---|---|---|---|---|
| MAIN | 22 | 94 / 14 | 80 | 1791081055.2781744, unchanged | 24 / 95 |
| V8.1 | 146 | 535 / 55 | 480 | 1791081018.6079752, unchanged | 156 / 538 |

The journal continued writing between initial readback and restart, explaining startup counts greater than the earlier samples. Persisted sequence minus new-process writes proves recovery; read-only SQLite coverage retained the original first_at and accumulated counts. MAIN's native epoch and V8.1's book epoch changed across process restarts, as expected. Both sampled queue depths/drops were zero. Active-origin and latched-terminal restoration are fixture-verified; no live active origin existed to test that branch during these restarts.

Both initial contract denominators correctly report quiet=true and MISSING_OR_PARTIAL because qualification began inside the window and included startup/restart gaps. These are not complete performance cohorts or manufactured PASS opportunities. Existing bounds remain queue16, record/view64KiB, SQLite512MiB, 30days/300,000events, coverage96contracts.

### Settlement path and existing fixtures

The official prior market KXBTC15M-26OCT032230-30 returned finalized / yes, settlement_ts 2026-10-04T02:30:07.213817Z, expiration_value 84822.76. That real receipt passed the exact frozen receipt parser and both lane processors into isolated temporary SQLite journals, then survived readback as AUTHORITATIVE / UP without creating an origin. This is a functional receipt-path check using a real official result, **not a live service journal receipt**.

The existing SettlementReader fixture verifies bounded GET-only lookup, finalized-only acceptance, exact contract/window, persistence and no repeated finalized lookup. During documentation work the contract closed naturally. Final live coverage readback at 02:47:44 UTC showed BOTH running services had fetched and persisted the official result: market_status=determined, result=no, expiration_value=84792.27, settlement_ts=null. MAIN received it at 02:45:12.661 and V8.1 at 02:45:19.058. Both correctly recorded PENDING_OR_NONBINARY with side=null because determined is not finalized. This directly proves the live GET → parser → writer → SQLite readback path and its refusal to invent an authoritative result. The new 02:45–03:00 contract was separately journaled. No idling or forced polling of the settlement worker was required, and no live finalized receipt is claimed. Scratch Python lacked requests for a proposed additional direct-reader invocation; the existing fixture and real receipt check were used without installing dependencies or changing runtime code.

Both local frozen-byte verifiers passed and the exact existing gate passed **91/91** again:

~~~sh
python btc15_verify_ladder_freeze_v2.py
python btc15_verify_ladder_freeze_v2.py --lane v81 --root ../v81
python -m unittest test_btc15_ladder_completion_v1 test_btc15_scalp_journal_v1 test_btc15_product_logic_v2 test_directional_position_manager_v1
~~~

This gate covers the immutable EARLY origin/helper sequence, independent FINAL fallback, SCALP actual ask/later bid, protection/overshoot/latched EXIT, serial handoff/re-entry/reversal, target/stop chronology, 5M/3M context, flip informational authority, future/stale/sequence rejection, checkpoint identity and durable atomicity. Its synthetic signals are not market observations. Prior exact-SHA hosted CI remains successful; no new broad test campaign was started.

## Production unchanged and next approval

Production MAIN deployment remains **6a6581ba-fc0a-4021-84c4-9c1896c4f179**. Production V8.1 remains **54a117aa-1809-4c56-8d32-190fbc5c1ce9**. Neither service was restarted, redeployed, reconfigured or given a new volume. No production changes are staged.

**Current blocker/next action: separate explicit production-promotion approval.** Brief V2 functional qualification passes; product logic remains frozen. The proposal is concrete but NOT STAGED, NOT APPROVED and NOT APPLIED:

[Exact production proposal](qualification/BTC15_V2_PRODUCTION_PROMOTION_PROPOSAL_20261004.json).

| Proposed resource | Exact production action requiring approval |
|---|---|
| Btc-15min-bot / ab28dca6-7bea-4956-bdb9-dbb7b4c74635 | Pin release/ladder-completion-20261003 to MAIN de4f3e20b8657eb8cfee91bd4e525c103b5bf513; use the already-qualified MAIN mount-guard/frozen-verifier/installer start command. Keep existing 10,000 MB /data volume 6ced6b1a-3755-4518-a240-c895e936d443 and its contents. Set BTC15_LADDER_DATA_ROOT=/data/btc15_ladders_v2 and BTC15_V81_LADDERS_URL=https://v81-live-diagnostics-production.up.railway.app/ladders. Remove BTC15_CAPTURE_ACTIVATION to keep retired capture disabled. |
| v81-live-diagnostics / 6025e83e-a41c-4e0a-8c16-f71120bd501b | Pin release/v81-ladder-completion-20261003 to V8.1 60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1; use the already-qualified V8.1 mount-guard/frozen-verifier/live-feed start command. Set BTC15_LADDER_DATA_ROOT=/data/btc15_ladders_v2 and PORT=8080. Remove BTC15_CAPTURE_ACTIVATION. |
| New production volume btc15-v81-ladder-journal-v2 | Create 2,048 MB in iad and mount /data on production V8.1 only. Production V8.1 currently has no persistent volume. Do not move either qualification volume or reuse its data as a new production denominator. |

Both proposed production services use RAILPACK, one iad replica, existing domains/port8080, /health, MAIN120s/V8.1 30s health timeout, ON_FAILURE10 as qualified. Preserve all other variables and credentials; no shared-variable/BRTI-owner changes. Qualification services/volumes remain unchanged. The proposal replaces the legacy MAIN inventory/preservation startup wrapper with the qualified frozen verifier command; it deletes no existing evidence.

Approval would touch production and cause deployment startup interruption. After explicit approval, stage only these three resources, review the exact pending scope, apply through the supported Railway confirmation path, verify frozen startup/source wiring and production journal durability, then update this document. Preserve current production deployment/configuration receipts and all volumes for rollback. PR #53 is not silently merged or undrafted.

## Permanent anti-drift rules

- **RECOVER BEFORE REBUILDING.** Check repository/history before declaring product behavior missing.
- Supporting infrastructure cannot redefine the product objective or move the fixed sixteen-capability finish line.
- The V2 completion certificate is authoritative. Strategy, thresholds, weights and ladder logic remain unchanged.
- Ground Zero is retired. Both failed Oct. 3 intervals stay excluded from scoring, training, tuning, candidate selection and validation.
- V1 qualification is obsolete. Its source/configuration must not be reused.
- No multi-day or multi-week pre-deployment performance campaign is required. Function and live wiring are distinct from future statistical performance.
- Do not claim EARLY 85%/90% reliability, FINAL calibration, profitable SCALP execution or increased frequency from this qualification.
- **SIGNAL ONLY / NO ORDERS / NO AUTOMATED EXECUTION.** Guidance assumes no actual manual fill.
- Update this document and supporting evidence in one commit at each major transition. A build is not deployment; qualification is not production promotion.
