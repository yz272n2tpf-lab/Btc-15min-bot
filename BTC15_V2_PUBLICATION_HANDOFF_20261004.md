# BTC15 V2 authoritative publication handoff — 2026-10-04

SIGNAL ONLY / MANUAL EXECUTION ONLY / NO ORDERS. DO NOT DEPLOY.

This review update continues `613161e7d69f4f4662db307b867031de335c24bf`. The V8.1 packaging blocker is closed. The exact candidate branch publication blocker remains open. This review branch is not a deployment candidate.

## Exact candidate identities

| Lane | Candidate commit | Candidate tree | Intended branch | Publication status |
|---|---|---|---|---|
| MAIN unchanged | `020f8a38d07e0a11e983a1e3bee3b06a4898c2f3` | `5ffab0fa22364129502d2c9bb817cc2eba862a1c` | `candidate/v2-product-20261004` | Exact objects preserved in published bundle; branch ref absent |
| V8.1 corrected | `985260e4166559701fc96b5582ca2211619d53ee` | `172b9eaa9686b165ec3cd396ba9398b715d31028` | `candidate/v81-product-20261004` | Exact objects preserved in published corrected bundle; branch ref absent |

V8.1's new commit is a direct child of `07406e46945cc0bfebbb25299c5da53e87ac6a2a`. It adds only `btc15_cohort_evidence_v1.py`, copied byte for byte from the already-qualified MAIN source. SHA256: `9812c23a6200bf31c2c5eb4e8f317fe32cfcafefeaa37d2a9b9a041967447d1a`. No existing V8.1 tracked file changed. The product manifest stays `7289357977b4771b16644b32f75101883a4ecaaf7e8f82eef8d8042848d040f0`.

## Published review package

Original evidence remains unchanged under `release_review/v2-product-r1-20261004/`. The correction is under `release_review/v2-product-r1-packaging-20261004/`:

- `BTC15_V2_Corrected_Release_Package_20261004.zip`: corrected active index, both active candidate bundles, unchanged original 90-entry archive, invalid receipt template with corrected V8.1 build, verification logs, integrity reports, rollback/acceptance document and exact-ref publication script.
- `v81-candidate-corrected.bundle`: exact corrected V8.1 history; SHA256 `a19550c78677e6f2b5cb275dd5330aedfa047fc7808789220cac5b6aa36f3b9a`.
- MAIN bundle remains `3e71a3e9b99bcda2187bcd2eeb702b08d2615c2191e13b6e8fbd815c153097c9`.
- `SHA256SUMS`, `ARTIFACT_SHA256SUMS.txt`, `packaging_integrity.json`, `bundle_restore_verification.json` and limited-check logs bind the package and evidence. Post-publication readback is recorded separately.

The old V8.1 bundle and original report remain historical evidence. They are not rewritten to conceal the earlier untracked-file packaging mistake. The top-level corrected index supersedes the old V8.1 build identity; it does not change the evidence revision or strategy.

## Completed qualification and affected checks

Preserved completed qualification: **280 MAIN passed / 19 current V8.1 passed / 17 scoring bridge passed / 12 assembled-dashboard DOM scenarios passed**. Older V8.1 fixtures remain **14 passed / four errors reproduced identically on the frozen baseline**. Those tests, logs and classifications remain unchanged.

Only affected checks were repeated after adding the file: clean committed V8.1 checkout; original release/freeze verifier via the offline launcher; 17 scoring-bridge/diagnostic tests. All pass, with zero failures. No new full qualification, model building, optimization, tuning, browser campaign or live acceptance was run.

Both lane release manifests now pass against committed trees. All 697 original MAIN and 607 original V8.1 files, including frozen EARLY/FINAL/SCALP strategy/model files, remain unchanged. All 90 original archive hashes verify. Both original bundles and the corrected V8.1 bundle verify; active bundles restore the exact candidate commits/trees, including the scorer. Rollback and acceptance document SHA256 remains `00018d05f6ae3c92ac6a546f1422dd0bfa598b436ce53504b0ca7c1ebb2b5fb0`.

## Exact-ref publication blocker and required user step

The authenticated GitHub connector successfully publishes review artifacts but its exposed commit API cannot import raw local commit objects or preserve original author/committer timestamps. Creating same-tree replacement commits would violate the exact MAIN identity. The local Git push path has no authenticated credentials. The browser inspection shows GitHub signed out; that path was stopped without attempting sign-in. No PAT, SSH credential, new account, alternate repository or substitute candidate commit was created.

What is needed: an **existing authenticated Git push session for `yz272n2tpf-lab/Btc-15min-bot`**. In an already authenticated checkout containing both frozen bases, extract the corrected ZIP, verify its checksums, then run:

```sh
python /absolute/path/to/extracted-package/publish_exact_candidates.py --repo /absolute/path/to/existing-authenticated-checkout --push
```

The script verifies both bundle hashes, imports exact objects, atomically pushes only the two authorized candidate refs without force, refuses unrelated existing heads, and verifies remote SHAs and unchanged frozen production Git refs. It creates no credentials, invokes no Railway operation and performs no deployment. After that step, read back the two branch SHAs and recheck Railway before recording publication complete. Browser sign-in alone does not establish a usable exact-object Git push path.

## Production freeze and remaining review gates

Read-only Railway inspection preserves MAIN source `de4f3e20b8657eb8cfee91bd4e525c103b5bf513`, deployment `ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa`; V8.1 source `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1`, deployment `2051e772-bd39-4dea-a77d-52fea0a07c02`. Both are SUCCESS, with original configuration and volumes and no staged changes. The 53-service inventory has no candidate/review branch binding. No Railway write, production change, watcher update, alert delivery, service retirement, credential creation or order action occurred.

Previously open rendered/physical iPhone/iPad Safari checks, D04 live attribution, comparable production quote lag, actual alert delivery and bounded real contract-plus-rollover scoring acceptance remain open. No synthetic result is promoted into a production claim, no gate is waived and no multi-day performance campaign is requested.

## Verified GitHub readback

Artifact publication commit: `eeb783fbbe36cea9f0f52528c5b7c046d9f5ce11`; tree: `1802f9f3424f8f1ed3609dcf1ab664c27961e90b`. Readback at 2026-10-04T18:20:27Z verified all 23 published artifact files, all 19 correction-package hashes, all 90 original nested hashes, both active bundles and the unchanged original review folder. Corrected ZIP SHA256: `12e64a18cb2b50ff7083853602fed444fa269cde393be5b176236edd45552ae5`.

`post_publication_verification.json` and the three `railway_after_*.json` files in the correction folder record the result. MAIN and V8.1 configuration/deployment readbacks are identical to the previous review and this mission's before snapshots. The entire 53-service environment inventory is unchanged after ignoring list order, with no staged changes. Remote candidate refs are still absent; frozen production Git refs remain exact.

**Status: packaging-correct review package published; exact candidate refs still blocked; not publication-complete and not authorized for production deployment.**
