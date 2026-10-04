# BTC15 current state and finish line

Updated: 2026-10-04 00:12 UTC (October 3, 20:12 New York). Transition: **USER_APPROVED_EXACT_V2_PAYLOAD → RAILWAY_COMMIT_CONFIRMATION_CANCELLED**.

This is the authoritative operational state document. It lives on documentation-only branch `ops/btc15-v2-qualification-20261003`; the frozen runtime branches and PR #53 head remain unchanged. Update this document and its supporting approval snapshot in one Git commit at every major qualification/deployment transition. A successful build is not live qualification, and qualification is not production deployment.

## Authoritative identities

| Item | Exact identity |
|---|---|
| Candidate | `BTC15_LADDER_COMPLETION_20261003_V2` |
| MAIN candidate | `de4f3e20b8657eb8cfee91bd4e525c103b5bf513` |
| MAIN tree | `9103a8d16bfd84f7c13bb4fe82f4001c09697247` |
| V8.1 candidate | `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1` |
| V8.1 tree | `a082eb5486d32defba89010e9fa964394d1ce90d` |
| Frozen manifest SHA256 | `9333eff3c5db1783a533d484b5c3dd14045f33d3a711729e084603dc86cb69f5` |
| Product authority | `BTC15_PRODUCT_LOGIC_V2_20261003.md` at the frozen MAIN commit |
| PR #53 | DRAFT / DO NOT DEPLOY; open, not merged; head remains exact MAIN candidate |
| Existing production MAIN baseline | `abe212b513827c8cec28a2f64e0161e79296bd82` |
| Existing production V8.1 baseline | `b05723ec622f901a05402ecf27f4d33505753ef1` |

The exact commit/tree identities were read from GitHub. Local manifest-covered files plus manifest/verifier were compared to their Git blobs: 31 MAIN files and 12 V8.1 files match. The existing state-document path was checked in both complete candidate trees and MAIN candidate path history before creating this document. The accepted recovery/audit and frozen certificate were reused; no ladder research or development was reopened.

## Fixed sixteen-capability finish line

Statuses below concern **V2**, not the older production baseline. “Offline PASS” means the exact frozen functional/adversarial gate passed; it does not imply every branch has occurred live.

| Capability | BUILT / DONE | SHADOW-ONLY | Offline qualified | Live QUALIFIED | V2 DEPLOYED to production | Frozen scope / limitation |
|---|---|---|---|---|---|---|
| 1. Finished EARLY | YES | NO | PASS | PENDING | NO | Frozen entry gates and origin; outcome B for unsupported additional alpha expansion. |
| 2. Independent FINAL | YES | NO | PASS | PENDING | NO | Own direction, probability, confidence/lock and original timing. |
| 3. FINAL → EARLY helper/protection | YES | NO | PASS | PENDING | NO | Immutable linkage, confirmation/MIXED/opposition/flip, latched PROTECT; unsupported automatic EARLY EXIT remains absent. |
| 4. Actionable SCALP lifecycle | YES | NO | PASS | PENDING | NO | ENTER/HOLD/WATCH/CAUTION/PROTECT/EXIT; serial ownership. |
| 5. Recovered profit protection | YES | NO | PASS | PENDING | NO | Frozen 5¢ arm / 4¢ giveback risk policy; no statistical performance qualification. |
| 6. Latched EXIT | YES | NO | PASS | PENDING | NO | Actual observed EXIT and predecessor survive checkpoint recovery. |
| 7. Executable price semantics | YES | NO | PASS | PENDING | NO | Original ask, strictly later same-side accepted bids, actual-bid EXIT; no fill claims. |
| 8. 5M CAUTION | YES | NO | PASS | PENDING | NO | Existing deterioration/conflict context; no timer EXIT authority. |
| 9. 3M guard rails | YES | NO | PASS | PENDING | NO | Limited-runway CAUTION; stronger existing states preserved. |
| 10. Flip-risk | YES | NO | PASS | PENDING | NO | Active informational output only; no automatic exit threshold. |
| 11. PASS / UNAVAILABLE | YES | NO | PASS | PENDING | NO | Qualified insufficient edge versus unavailable/stale/inconsistent evidence. |
| 12. Permanent bounded journal | YES | NO | PASS | PENDING | NO | Both lane implementations, atomic event/checkpoint, coverage denominator, official settlement receipt path. |
| 13. Exact Kalshi alignment | YES | NO | PASS | PENDING | NO | Official ticker/900-second window and immutable official target. |
| 14. BRTI ≤5 seconds | YES | NO | PASS | PENDING | NO | True source age, causal cutoff and read-time expiry; no future observations. |
| 15. SIGNAL ONLY | YES | NO | PASS | PENDING | NO | Guidance, UI and records; no assumed manual fill. |
| 16. NO ORDERS | YES | NO | PASS | PENDING | NO | No placement, routing, order objects or automated execution added. |

Additional classifications:

- **SHADOW-ONLY / telemetry:** descriptive historical alternative exit policies and the +8/+10/+15/+20/+30¢ target / −10¢ comparison-stop analysis are not promoted execution policies. Current telemetry is recorded; it has no extra automatic exit authority. Flip-risk is active informational context, not a missing feature.
- **MISSING operational evidence:** actual Railway volume provisioning for qualification, live V2 wiring observations, live journal readback, restart durability and official-settlement receipt-path verification. No product logic is reclassified as missing.
- **REJECTED/SUPERSEDED:** V1 qualification configuration is obsolete and its 19 pending changes were cleared. Historical rejected families retain their accepted audit dispositions. Unsupported EARLY automatic EXIT, added fixed SCALP targets/stops and statistical performance claims were not introduced.
- **QUALIFIED:** exact offline gate only. Live qualification is PENDING.
- **DEPLOYED:** V2 has never deployed to either qualification service or production. Both qualification services currently have `latestDeployment=null`.

## Completed exact offline gate

Both frozen verifiers passed. The exact focused suite passed **91/91** on this mission, including existing local recovery and causal/adversarial branches:

```sh
python btc15_verify_ladder_freeze_v2.py
python btc15_verify_ladder_freeze_v2.py --lane v81 --root ../v81
python -m unittest test_btc15_ladder_completion_v1 test_btc15_scalp_journal_v1 test_btc15_product_logic_v2 test_directional_position_manager_v1
```

Local invocation used the primary Python 3.12 runtime and MAIN/V8.1 source directories. The supporting snapshot records the exact invocation output. Existing hosted broad CI for exact MAIN SHA was independently read back as completed/success: https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/37158456627 . No extra historical sweep or new test laboratory was created.

The local SQLite close/reopen tests prove local checkpoint behavior. They do **not** prove Railway volume durability. The 16 capabilities are present in the unchanged frozen bytes; passing tests do not enlarge that certificate's scope.

## Concrete Railway approval payload

Project `noble-warmth` / `baea4e22-d004-4434-b2c5-81a7fbc05086`.
Environment is named `production` / `61775c5d-c583-4dfc-af41-f25578856fd9`, but this proposal touches only the isolated qualification services listed below. It does not promote the candidate or modify the production MAIN/V8.1 services.

| Lane | Service / ID | Pinned candidate | Persistent volume to provision |
|---|---|---|---|
| MAIN | `btc15-v2-main-qualification` / `e6101c69-18df-4522-99d8-94e363ad8b92` | `de4f3e20b8657eb8cfee91bd4e525c103b5bf513` | `btc15-v2-main-journal` / `b6304c46-7027-4bfd-932d-94bb9c67da8e`; 2,048 MB; iad; /data |
| V8.1 | `btc15-v2-v81-qualification` / `725e8200-656a-4576-a62a-0b84fedf9ffd` | `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1` | `btc15-v2-v81-journal` / `97cc9dcd-ef90-495e-a1be-ffda31eac1b3`; 2,048 MB; iad; /data |

Both services are pinned using Railway's `source.commitSha`; branch pushes cannot advance those pins. Repository: `yz272n2tpf-lab/Btc-15min-bot`. MAIN branch is `release/ladder-completion-20261003`; V8.1 branch is `release/v81-ladder-completion-20261003`.

Two small isolated volumes are necessary because neither qualification lane had persistent storage and production's attached MAIN volume cannot be shared between running services. No existing volume is resized, moved, deleted or reused. Journal root on each is `/data/btc15_ladders_v2`, containing `main.sqlite3` / `main.json` or `v81.sqlite3` / `v81.json`. Existing journal bounds are unchanged: 512 MiB SQLite page cap per lane, 30 days / 300,000 events, queue 16, 64 KiB record/view cap.

Production MAIN already has its separate 10,000 MB `/data` volume `6ced6b1a-3755-4518-a240-c895e936d443`. Production V8.1 still has no volume. Its final storage attachment/promotion remains a separately approved production transition; qualification storage does not falsely certify production durability.

Public domains already allocated to the **empty, never-deployed** qualification services:

- MAIN: `https://btc15-v2-main-qualification-production.up.railway.app`
- V8.1 ladder endpoint: `https://btc15-v2-v81-qualification-production.up.railway.app/ladders`

Railway rejected public-domain creation for staged-only services. The preparation therefore created empty service shells and domains without a source/build/deployment, then staged the source, storage, variables and startup configuration. No application process was started. The abandoned staged-only shell entries were removed before final review.

### Variables to apply

Only these service-scoped variables will be set. There are no shared-variable changes. `${{...}}` expressions are Railway references to existing configuration/credentials; secret values were not retrieved or copied into this document. Reference rendering is verified after approved deployment without printing credentials. No Ground Zero capture activation is configured.

| Variable | MAIN qualification | V8.1 qualification |
|---|---|---|
| `BTC15_BRTI_GATEWAY_URL` | `${{Btc-15min-bot.BTC15_BRTI_GATEWAY_URL}}` | Not set |
| `BTC15_BRTI_SHARED_URL` | `${{Btc-15min-bot.BTC15_BRTI_SHARED_URL}}` | `${{v81-live-diagnostics.BTC15_BRTI_SHARED_URL}}` |
| `BTC15_BRTI_TRANSPORT` | `${{Btc-15min-bot.BTC15_BRTI_TRANSPORT}}` | `${{v81-live-diagnostics.BTC15_BRTI_TRANSPORT}}` |
| `BTC15_DASH_V13_Z1` | `${{Btc-15min-bot.BTC15_DASH_V13_Z1}}` | Not set |
| `BTC15_DASH_V13_Z2` | `${{Btc-15min-bot.BTC15_DASH_V13_Z2}}` | Not set |
| `BTC15_DASH_V13_Z3` | `${{Btc-15min-bot.BTC15_DASH_V13_Z3}}` | Not set |
| `BTC15_DASH_V13_Z4` | `${{Btc-15min-bot.BTC15_DASH_V13_Z4}}` | Not set |
| `BTC15_DASH_V13_Z5` | `${{Btc-15min-bot.BTC15_DASH_V13_Z5}}` | Not set |
| `BTC15_ENABLE_INFORMATION_EXPORT` | `1` | Not set |
| `BTC15_INLINE_SCALP_V1` | `${{Btc-15min-bot.BTC15_INLINE_SCALP_V1}}` | Not set |
| `BTC15_KALSHI_QUOTE_PROVENANCE_CANARY` | `1` | Not set |
| `BTC15_LADDER_DATA_ROOT` | `/data/btc15_ladders_v2` | `/data/btc15_ladders_v2` |
| `BTC15_USE_SHARED_BRTI` | `1` | `1` |
| `BTC15_V81_LADDERS_URL` | `https://btc15-v2-v81-qualification-production.up.railway.app/ladders` | Not set |
| `KALSHI_KEY_ID` | `${{Btc-15min-bot.KALSHI_KEY_ID}}` | `${{v81-live-diagnostics.KALSHI_KEY_ID}}` |
| `KALSHI_PRIVATE_KEY_B64` | `${{Btc-15min-bot.KALSHI_PRIVATE_KEY_B64}}` | `${{v81-live-diagnostics.KALSHI_PRIVATE_KEY_B64}}` |
| `PORT` | `8080` | `8080` |
| `PYTHONUNBUFFERED` | `1` | `1` |
| `V81_DIAG_LIVE` | Not set | `1` |

### Start commands and deployment settings

MAIN:

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && python btc15_verify_ladder_freeze_v2.py --lane main && exec python -u btc15_information_install_v1.py'
```

V8.1:

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && python btc15_verify_ladder_freeze_v2.py --lane v81 && exec python -u v81_30_45_live_feed.py'
```

These commands fail before runtime startup if the expected Railway volume metadata is absent, verify frozen lane bytes, then run the existing frozen entry point. No runtime source, strategy threshold or weight changes.

Both: RAILPACK, one replica in iad, port 8080, healthcheck `/health`, restart `ON_FAILURE` with 10 retries (matching the frozen repository's railway.json). MAIN healthcheck timeout 120 seconds; V8.1 30 seconds. No custom build/pre-deploy command, source-root change, new upstream BRTI owner, tracing system or order capability.

### Reviewed pending patch

Patch container `19ab6a3d-1e97-4b38-896e-a64b7b8e59a8`, **57 pending fields**, four resources, non-destructive. Railway reused the cleared patch container ID; its contents are a new V2-only configuration. No V1 source SHA, old qualification-service change, shared variable, production-service change or unrelated resource remains.

Machine-readable approval payload and readback: `qualification/BTC15_V2_RAILWAY_STAGED_20261003.json`.

Before applying, re-read the pending patch and compare its four-resource allowlist, exact SHAs, commands, variables and mounts against that snapshot. If another actor adds a change, do not commit the expanded patch under this approval. Railway accept-deploy applies **all** staged environment changes.

Production before/after readbacks have identical configurations, volumes and deployment identities:

- MAIN deployment `6a6581ba-fc0a-4021-84c4-9c1896c4f179`.
- V8.1 deployment `54a117aa-1809-4c56-8d32-190fbc5c1ce9`.

## Current blocker and next action

**USER APPROVAL RECEIVED; RAILWAY CONNECTOR CONFIRMATION DID NOT COMPLETE.** On October 3 at 20:10 New York, the user explicitly approved the exact two-service/four-resource qualification payload, including volumes, reviewed variables/start commands, brief live wiring, journal durability/restart and settlement-path checks. Production remains excluded.

The pending patch was re-read immediately before the commit attempt and matched the repository-preserved approval snapshot exactly: 57 fields, four approved resources, no extras, unchanged patch timestamp. The `railway_accept_deploy` call returned: **“Cancelled — the user did not approve this action. No changes were made.”** This is the connector result, not an assertion that the user's written approval was absent.

Post-cancellation readback confirmed the same 57-field patch remains STAGED, both qualification services still have `latestDeployment=null`, and both 2,048 MB volumes remain `staged-create`. No live qualification, restart, settlement-path observation or production promotion occurred. The original approved payload file remains unchanged; the attempt receipt is `qualification/BTC15_V2_QUALIFICATION_ATTEMPT_20261004.json`.

Next action: complete the connector's deployment confirmation, then re-check the unchanged approved patch before committing. Do not retry through another deployment route to bypass the cancelled confirmation. No broader scope approval or product redesign is needed.

After the connector confirmation completes:

1. Commit only the reviewed V2 patch. Confirm exact deployment SHAs and startup verifier output; check both mounts/root paths and the staged V8.1 URL.
2. Observe official Kalshi ticker/window/immutable target, true BRTI age ≤5s, accepted quote provenance/freshness, Coinbase freshness and no future observations. Confirm readable independent FINAL, PASS versus UNAVAILABLE, signal_only=true and orders=false.
3. Match live publications to existing bounded journal records: immutable EARLY/SCALP origin where observed, actual ask/later same-side bid, genuine FINAL linkage, protection/EXIT and predecessor identity. Use existing deterministic fixtures for unobserved state branches; label fixture proof separately from live wiring evidence. Never fabricate a live event or require a multi-day signal cohort.
4. Read back durable journal/checkpoint/coverage state; perform a controlled restart of each qualification lane and prove persisted origins/terminals/sequence remain intact with the same volume. Confirm official settlement receipt handling through the existing GET-only path, preserving pending/unavailable outcomes. Do not wait idly for market settlement.
5. Update this document transactionally with actual evidence and DONE / MISSING / SHADOW-ONLY / QUALIFIED / DEPLOYED / REJECTED statuses. If a narrow wiring/storage defect appears, isolate it without reopening strategy development.
6. If brief qualification passes, **STOP FOR SEPARATE PRODUCTION PROMOTION APPROVAL** and present the exact production source/storage/variable/start-command proposal. Do not infer promotion approval from qualification approval.

## Permanent anti-drift rules

- **RECOVER BEFORE REBUILDING.** Check repository/history before declaring product behavior missing.
- Supporting infrastructure cannot redefine the product objective or move the fixed sixteen-capability finish line.
- The V2 completion certificate is authoritative. No strategy, threshold, weight or ladder-development change is authorized in this mission.
- Ground Zero is retired. Both failed Oct. 3 intervals remain excluded from scoring, training, tuning, selection and validation.
- V1 qualification is obsolete; do not use its source SHA, startup gate or service configuration.
- No multi-week or multi-day pre-deployment statistical campaign is required. Brief functional qualification is distinct from future performance evidence.
- Never claim 85%/90% EARLY reliability, calibrated FINAL probabilities, profitable SCALP execution or increased signal frequency from these functional checks.
- **SIGNAL ONLY / NO ORDERS / NO AUTOMATED EXECUTION** is invariant.
- BUILT, SHADOW-ONLY, QUALIFIED and DEPLOYED are distinct. Do not promote a status without its evidence and required approval.
