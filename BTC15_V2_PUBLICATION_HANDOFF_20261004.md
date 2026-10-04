# BTC15 V2 publication handoff - 2026-10-04

SIGNAL ONLY / MANUAL EXECUTION ONLY / NO ORDERS. DO NOT DEPLOY.

## Exact artifacts; incomplete candidate-ref publication

The completed original ZIP/PDF, both exact incremental bundles and checksum files are published unchanged under `release_review/v2-product-r1-20261004/`. This documentation commit is not a replacement deployment candidate.

The exact candidate branch refs remain BLOCKED: this workspace's Git push has no authenticated credentials. The connector can publish artifacts, but its commit-creation interface cannot retain the original author/committer metadata and SHA. No substitute candidate commit was created. Original candidate objects remain intact in the bundles.

- MAIN: `020f8a38d07e0a11e983a1e3bee3b06a4898c2f3`; tree `5ffab0fa22364129502d2c9bb817cc2eba862a1c`; frozen parent `de4f3e20b8657eb8cfee91bd4e525c103b5bf513`.
- V81: `07406e46945cc0bfebbb25299c5da53e87ac6a2a`; tree `2a32b72db1a0eb9a9beb28d42ad659e35a8b9d0e`; frozen parent `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1`.

## Newly found committed-tree packaging failure

V8.1 `07406e46945cc0bfebbb25299c5da53e87ac6a2a` omits `btc15_cohort_evidence_v1.py`, required by its release manifest. The file was present in the earlier offline worktree, but not in the commit. MAIN's committed manifest inventory passes; V8.1 fails this one missing-file check. All other listed file hashes match. This packaging defect is separate from the four baseline-equivalent test-fixture errors. No repair or candidate modification is made because this mission explicitly freezes the candidate.

The original report/archive is preserved as historical evidence. This publication handoff corrects the scope of its workspace-verification claim: it was not sufficient to prove a self-contained V8.1 committed release. The package is NOT deployment-ready.

## Completed results preserved without rerunning

280 MAIN tests passed / 19 current V8.1 tests passed / 17 scoring-bridge tests passed / 12 assembled-dashboard DOM scenarios passed. Older V8.1 suite remains 14 passed / four obsolete fixture errors, reproduced identically on its frozen baseline and unchanged. No tests, model builds or tuning were repeated during publication. Original fixture scoring accumulated one then two strict settled contracts, with production claim still blocked as SYNTHETIC_FIXTURE_ONLY.

## Integrity and rollback

`publication_integrity.json` records commit/tree identities and release/source/model hashes. All 697 original MAIN and 607 original V8.1 files remain unchanged; original lane freeze manifests verify. Both original bundles verify against frozen parents and all 90 checksums inside the original ZIP match. Rollback commands, frozen source commits, original start commands, cohort isolation and intentionally invalid deployment receipt are intact. Original archive text saying local/not pushed describes creation-time state; artifact publication does not rewrite it.

## Production freeze

Read-only pre-publication Railway inventory found 53 services, none attached to the new candidate/review branch names, and no staged changes. MAIN deployment: `ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa`, source `de4f3e20b8657eb8cfee91bd4e525c103b5bf513`. V8.1 deployment: `2051e772-bd39-4dea-a77d-52fea0a07c02`, source `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1`. Both SUCCESS. No Railway write, production deployment/configuration change, alert update, service retirement, credential creation or order action occurred. Post-publication readback is recorded separately.

## Remaining blockers

1. Authenticated Git push needed to import/push exact original candidate refs; do not recreate them under new SHAs. Browser fallback to the existing authenticated Codespace requires approval under the browser-tool fallback rule; do not start login loops or create credentials.
2. V8.1 committed-tree missing scorer file requires a separately authorized packaging correction/new commit; exact candidate is unchanged here.
3. Previously documented D04 attribution, rendered-browser/physical Safari checks and bounded live acceptance remain open. Real strictly scoreable settlement/later accumulation, comparable production quote lag and actual alert delivery are not established.

Publishing the review package is not production approval. Do not merge or deploy this review branch.
