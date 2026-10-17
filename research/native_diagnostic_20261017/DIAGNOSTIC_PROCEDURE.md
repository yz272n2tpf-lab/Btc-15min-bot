# 60-second native diagnostic — proposed, NOT executed

**Decision: NOT READY for activation.** Exact source packages are complete.
Storage, mounted-volume lease, exact native dependency/runtime checks, billing
headroom and a selective deployment route must be cleared first. Each stage
requires separate authorization. This document grants none.

## Immutable approval inputs

- Engineering baseline: `0daf1ac442c4f5276d3e748421bfd13deef4ea1f`.
- MAIN/information package: branch `research/native-diagnostic-main-20261017`,
  commit `e2294683d2ec268d921df0277f5a9cb518f2e67d`, tree
  `8d640adab13a19b4990107474de114b51fb50bf8`.
- V81 package: branch `research/native-diagnostic-v81-20261017`,
  commit `f7c32d04556335632c862515a9ee1b742ad88ad3`, tree
  `30034850c51d515e0ce442277641216f9bc57ef3`.
- Exact archives and manifests: `PACKAGES.json`. Information is already the
  MAIN worker; install the shared MAIN archive once. No third service.
- Draft campaign: `campaign.approval-draft.json`, SHA-256
  `12b17ac651578d3325fadbc39fd340e9e6dc700d769c9ff5d6678e004d191949`.
  Run ID `DIAG_20261017_e2294683_f7c32d04`; 60 seconds per role from its
  bootstrap, including startup. This is not a synchronized 60-second cohort
  or a claim of sustained capacity. Preserve role start/end clocks and overlap.
- Exact current/proposed start commands, build/manifest pins, recorder variable
  values and rollback identities are in `PROPOSED_SETTINGS.json`. These are
  files only; no Railway settings were written. The draft's capture opt-in
  becomes operative only after separately approved installation and activation.

## Preconditions — stop at the first failure, no retry loop

1. Refresh deployment and source identities. MAIN must still be
   `c0993600-34b7-4501-92cd-b8d4a934b68a` / `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`;
   V81 must still be `21bf7fd3-c294-46d9-8a0a-f551cce7a303` /
   `c14b3f9b04caea13e62bcdd6fb0e5990049aa17b`. Reconcile any mismatch before
   continuing. Read back native release files and dependency versions through
   the existing pinned private SSH identity. Never print API keys.
2. Require exact `statvfs`/`disk_usage('/data').free` on each producer to be at
   least **2,181,038,080 bytes (2.03125 GiB)**, plus a measured allowance for
   native-journal growth during deployment, capture and drain. MAIN includes
   both 16 MiB roles; V81 has 32 MiB. The current V81 metric-derived nominal
   unused space is only 1,785,664,000 bytes; do not lower the reserve. No resize
   or evidence deletion is authorized. If refreshed space fails, obtain a
   separate minimal storage decision before requesting diagnostic activation.
3. Verify existing research volume `2dba2ef6-b84d-4abf-9d04-58a1e77082c5` at
   `/research-evidence`, one replica, serial jobs, restart NEVER, and >=5 GiB
   actual free space for this diagnostic's raw files, DB, full rollback journal
   contingency, bounded ledger exports and reserve. Its current deployment has
   **zero running replicas**. Starting it or deploying the new lease code is
   separate authorization; neither happened here. Then run exactly once:

   ```sh
   python -B -m research.native_diagnostic_20261017.lease_probe
   ```

   Require its PASS receipt: exact research identity, actual mounted directory,
   independently contested volume lock, second ReaderLease rejected, SIGKILL
   of the probe's own child, successful reacquisition, unchanged lock inodes.
   No historical DB is opened; lock files are never unlinked. A busy lock is a
   blocker, not permission to kill another process. This is containment of the
   unresolved concurrent SQLite failure, not a filesystem durability proof.
4. Confirm billing cycle spend, credits, limits and remaining approved budget.
   The connector exposes resource metrics, not account billing balances.
   `STORAGE_COST.json` contains incremental scenarios, not verified headroom.
5. Verify a **service-scoped** installation route that leaves pending patch
   `ead9997e-b5b7-4668-a612-e8417e197838` and all four changes untouched.
   The available connector's `accept-deploy` commits the entire patch and is
   forbidden. No selective commit route has been verified in this session.
   Do not clear, save over or apply the pending changes to make deployment work.
6. Confirm the exact pinned dependencies from each unchanged `requirements.txt`
   in the native build/runtime. The local test interpreter has different
   versions and no requests distribution; local tests are not a native
   dependency qualification. Run the existing release verifier and recorder
   `attest` against the exact package and approved config without calling
   bootstrap/capture. Any mismatch blocks activation; never weaken the guard.

## Approval A — exact installation and one diagnostic

The approval must name both package commits, both existing services/volumes,
the config hash, proposed settings, spending limit, one attempt, and rollback
scope. Information shares MAIN's approval. A default-off deployment and a
capture-enabled deployment are different actions; explicitly approve the
chosen operation. A single coordinated deployment with the approved config
minimizes restarts, but must pass all prerequisites first.

1. Preserve a private before-state receipt of both service settings and
   recorder variable values for rollback; do not expose secrets. Recheck the
   seven volume IDs/allocations and four-change pending patch.
2. On each existing producer, create the new control directory
   `/data/btc15_recordings-control/DIAG_20261017_e2294683_f7c32d04/` with mode
   0700 and write the exact canonical draft bytes as `campaign.json`, mode
   0600, using exclusive creation and fsync. Refuse any existing file/campaign
   directory; never append/reuse an earlier role or overwrite historical
   evidence. Verify its SHA-256 equals the approval hash. This is an approved
   future configuration write, not performed by this preparation.
3. Through the verified selective route, install only the two pinned source
   packages and apply exactly `PROPOSED_SETTINGS.json`. Keep current start
   commands identical except their approved build and manifest pins; the three
   recorder variables point to the exact config. No strategy, timing, market,
   BRTI, authentication, health-check, replica or order setting changes.
4. Observe actual successful deployment IDs and exact runtime build/manifest,
   service, volume and environment receipts. `ATTEST_AT_START` binds the new
   platform-assigned IDs; independently confirm them through the control plane.
   A deployment ID is not fabricated in advance. Stop if any role binds to an
   unexpected build or MAIN/information report different runtime identities.
5. Capture admits for at most 60 seconds per role. The current watchdog closes
   admission at the deadline; accepted work drains separately. No native owner
   is stopped. Monitor existing `health.json`, original proof queues and native
   health; do not add endpoints, polls of market sources or services.

| Role | Compressed cap | Decoded cap | Envelope cap |
| --- | ---: | ---: | ---: |
| MAIN | 16 MiB | 128 MiB | 20,000 |
| V81 | 32 MiB | 256 MiB | 200,000 |
| Information | 16 MiB | 128 MiB | 50,000 |

Queue stays 32 MiB / 16,384 items; observation charge cap 4 MiB; batches stay
1 MiB / 256 envelopes. Existing timing, freshness, chronology, schema and loss
checks remain strict. Internal seal reserves cause an earlier finite stop;
caps are ceilings, not promises of usable payload capacity.

## Stop, seal and evidence preservation

First admission rejection (including oversize or queue loss), original journal
gap, invalid timestamp schema, writer error, identity mismatch, quota/reserve
breach, native health regression or timing failure stops this attempt. The
existing limits include >5 ms individual measured hook or >1% over 1 ms after
100 calls per label. Some startup/callback overhead still requires native
measurement; source-code equality does not prove unchanged wall-clock timing.

The first failure remains INCOMPLETE. Do not enlarge the queue/observation cap,
relax freshness, reclassify gaps, suppress failure or immediately retry. The
original oversized payload is not reconstructed: record only its actual kind,
charge, raw length/type and field count when the diagnostic encounters it.

For operator stop, use the existing pinned private SSH transport from the
authorized research environment with the exact config on stdin:

```sh
# MAIN service: existing recorder only, no process signal
python -B -m ops.live_recording.remote finish --roles main,information < campaign.json
# V81 service: existing recorder only, no process signal
python -B -m ops.live_recording.remote finish --roles v81 < campaign.json
```

These are remote `/app` commands, not local producer commands to run here.
The matching run/role identities are mandatory. The capture stop joins for
5 seconds; a drain timeout is permanently INCOMPLETE even if a late seal appears.
The remote command waits at most 8 seconds for seals. Preserve all partial,
late and failed records. Do not kill native owners to force a seal. Do not
invoke stop on an earlier campaign.

Copy health diagnostics before any rollback, then use the existing private
finisher, once, serially on the isolated research volume:

```sh
python -B -m ops.live_recording.finish \
  --config /research-evidence/approved/DIAG_20261017_e2294683_f7c32d04/campaign.json \
  --output /research-evidence/DIAG_20261017_e2294683_f7c32d04-reader
```

Provision the approved private config there first; do not copy producer secrets.
This uses the existing bounded reader with a 1 GiB DB ceiling and 240-second
reader budget, separate from capture. It transfers only seal-listed bounded
objects with SHA-256 checks. Store raw compressed bytes, identity/config,
health, terminal/seal/partial-seal receipts, deployment observations, ledger,
reader logs and recovery archive. Preserve producer copies and all prior runs.
An unsealed failure requires a separately reviewed bounded evidence recovery
plan; never broaden the finisher's allowlist or delete data to make it pass.

## Rollback — separately included in approval

First disable admission through the exact campaign stop above, drain/preserve
all possible evidence, then use the verified service-scoped route to set
`BTC15_RECORDING_ENABLED=0`. Do not assume an environment edit changes an
already running process; the in-process stop is required. Leave the config and
evidence files in place. If application health is impaired, the approved
operator rollback can precede a clean seal; record that capture as INCOMPLETE.

Restore MAIN deployment/source `c0993600-34b7-4501-92cd-b8d4a934b68a` /
`dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`, V81
`21bf7fd3-c294-46d9-8a0a-f551cce7a303` /
`c14b3f9b04caea13e62bcdd6fb0e5990049aa17b`, and the exact prior start commands
in `PROPOSED_SETTINGS.json`. Preserve all unrelated settings and pending work.
Verify retained-image availability immediately before approval; if unavailable,
an exact-source rebuild needs approval. Do not run the local installer rollback
inside `/app` or `/data`; it intentionally forbids that use.

After rollback, verify native health, source/manifest identity, signal-only
behavior, recorder disabled, four staged changes unchanged, seven historical
volumes unchanged, and evidence still present. No automatic retry or onward run.

## Pass evidence and next approval

All three role identities/seals must agree, zero losses or unaccounted native
sequence gaps, accepted work fully durable, source clocks/timing strict, native
owners healthy, and reader associations verified for the emitted scope. Report
missing BUY/management/settlement coverage honestly. Absence during 60 seconds
is not fabricated and does not prove full EARLY readiness. Record admitted and
durable byte/item deficits, fsync/hook timings, per-kind sizes and compressed
growth; reject inconsistent telemetry snapshots from rate calculations.

Only after reviewing a passing diagnostic, separately approve one 20-minute
native preflight; only after its authentic gates pass, separately approve the
10-hour EARLY evaluation. Then analyze and improve EARLY, complete production
acceptance, launch the signal-only bot, and review several days of forward live
evidence. There is no automatic transition between stages.
