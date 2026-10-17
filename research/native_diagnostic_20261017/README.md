# Native diagnostic packaging readiness — 2026-10-17

**Packaging PASS. Native activation NOT READY.** No production deployment,
restart, setting change, resize, capture, order or evaluation was performed.

Continue from `research/early-10-12h-preflight-20261017` at
`0daf1ac442c4f5276d3e748421bfd13deef4ea1f`. All existing reader/checkpoint and
capture source bytes are preserved. This work adds exact-source packaging,
integrity tests, approval inputs, an inert mounted-lease probe and this report.
The prior 101-test receipt and all earlier evidence remain unchanged. No
600,000-record or long retention workload was repeated.

## Exact packages

| Role | Published research branch | Commit |
| --- | --- | --- |
| MAIN | `research/native-diagnostic-main-20261017` | `e2294683d2ec268d921df0277f5a9cb518f2e67d` |
| V81 | `research/native-diagnostic-v81-20261017` | `f7c32d04556335632c862515a9ee1b742ad88ad3` |
| Information | Same existing MAIN installation | `e2294683d2ec268d921df0277f5a9cb518f2e67d` |

The reproducible archives are 24,567,912 bytes MAIN/information and 24,550,761
bytes V81. SHA-256:

- MAIN/information: `f04b5e667e9d7dd958fb171bdf57c5e136ce768ff6e5d62a99aad4f62e53e73c`
- V81: `abf1d1cffcfdcd9555f30099a3175954a6edbbbb8fa2eaf84dda4dfebbec5c1c`

`PACKAGES.json` gives each role its own package identity and records complete
changed-file/protected-file hashes, source trees, original/candidate manifest
hashes, deployment binding and rollback results. Information reuses the MAIN
archive deliberately; no duplicate installation or new service is needed.
GitHub's auto-generated archives use different tar metadata; these hashes refer
to the deterministic archives produced by `packages.py`, not codeload archives.

## Source recovery and unchanged behavior attestation

The connected GitHub service supplied 13 missing blobs. Each was reconstructed
as a Git blob and its object ID checked before entering the local object store.
`RECOVERED_OBJECTS.json` records Git IDs, SHA-256 and sizes. Full original and
deployed trees were exported from verified objects without ancestry traversal.
The live Railway metadata still identifies MAIN `dd46b7bc...` and V81
`c14b3f9b...`; their pinned GitHub trees match the source used for comparison.

Both packages use the existing allowlisted installer against original bases
MAIN `4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c` and V81
`6e04aced0f718b29f8ed805abcc0f76b01ed5096`. Compared with actual deployed
recorder releases, each changes exactly 17 files: two installation manifests,
13 `ops/live_recording` modules and two offline evidence/lifecycle modules.
All changes are the already completed baseline engineering; no new production
module change was introduced here. Existing bounded reader modules accompany
the recorder through its established installer, not a replacement validator.

903 MAIN files and 889 V81 files remain byte-identical to deployed source.
All 38 MAIN and 14 V81 freeze/protected entries pass. Every native entrypoint,
native information/journal writer, strategy, FINAL/EARLY/SCALP policy,
entry-price/threshold, timing scheduler, Kalshi integration, settlement and
order-related source file is unchanged. This follows from the full inventory
comparison, not only the protected subset. Manifest safety stays signal-only,
orders false, capture default off. Package subprocess checks ran with network
connections forbidden and did not start native owners or capture.

This attests source logic and configuration, **not zero runtime overhead**.
Recorder callbacks add work; native timing, actual oversize kind, loss-free V81
drain and dependency compatibility still need authentic diagnostic evidence.
The local Python environment differs from native requirement pins (including
missing requests); `TEST_RESULTS.json` records the exact differences rather
than treating local tests as native runtime qualification.

## Focused verification

- 52 offline checks passed: 49 serial tests in 6.773 seconds (8 package,
  17 short-preflight, 24 checkpoint/recovery), plus 3 inert approval-input
  checks in 0.002 seconds. No failures/errors.
- Every archive member, path, duplicate check and content hash matched its
  complete installed-tree inventory; rebuilding twice produced identical bytes.
- The existing release/freeze verifier passed inside each actual package.
  Native bootstrap remains inert with recording disabled for all three roles.
- All installed Python sources compile. Baseline reader/checkpoint/capture
  hashes match the preserved 101-test receipt exactly.
- Existing installer rollback copies restore original bases exactly. A separate
  copy of each package restores its actual deployed source inventory exactly.
- Process interruption before/after commits and within windows, resumed MAIN,
  V81/settlement associations, no duplicate ledgers, logical/SQLite integrity,
  stale evidence rejection and source-code drift protection remain passing.
- Local single-reader exclusion across outputs/processes and SIGKILL lock
  release pass. **Mounted Railway-volume lease has not run.**

The first scratch packaging attempt stopped on an unexpected extra temporary
CSV in its V81 source export. It is preserved, not accepted or cleaned up.
A fresh isolated `/tmp` export passed full inventory, rollback and archive
checks. The cause of that scratch mutation is unproven. The earlier concurrent
SQLite corruption remains unresolved; serial execution is mandatory.

Reproduce only the bounded checks:

```sh
python -B -m research.native_diagnostic_20261017.packages --out /tmp/NEW-unique-bundle-directory
BTC15_TEST_BUNDLES=/tmp/NEW-unique-bundle-directory python -B -m unittest -v \
  research.native_diagnostic_20261017.test_packages \
  research.early_10_12h_20261017.test_preflight \
  research.bounded_reader_recovery_20261016.test_recovery
python -B -m unittest -v research.native_diagnostic_20261017.test_approval
```

## Current access, storage and cost

`PLATFORM_READS.json` / `PRODUCER_CONFIG_READS.json` preserve read-only platform
receipts. Seven historical production volumes remain: 50,000 / 5,000 / 2,048 /
2,048 / 1,024 / 20,000 / 5,000 MB. Research remains 100,000 MB. Four staged
changes remain pending under `ead9997e-b5b7-4668-a612-e8417e197838`.

| Producer | Allocation | Current disk metric | Nominal unused | Diagnostic initial minimum |
| --- | ---: | ---: | ---: | ---: |
| MAIN + information | 20,000 MB | 11.701543 GB | 7.729 GiB | 2.03125 GiB + native growth |
| V81 | 5,000 MB | 3.214336 GB | 1.663 GiB | 2.03125 GiB + native growth |

Nominal unused is allocation minus service disk metric, **not verified usable
filesystem free space**. V81's nominal shortfall is 395,374,080 bytes (377.06
MiB), before native growth. Require exact filesystem readings; no reserve was
lowered, volume resized or evidence deleted. The existing research deployment
has zero running replicas, so mounted lease/free-space/production SSH checks
cannot run without a separate start/deployment authorization. The connector
has no exec or billing balance tool and no authenticated local CLI path exists.

The total diagnostic compressed cap is 64 MiB. At Railway's published
$0.15/decimal-GB-month and $0.05/GB egress, retaining that cap for a month is
about $0.0101 and one transfer is $0.00336. A full 1 GiB reader DB adds about
$0.161/month retained. A conditional 1 GB RAM + 1 vCPU for seven minutes is
$0.00486. These exclude existing usage, native overhead, copies, metadata,
additional CPU/RAM, plan fees and credits; they are **not an account bill or
verified budget headroom**. Rate source checked through official Railway docs:
https://docs.railway.com/pricing/plans . Exact assumptions: `STORAGE_COST.json`.

## Remaining blockers and decision

| Gate | Result / exact blocker |
| --- | --- |
| Pinned source recovery and producer bundles | PASS; source packaging blocker cleared |
| Protected source / signal-only / offline integrity | PASS; runtime timing remains unmeasured |
| Mounted research-volume ReaderLease | BLOCKED; zero running replica, no authorized start/exec path |
| Producer usable free space | UNVERIFIED; V81 metric projection fails reserve |
| Native exact dependency and runtime attestation | PENDING; local dependencies differ, runtime SSH inaccessible |
| Actual account spend/credits/headroom | BLOCKED; billing not exposed by current connector |
| Selective deployment without four pending changes | BLOCKED; available accept-deploy commits the full patch |
| Separate diagnostic authorization | NOT GIVEN; no activation requested/executed |

**NOT READY / NO-GO for native activation or EARLY evaluation.** Follow
`DIAGNOSTIC_PROCEDURE.md` for the concrete proposed settings, storage caps,
stop/rollback commands and evidence preservation. Clear the access/storage
gates, then obtain approval for the exact 60-second operation. A passing
diagnostic does not qualify the 20-minute preflight or 10-hour evaluation;
each needs its own evidence review and authorization.
