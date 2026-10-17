# Single 60-second native diagnostic: authorization package

Decision: **READY TO REQUEST AUTHORIZATION for one controlled diagnostic**.
No production action is authorized by this document. The 20-minute preflight,
10-hour evaluation and production acceptance remain unapproved and unproven.
This narrowly supersedes stale operational blockers in the two earlier
diagnostic reports; their evidence and test results are preserved unchanged.

Base: `950e4b5e401d501bb26b5a66473e06500e8c08ac`.
Research branch: `research/native-diagnostic-authorization-20261017`.
Only receipts, an offline static check and authorization instructions are added.
No producer package, strategy, validator or existing reader is changed here.

## Verified evidence and remaining diagnostic objectives

The completed research deployment is
`b6c57782-2b39-46de-b57d-e29ae2192528`. Its original receipt is retained as
`PROBE_RECEIPT.json`, SHA-256
`26a94f28ed48f26a9dd8cd31b7918b86327a0b731beba8370e5cdca666bfd480`.
It agrees byte-for-byte with the hash logged by that deployment. Producer
samples were taken 2026-10-17 approximately 12:06:41–12:07:02 UTC. The job has
exited; the control plane reports zero running research replicas. It was not
rerun for this preparation.

| Gate | Result | Evidence / scope |
| --- | --- | --- |
| Pinned access and original source | PASS | Both pinned SSH connections succeeded; 36 MAIN and 17 V81 source-file hashes match; exact service/environment/volume/build/deployment identities match. |
| Actual producer space | PASS | Table below uses actual available bytes, not volume metrics. No resize needed. |
| Mounted single-reader lease | PASS | Concurrent volume lock and full ReaderLease rejected; own-child SIGKILL released lock; reacquisition passed with stable lock inodes. No DB opened or historical file changed. |
| Runtime prerequisites | PASS | Native Python 3.12.14 and all eight pinned distribution versions match on both producers. |
| Exact package static installation | PASS | All three roles pass package attestation using observed native version metadata and offline hook seam installation/compilation. Complete source inventories match. No native callback, thread, network, capture or order execution. |
| Selective deployment | PASS, API-contract verification | Explicit service-only connector operations below; no staged-patch commit. Production has exactly one environment. No live mutation was performed to test the backend. |
| Protected behavior | PASS, source/config scope | Strategy, Kalshi integration and timing logic, freshness checks, entry policy, settlement/native writers and signal-only policy remain unchanged. |
| Native hook overhead, loss-free drain and emitted associations | NOT YET PROVEN | These are the purpose of this diagnostic, not a claim made by the static check. |
| Account billing/credits/headroom | UNKNOWN | Available connector has no billing query; no authenticated local CLI. No claim that the account is below $20/month. Explicit incremental allowance requested below. |

The mounted lock is containment of the concurrent SQLite issue; it does not
prove the original corruption's root cause or filesystem crash durability.
The new local check replays native distribution metadata; the local installed
dependency set differs. It is not execution inside the producer's runtime.
The preserved 52 packaging/approval tests and earlier regression receipts are
not rerun or relabeled as native tests. The 600,000-record test is not rerun.

## Space and cost decision

Each producer reserves 32 MiB compressed capture plus 2 GiB operating reserve:
**2,181,038,080 bytes**. Add **256 MiB = 268,435,456 bytes** for native growth
over a thirty-minute installation/capture/drain/transfer/rollback planning window after the fresh
preactivation space check. The approval floor is **2,449,473,536 bytes**.

| Producer | Measured available bytes | Margin above approval floor | Shortfall |
| --- | ---: | ---: | ---: |
| MAIN, including information | 9,142,173,696 | 6,692,700,160 | 0 |
| V81 | 2,611,572,736 | 162,099,200 | 0 |

MAIN's ten-second net disk consumption was 48,332.32 B/s; V81's was zero.
The growth allowance corresponds to 149,130.81 B/s over thirty minutes, about
3.09 times that MAIN sample. This is a conservative planning allowance, not a
proven bound: buffered writes and bursts can exceed short samples. V81's zero
sample is not a prediction. Read available bytes once immediately before
approved writes; abort below the floor or if preparation exceeds the window.
Do not repeat the completed probe. Native recorder reserve checks remain active.
No ten-hour retention conclusion is drawn from these measurements.

Research available space was 94,873,952,256 bytes; retain the existing >=5 GiB
guard, 1 GiB reader-DB ceiling, 240-second reader budget and serial lease.

No capacity adjustment is needed: resizing cost is **$0**. At current published
rates, 17 minutes of the existing 4-vCPU/8-GB research ceiling is approximately
**$0.0629**. Request **$0.10 incremental compute planning allowance** for the
single diagnostic workflow. This is not a billing-enforced cap or a guarantee
of total producer cost; deployment duration/producer overhead are unmeasured.
Existing production baseline, subscriptions, credits, egress and retained
evidence storage are separate. Producer raw data at both caps adds about
$0.0101/month; retaining one extra raw copy and a full 1-GiB reader DB adds about
$0.1711/month, excluding exports/recovery archives and transient journals.
No billing settings change is proposed. If a verified account-wide ceiling is
required, owner billing confirmation is the sole additional financial step;
no resizing or further engineering is needed.

Rates: RAM $0.000231/GB-minute; CPU $0.000463/vCPU-minute; used volume storage
$0.15/GB-month; public egress $0.05/GB. Sources checked 2026-10-17:
https://docs.railway.com/pricing/plans and
https://docs.railway.com/volumes/reference. These are conditional calculations,
not an account bill.

## Immutable installation and rollback identities

| Identity | MAIN + existing information worker | V81 |
| --- | --- | --- |
| Candidate branch | research/native-diagnostic-main-20261017 | research/native-diagnostic-v81-20261017 |
| Candidate commit | e2294683d2ec268d921df0277f5a9cb518f2e67d | f7c32d04556335632c862515a9ee1b742ad88ad3 |
| Candidate tree | 8d640adab13a19b4990107474de114b51fb50bf8 | 30034850c51d515e0ce442277641216f9bc57ef3 |
| Archive SHA-256 | f04b5e667e9d7dd958fb171bdf57c5e136ce768ff6e5d62a99aad4f62e53e73c | abf1d1cffcfdcd9555f30099a3175954a6edbbbb8fa2eaf84dda4dfebbec5c1c |
| Release manifest SHA-256 | a31e1bd814771aaf678538e4d0f552f71ba8bc60a23dfad47fa78ae37121174d | 02aedccf31ceec8507900a93f1635d90ccbd9064fea9203599ab0d2c1e4eee8c |
| Install manifest SHA-256 | 5394c70b27fe286d8e6998055fe356d00ae5a9fc80c38348c32ab4f7b9c908ab | 9bdb8dd3f79373740d1758918f54d23f82fb8782f55cc701387c4fa8e04c2de4 |
| Service | ab28dca6-7bea-4956-bdb9-dbb7b4c74635 | 6025e83e-a41c-4e0a-8c16-f71120bd501b |
| Existing /data volume | 6ced6b1a-3755-4518-a240-c895e936d443 | d5eeafca-e0fc-42f0-b7d1-4705907720c6 |
| Rollback source commit | dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72 | c14b3f9b04caea13e62bcdd6fb0e5990049aa17b |
| Retained rollback deployment | c0993600-34b7-4501-92cd-b8d4a934b68a | 21bf7fd3-c294-46d9-8a0a-f551cce7a303 |
| Rollback release manifest SHA-256 | 9290281a9a9c5a8c2e51124f97343e8fee6f0bb4e729c0138945638439c3748b | 4bb232d5cb241b59a20c6d98c69fb68f8d634836c9c974bd11d2d4cf7ad29c38 |

Package IDs are `BTC15_NATIVE_DIAGNOSTIC_MAIN_20261017`,
`BTC15_NATIVE_DIAGNOSTIC_V81_20261017` and
`BTC15_NATIVE_DIAGNOSTIC_INFORMATION_20261017`. Information shares MAIN's
archive, service and volume; there is no third installation. The MAIN archive
was rehashed here. The V81 archive hash is preserved from the completed package
receipt; its exact 906-file source inventory was reverified here, and deployment
uses the pinned Git commit, not that archive. Both GitHub branch pins were read
back unchanged. Rollback deployments still advertise reusable builds, but the
selected route below is an exact-source rebuild; do not improvise a second route.

The 17 changed paths per package are enumerated in the preserved `PACKAGES.json`:
two release/install manifests, thirteen recorder/reader modules and two offline
evidence/lifecycle modules. Named corrections are completed-candle schema
interpretation, bounded original-journal/window associations and checkpoints,
single-reader containment, payload-kind/size diagnostics, strict queue/drop
accounting, drain/terminal receipts and bounded diagnostic policy. There are no
native strategy/entrypoint/writer edits. MAIN has 903 unchanged deployed files
and V81 889, including all 38/14 protected paths. Source equivalence does not
promise unchanged wall-clock behavior once hooks are active; measure that now.

## Exact proposed activation sequence — separate approval required

Production project `baea4e22-d004-4434-b2c5-81a7fbc05086`, sole environment
`61775c5d-c583-4dfc-af41-f25578856fd9`.
Run ID `DIAG_20261017_e2294683_f7c32d04`.
Config is the existing `research/native_diagnostic_20261017/campaign.approval-draft.json`,
SHA-256 `12b17ac651578d3325fadbc39fd340e9e6dc700d769c9ff5d6678e004d191949`.
Do not edit its bytes, profile, duration, caps or signal-only/order restrictions.

1. After explicit approval, use only the existing research service
   `1fff593b-8b09-4cc4-8c51-f9603082657f`, project
   `87ad03d5-e1d6-47d6-b1ea-159cd7594686`, environment
   `12d241b7-23b4-4421-aafd-142e943555ee`, mounted volume
   `2dba2ef6-b84d-4abf-9d04-58a1e77082c5`, for bounded private SSH preparation,
   observation and finishing. Retain one replica, 4-vCPU/8-GB limits and restart
   NEVER. Reuse the existing source/reader at `950e4b5e401d501bb26b5a66473e06500e8c08ac`;
   do not run its operational-probe start command. Total research runtime
   planning window is 17 minutes (ten minutes setup/capture/drain plus seven
   minutes finisher); stop the job after completion/failure, preserving output.
2. Read current source/deployment identities, the four staged fields and seven
   volume identities; stop on drift. Through the existing strict pinned SSH
   key/known_hosts, make the single fresh free-space check on each /data mount.
   Require >=2,449,473,536 bytes each and research >=5 GiB. Do not replace a host
   pin or retry access failures. Capture private before-state without logging
   credentials. No lease retest, owner import or market API request is needed.
3. Exclusively create, with directory mode 0700 and file mode 0600, then fsync
   file and directory, the exact approved config on each producer at
   `/data/btc15_recordings-control/DIAG_20261017_e2294683_f7c32d04/campaign.json`.
   Verify its SHA-256. Refuse an existing directory/file or evidence run root;
   do not overwrite, reuse or delete anything. Store the same private config at
   `/research-evidence/approved/DIAG_20261017_e2294683_f7c32d04/campaign.json`.
4. Apply only the six explicit connector calls in `SELECTIVE_ACTIONS.json`,
   in listed order, once: three recorder variables per service with
   `skipDeploys:true, staged:false`; exact proposed startCommand only with
   `staged:false`; then connect each exact repo/branch/**commitSha** with
   `staged:false`. Do not use environment-wide Deploy, accept-deploy,
   EnvironmentPatchCommitStaged, railway up, staging or archive installation.
   The source tool applies to all environments, so require the verified sole
   production environment still to be the only environment before the call.
   These source connections trigger the two builds. Read back the returned
   source and all pending fields after mutations; stop on any unexpected field.
5. Verify both new deployment IDs and candidate source/manifest attestations.
   `ATTEST_AT_START` binds actual platform IDs; independently compare with the
   control plane. MAIN/information runtime identities must agree. Do not
   fabricate deployment IDs or wait for one role to collect an event before
   starting another. The 60 seconds include each role's startup and need not
   overlap fully. Keep all start/end clocks and record actual overlap.
6. Monitor existing recorder/native health and admission/queue counters. The
   configured limit is **60 seconds per role**, enforced by the existing
   watchdog polling every 0.5 seconds. This is not a hard real-time kill:
   scheduler/fsync delay can cause overshoot. Record actual duration; an
   unexpected overrun is a failed diagnostic, never permission to extend it.
   No new source poller, order path, cadence, threshold or freshness relaxation.
7. Stop, drain and preserve as below, then perform the approved rollback.
   Read back all four staged changes and all seven historical volumes after
   activation and after rollback. Leave all evidence in place. End the research
   job and verify zero running replicas. No automatic next stage or retry.

`SELECTIVE_ACTIONS.json` is a reviewable description, not an executable tool
invocation. Its arguments are derived byte-for-byte from the already prepared
activation/rollback patches. Service-specific tools do not commit the pending
patch; this is their documented contract, not a claim of a tested live mutation.
The pending patch is `ead9997e-b5b7-4668-a612-e8417e197838`, status STAGED,
exactly four changes solely for `84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1`.
No changes to that service or patch are included.

Interruption risk: each producer restarts once to install and once to
rollback. Railway documents downtime for services with attached volumes.
Build/cold-start duration is unknown; signals may be unavailable and
current-contract continuity must not be assumed. The service-tool sequence is
not atomic: a spontaneous restart between settings and source connection could
encounter mismatched build pins and fail closed. Perform the calls without
unnecessary pauses; on failure stop and restore only the approved settings.
Do not claim an interruption-free deployment or alter restart/health policy.

## Stop, complete drain, preservation and rollback

Compressed ceilings: MAIN 16 MiB, information 16 MiB, V81 32 MiB; decoded
128/128/256 MiB; record caps 20,000/50,000/200,000. Queue remains 32 MiB and
16,384 items; observation charge 4 MiB; batches 1 MiB/256. Seal reserves can
stop earlier. No cap increase or strategy change is included.

Close admission on the first loss/rejection/oversize, native-journal gap,
invalid candle/timestamp schema, identity/freshness/timing failure, quota/reserve
breach, writer/drain failure or native-health regression. Existing measured
hook limits remain >5 ms individually or >1% over 1 ms after 100 calls per
label. Native ordering/freshness checks remain strict. Preserve the first
failure as INCOMPLETE. Do not synthesize missing oversized observations or
repeat the diagnostic to obtain a BUY or settlement.

For immediate operator stop, send the exact approved config on stdin through
the same pinned SSH to `/app` on the corresponding service, once:

```sh
python -B -m ops.live_recording.remote finish --roles main,information
python -B -m ops.live_recording.remote finish --roles v81
```

These target only this run's recorder admission; do not signal native owners.
The drain join is five seconds, seal wait eight seconds. Drain timeout is
permanently INCOMPLETE even if a late seal follows. Require zero admitted/durable
deficit and no queue/native sequence losses for PASS. Save health and available
partial/terminal/seal receipts before any source rollback. The standard finisher
needs the candidate source identity still installed. Run it once, serially:

```sh
timeout --signal=TERM --kill-after=10s 420s python -B -m ops.live_recording.finish \
  --config /research-evidence/approved/DIAG_20261017_e2294683_f7c32d04/campaign.json \
  --output /research-evidence/DIAG_20261017_e2294683_f7c32d04-reader
```

The existing finisher bounds transfer, checks SHA-256 and runs the existing
reader with its mounted lease, 1-GiB DB and 240-second reader budget. Preserve
compressed originals, config/identity/deployment receipts, health, seals,
partial failures, ledger, reader logs and recovery archive on the existing
research volume; keep producer originals too. Existing bounded per-object
transport handling is unchanged; this authorization grants only one finisher
invocation, not repeated recovery campaigns. An unsealed failure remains
INCOMPLETE and its producer files remain untouched; broader recovery requires
separate review. Do not broaden allowlists or kill an existing reader.

After preservation, execute only the `rollback` list in `SELECTIVE_ACTIONS.json`:
set recorder enabled to 0 (skipDeploys), restore the exact original start command
for each service, then connect each original source commit/branch once. This
selected exact-source rebuild restores all package code and build/manifest pins
and incurs another possible restart per producer. It preserves config paths
and evidence; it intentionally disables capture rather than claiming exact
restoration of unknown old recorder-variable values. Do not also redeploy the
retained images. If native health is impaired, approved rollback takes priority
over a clean seal, and the capture remains INCOMPLETE.

Verify SUCCESS, old source/manifest, native health, recorder disabled, unchanged
signal-only behavior, untouched staged patch/volumes and evidence retention.
One unsuccessful rollback stops for operator review, without retry loops.

## Exact authorization request

Authorize one installation of MAIN/information `e2294683d2ec268d921df0277f5a9cb518f2e67d`
and V81 `f7c32d04556335632c862515a9ee1b742ad88ad3` on the two existing services,
only the named build/manifest start-command substitutions and three recorder
variables, exclusive writes of config hash
`12b17ac651578d3325fadbc39fd340e9e6dc700d769c9ff5d6678e004d191949`,
one 60-second-per-role diagnostic with the existing watchdog semantics,
bounded use of the existing research service for private preparation/finishing,
and the exact-source rollback above. Approve $0.10 incremental compute planning
allowance while acknowledging account-wide spend/credits are unverified and
retained storage is separate. Accept possible installation/rollback signal
interruption. No resize, new infrastructure, staged-patch commit, strategy
change, orders, 20-minute preflight or 10-hour evaluation is included.

No remaining source, space or lock blocker is established for this limited
attempt. Actual native hook compatibility, timing and complete drain must be
proven by its evidence before any separate 20-minute authorization request.
