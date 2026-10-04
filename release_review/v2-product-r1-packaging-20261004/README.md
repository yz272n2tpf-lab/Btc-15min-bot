# BTC15 V2 packaging correction — 2026-10-04

SIGNAL ONLY / MANUAL EXECUTION ONLY / NO ORDERS. DO NOT DEPLOY.

The V8.1 missing-file blocker is fixed. Exact candidate branch publication remains blocked by unavailable authenticated Git push. The connected GitHub API publishes this review package but cannot import original local Git commit objects with their exact metadata. The inspected cloud browser is signed out; no sign-in, credentials, new account or alternate repository was attempted. Browser sign-in alone is not proof of an authenticated Git push path.

## Exact release identities

| Lane | Commit | Tree | Intended remote branch (not yet published) |
|---|---|---|---|
| MAIN unchanged | `020f8a38d07e0a11e983a1e3bee3b06a4898c2f3` | `5ffab0fa22364129502d2c9bb817cc2eba862a1c` | `candidate/v2-product-20261004` |
| V8.1 corrected | `985260e4166559701fc96b5582ca2211619d53ee` | `172b9eaa9686b165ec3cd396ba9398b715d31028` | `candidate/v81-product-20261004` |

Corrected V8.1 is a direct child of `07406e46945cc0bfebbb25299c5da53e87ac6a2a`. Its entire change is the addition of `btc15_cohort_evidence_v1.py`, byte-identical to the already-qualified MAIN version: SHA256 `9812c23a6200bf31c2c5eb4e8f317fe32cfcafefeaa37d2a9b9a041967447d1a`. No existing tracked V8.1 file changed. No scorer contents, strategy/model files, timing/freshness thresholds, source definitions, evidence definitions, runtime logic or protection/EXIT policy changed.

The unchanged product manifest is `7289357977b4771b16644b32f75101883a4ecaaf7e8f82eef8d8042848d040f0`. Product revision remains `BTC15_V2_PRODUCT_20261004_R1`; strategy remains `BTC15_LADDER_COMPLETION_20261003_V2`.

## Preserved evidence and limited revalidation

The original archive in `original/` is preserved byte for byte, including all 90 checksummed members, both original bundles, original PDF, full qualification results, four baseline-equivalent V8.1 fixture errors, rollback and bounded live acceptance. The original V8.1 bundle is historical evidence; the top-level corrected V8.1 bundle is the release candidate. Original creation-time indexes are superseded only for V8.1 identity and packaging/publication status by this top-level `RELEASE_INDEX.json`.

Completed results retained: 280 MAIN / 19 current V8.1 / 17 scoring bridge / 12 assembled-dashboard DOM scenarios passed. Older V8.1 remains 14 passed / four obsolete fixture errors reproduced on its frozen baseline. These errors were neither edited nor reclassified.

Only affected checks were run again: clean committed V8.1 checkout, offline launcher release/freeze verification, and 17 existing scoring-bridge/diagnostic tests (17 passed, zero failed). All release, frozen strategy/model, packaged-source and original archive hashes verify. Original files unchanged: MAIN 697, V8.1 607. No 280-test campaign, current-source 19-test suite, dashboard 12-scenario suite, model building or profiling was repeated.

`packaging_integrity.json` records exact checks and hashes; the two `clean-commit-*.log` files record the new limited checks. `verify_packaging.py` preserves the verification procedure and original workspace paths; it is audit evidence, not a portable runtime command.

## Exact publication step still needed

Use an **already authenticated existing checkout of `yz272n2tpf-lab/Btc-15min-bot`** with both frozen base commits available. Do not create PATs, SSH credentials, accounts or repositories. Extract this package and verify `SHA256SUMS` before proceeding. The package's script defaults to bundle-hash verification and does not create credentials, invoke Railway, change production refs, dispatch workflows or run qualification.

```sh
python publish_exact_candidates.py
python publish_exact_candidates.py --repo /absolute/path/to/existing-authenticated-checkout --push
```

The second command imports the two exact bundles and atomically pushes only the two intended candidate refs, without force. It refuses unexpected repository URLs, changed frozen production refs or unrelated existing candidate heads, and reads remote refs back. If existing authentication fails, it stops without prompting for credentials. No cherry-picking, same-tree substitute commits or API-recreated candidate identities are acceptable.

After that user-only authenticated push, record the exact remote refs and verify current Railway production remains frozen before calling publication complete. This package is packaging-correct and reviewable; it is **not yet publication-complete or deployment-authorized**.

## Production, rollback and pending acceptance

Current read-only Railway evidence retains MAIN deployment `ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa` at `de4f3e20b8657eb8cfee91bd4e525c103b5bf513` and V8.1 deployment `2051e772-bd39-4dea-a77d-52fea0a07c02` at `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1`, with no staged changes. No production configuration, deployment, watcher, service or order action was performed.

`BTC15_V2_PRODUCT_RELEASE_REVIEW.original.md` is the unchanged rollback/acceptance document (SHA256 `00018d05f6ae3c92ac6a546f1422dd0bfa598b436ce53504b0ca7c1ebb2b5fb0`). Read the original qualification logs at `qualification/qualification_summary.json` inside the preserved archive. The top-level receipt template changes only V8.1's build SHA; it remains intentionally invalid with no deployment IDs or start times.

Previously documented rendered/physical iPhone/iPad Safari verification, D04 live inner-cause attribution, comparable production quote lag, actual alert delivery and bounded real contract/rollover scoring acceptance remain uncompleted. This packaging mission does not waive them or claim live performance. Production approval remains required.
