# Proposed operational execution and diagnostic authorization inputs

**Nothing in this file is authorization. No commands here were executed
against Railway. Diagnostic approval is withheld while the README gates fail.**

## A. Small research-only access step

Use the existing research project `87ad03d5-e1d6-47d6-b1ea-159cd7594686`,
environment `12d241b7-23b4-4421-aafd-142e943555ee`, service
`1fff593b-8b09-4cc4-8c51-f9603082657f` and volume
`2dba2ef6-b84d-4abf-9d04-58a1e77082c5` mounted at `/research-evidence`.
Pin the new research source to the exact commit accompanying this report,
branch `research/native-operational-gates-20261017`. Preserve the Dockerfile,
one replica, 4-vCPU / 8-GB limits, volume and restart NEVER. No new service.

After separately approving that research deployment/start and checking account
headroom, replace only its old research command with:

```sh
timeout --signal=TERM --kill-after=10s 180s python -B -u -m research.native_operational_20261017.probe --authorized-research-only
```

This is the one-shot job, not the old `run_isolated` command. Verify terminal
job exit, then zero running replicas. A timeout/failure is a blocker, never an
automatic rerun. The five-minute compute planning allowance is $0.03; timeout
is a process bound, not a billing-enforced limit. No platform spend limit is
created. Preserve the new receipt and all partial output.

The probe first validates research identity/mount, key permissions and >=5 GiB
available space. It never creates or changes a host-key pin. Per producer it
uses one SSH attempt with strict existing known_hosts, 10-second connect timeout
and 45-second command timeout. It reads `/data` statvfs twice at least 10 seconds
apart, installed distribution versions and the exact source files enumerated in
`NATIVE_READ_PLAN.json`; no native owner is imported. Identity/source mismatch
aborts. SSH errors are not retried. Low space is reported without changing it.

It invokes the existing `research.native_diagnostic_20261017.lease_probe` once.
Required authentic result: volume-only contender rejected, full ReaderLease
contender rejected, SIGKILL of the probe's own child releases the lock,
reacquisition succeeds and lock inodes remain stable. No DB is opened and no
historical evidence is rewritten. It is not a SQLite crash-durability proof.
Never unlink locks or kill another reader. Keep every reader strictly serial.

`READS_COMPLETE` means measurements were collected, **not readiness PASS**.
Review dependency mismatch, source identity, actual free space, native growth
allowance and lease receipt. Complete the already existing package compatibility
checks under the observed native dependency set before diagnostic approval.
Short net disk-growth samples can hide buffered writes; do not extrapolate them
as an authoritative worst-case rate or a ten-hour retention measurement.

## B. Billing readout without a mutation

An authenticated owner can use the official CLI in their existing authorized
account session (credentials are never copied into chat):

```sh
railway usage --workspace b5c2a37f-467f-4f7a-ad26-4c2268769b3e --period current --json
railway usage projects --workspace b5c2a37f-467f-4f7a-ad26-4c2268769b3e --project baea4e22-d004-4434-b2c5-81a7fbc05086 --period current --json
```

Record billing-period boundaries, current/estimated bill, current resource
usage, subscription/credits and compute/agent limits separately. Verify credits
and balances from the account billing page when the usage response omits them.
No usage-limit setter is authorized. If an authentication/permission error
occurs, stop that access path and report it. A read-only browser fallback needs
separate approval because the available service plugin lacks billing access.

## C. Exact selective production route — later approval only

Production project `baea4e22-d004-4434-b2c5-81a7fbc05086`, environment
`61775c5d-c583-4dfc-af41-f25578856fd9`.

Pending patch `ead9997e-b5b7-4668-a612-e8417e197838` has four source changes
solely for shadow service `84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1`. Preserve its
ID, status, count and exact per-field values. Do not apply, discard, restage or
recreate it. No environment-wide Deploy, Alt+Deploy, accept-deploy or
`EnvironmentPatchCommitStaged` is allowed.

Use a reviewed official CLI with the direct JSON patch implementation inspected
at commit `05ed159796ef6bf15de0dab388b1054c1af6f395`; check the installed binary's
version/source provenance before approval. The schema documents
`environmentPatchCommit(environmentId, patch, commitMessage)` as committing the
provided patch. The CLI passes only the supplied JSON; it does not stage it or
call the staged-commit operation. This verifies the client/API contract, not
account permissions or a live backend mutation. If platform behavior cannot
preserve the existing staged patch, stop; do not fall back to a broad commit.

The prepared input is
`ACTIVATE_NOT_AUTHORIZED.patch.json`, SHA-256
`b6b130b13169b3c3b71494e283005c5285c6a54fc54fb4d126c796c4a0662926`.
It names only MAIN `ab28dca6-7bea-4956-bdb9-dbb7b4c74635` and V81
`6025e83e-a41c-4e0a-8c16-f71120bd501b`, their candidate branches/commits,
approved start commands and exactly three recorder variables. All other fields
are omitted. Information runs in MAIN and needs no third operation.

After ALL prerequisites pass and separate approval explicitly includes producer
deployment/restart, one diagnostic and rollback:

1. Read back sources, deployment IDs, settings, seven volumes, pending patch,
   actual free bytes and account headroom. Stop on drift. Preserve secret-bearing
   before-state privately; never dump environment variables into logs.
2. Follow the baseline procedure to exclusively create the new private control
   file on each existing volume, with fsync and hash verification. No overwrite:
   `/data/btc15_recordings-control/DIAG_20261017_e2294683_f7c32d04/campaign.json`.
   Config hash `12b17ac651578d3325fadbc39fd340e9e6dc700d769c9ff5d6678e004d191949`.
3. Submit exactly the reviewed JSON once. This is a **live production mutation
   and capture activation**, not a preview or a command authorized now:

   ```sh
   railway environment edit --project baea4e22-d004-4434-b2c5-81a7fbc05086 --environment 61775c5d-c583-4dfc-af41-f25578856fd9 --json --message 'Approved BTC15 single 60-second diagnostic' < research/native_operational_20261017/ACTIVATE_NOT_AUTHORIZED.patch.json
   ```

4. Observe actual successful deployment IDs and bind them through the existing
   `ATTEST_AT_START` mechanism; verify candidate source/manifest/runtime pins.
   Refresh the staged-patch contents and all seven volumes immediately. They
   must remain unchanged. No broad automatic repair is allowed on mismatch.
5. Monitor existing health/admission/queue diagnostics. Sixty seconds is per
   role including startup; it is not guaranteed synchronized overlap. Do not
   extend duration to obtain a BUY or settlement. Seal and transfer through the
   existing private finisher, serially, following the baseline procedure.

## D. Hard bounds and stop conditions

Compressed caps: MAIN 16 MiB, information 16 MiB, V81 32 MiB. Decoded caps:
128/128/256 MiB respectively. Envelope caps: 20,000/50,000/200,000.
Queue 32 MiB / 16,384 items; observation charge 4 MiB; batch 1 MiB / 256.
Producer reserve 2 GiB plus initial capture capacity and reviewed native growth.
Research available space >=5 GiB; reader DB <=1 GiB; reader budget 240 seconds.
These do not grant capacity or duration beyond the existing diagnostic profile.

Stop admission on the first loss/rejection/oversize, original native-journal
gap, invalid candle schema, identity mismatch, quota/reserve problem, writer or
drain failure, timing failure or native health regression. Existing measured
hook limits remain >5 ms individually or >1% over 1 ms after 100 calls per label.
Retain the first failure as INCOMPLETE; no relaxed guard, larger cap or retry.
Collect actual payload-kind/charge diagnostics; never reconstruct missing data.

The recorder watchdog closes admission at 60 seconds; drain is separate. For
operator stop, invoke ONLY the matching run via existing pinned private SSH:

```sh
# Remote /app in MAIN, approved config on stdin
python -B -m ops.live_recording.remote finish --roles main,information < campaign.json
# Remote /app in V81, approved config on stdin
python -B -m ops.live_recording.remote finish --roles v81 < campaign.json
```

Drain join is five seconds; seal wait at most eight. Timeout remains INCOMPLETE
even if a late seal appears. Preserve raw, partial, terminal, health and identity
receipts before rollback. Do not kill native owners to force a seal. Unsealed
recovery requires its own bounded review; never delete historical data.

## E. Exact-source rollback input — separately included in later approval

The immutable rollback source identities and prior start commands are in
`ROLLBACK_EXACT_SOURCE_NOT_AUTHORIZED.patch.json`, SHA-256
`20f286b2b0e798818bf7587002331a98b9f72034f8ab530e3b1349236a6bb16d`.
It restores the prior source commits/branches and start commands for these two
services, with recorder enabled explicitly set to `0`. Existing config paths
and evidence files are retained; this safety rollback does not claim to restore
unknown secret/variable values byte-for-byte.

First stop the matching recorder admission and preserve evidence as above.
The later approval may authorize this exact-source rebuild route once:

```sh
railway environment edit --project baea4e22-d004-4434-b2c5-81a7fbc05086 --environment 61775c5d-c583-4dfc-af41-f25578856fd9 --json --message 'Approved BTC15 diagnostic exact-source rollback; recorder disabled' < research/native_operational_20261017/ROLLBACK_EXACT_SOURCE_NOT_AUTHORIZED.patch.json
```

This route can rebuild/redeploy and has build-time downtime risk; it is not an
instant retained-image switch. Retained MAIN deployment
`c0993600-34b7-4501-92cd-b8d4a934b68a` and V81 deployment
`21bf7fd3-c294-46d9-8a0a-f551cce7a303` currently advertise reusable builds.
If choosing a retained-build rollback instead, review its service-scoped
settings-restoration sequence before approval; do not improvise a second route.
Do not execute both rollback routes or use the archive installer inside `/app`.

Verify terminal SUCCESS, old source/manifest, native health, recorder disabled,
signal-only behavior, unchanged pending patch and volumes, and retained evidence.
An impaired native owner can justify the specifically approved rollback before
clean sealing, but the capture is then INCOMPLETE. Stop after this one attempt.

Review authentic diagnostic results before separately authorizing 20 minutes;
review that preflight before separately authorizing the fixed 10-hour EARLY run.
Missing event/settlement coverage remains missing evidence, not a PASS.
