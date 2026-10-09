# Existing production infrastructure repair — October 9 UTC

Authorized scope: MAIN infrastructure, same Railway service and 10 GB volume;
no strategy edits, shadow services, orders, historical deletion or paid resources.
Parent is the actual live MAIN/COCKPIT commit
`7a0b661291743222c1f6ac30df8b42e274fd6c73`. Exact rollback configuration and all
three live deployment identities are in `evidence/infrastructure_20261009/rollback.json`.

## Information delivery

The public proxy previously collapsed every exception into a generic 503.
Its source deadline check could fail after a valid worker response expired in
transport. Existing Railway HTTP logs show repeated 503s in 4–131 ms, below
the 400 ms worker timeout. Other incident windows have worker BrokenPipeError
traces after the caller gave up. The worker used a single HTTP request thread
shared with `/revalidation`, which can wait 200 ms for a binding.

The repaired proxy distinguishes valid-but-expired source data (200, full-schema
WAIT with all source values redacted) from worker transport failure (503),
invalid upstream output (502) and internal errors (500/502). Source deadlines,
quote identity, original clocks, nonce echo and no-store headers remain enforced.
No expired frame is returned as AVAILABLE. Identity requests remain fail-closed.
The worker now has at most eight request threads and a 16-connection backlog,
within its existing 128-FD envelope. Information read-clock ordering remains
serialized; revalidation waits no longer block it. Inference stays off GET.
Client disconnects are bounded diagnostics rather than repeated tracebacks.

## Storage

Railway initially reported 8.705294336 GB used of 10 GB. The mounted filesystem
reported 7,954,300,928 bytes used, 1,422,872,576 free, and 9,393,950,720 total at
02:40:24 UTC. These are different platform/filesystem measurements.

The largest growing file was `/data/btc15_information_frames_v1.jsonl`,
2,634,225,656 bytes at that time. The retired qualification file remained
918,448,535 bytes across production snapshots; the earlier process cleanup is
still in effect. Native snapshot, model-input, settlement and trading journals
remain protected. The filenames containing “shadow” are historical names,
not proof of redundant current processes.

New information frames are written losslessly as fsynced gzip members to daily,
process-specific `.jsonl.segments/*.jsonl.gz` files. Each record retains the
same schema, frame identity and exact frame bytes. Partial writes are completed;
a failed segment cannot accept later records. Restarts use a new segment. The
existing reader now reads both the original file and new segments, streaming
lines rather than loading the entire legacy file as a string. Corrupt evidence
fails visibly, never silently disappears from scoring.

The original 2.6 GB file and every other historical file remain untouched.
Storage telemetry includes largest directories, the three owned processes,
open volume write paths and low-capacity warnings. No automatic pruning or
historical archiving is enabled. This reduces new storage growth; it does not
reclaim existing history or guarantee unlimited retention in a finite volume.
Substantial recovery requires separate approval to archive protected evidence.

## Validation and deployment boundary

Focused local regressions cover expiry versus internal failures, actual blocked
revalidation routing, timeout classification, gzip roundtrip/restart/day changes,
short writes, failed/corrupt segments, and old/new evidence reader compatibility.
Existing information integration/ingress and supported EARLY management checks
pass. MAIN and V81 freeze verification and MAIN assembly pass. The actual
cockpit explanation-stability regression passes, including native CALL through
HOLD/WATCH/PROTECT/EXIT and expiry/rollover. No live signal-scoring campaign ran.

No FINAL, EARLY, SCALP, reversal, frozen model, source-owner, freshness, trading
threshold or cockpit asset file is edited. Only MAIN needs deployment. Keep
the existing unrelated staged Railway patch uncommitted.

Rollback MAIN by restoring the original start command and reconnecting the
original pinned source in rollback.json. The original raw information file can
resume appending; the new compressed segments remain preserved. Use this repair's
reader to include those segments in subsequent historical evidence analysis.
Do not change the frozen manifest; the release manifest only updates reviewed
infrastructure bytes and adds the three information delivery/storage modules.

This commit is a predeployment record. A separate result receipt records actual
Railway SUCCESS and bounded production verification; a queued build is not success.

## Live result — 02:57 UTC / 10:57 p.m. Eastern

MAIN deployment `2d1ca61c-51b5-415d-8cca-02ed86a7cb69` reached SUCCESS at
02:54:22 UTC on `b8bd240b4e27a949e7db0388b8fc9bae24d83ef5`.
COCKPIT and SCALP retain the original SUCCESS deployments in rollback.json.
The unrelated Railway staged patch remains uncommitted.

An existing production HTTP-log sample from 02:54:56 to 02:55:47 contained
501 information requests, all HTTP 200, with no 503. At 02:56:18 a real
source-expiry-in-transit event was explicitly classified as redacted WAIT/200.
Cockpit source logs showed both AVAILABLE/QUALIFIED_INFORMATION_ONLY and
honest WAIT/INPUT_UNAVAILABLE or BTC_STALE_OR_NONCAUSAL responses. This is a
bounded verification, not an uptime promise or relaxation of freshness.

The browser showed current contract identity/target, live quotes and BTC/BRTI,
FINAL UP 90.3% with native PASS (distance/range gate), genuine EARLY WATCH
evaluation, and independent SCALP UP WATCH/CAUTION with its existing origin.
MAIN journal sequence advanced 32 to 40 with queue 0 and drops 0. No application
JavaScript error was observed; one browser-extension metadata error was unrelated.
The native EARLY/SCALP/FINAL files and cockpit assets match the pre-repair commit.

New live information storage wrote a complete 1,798-byte record in 917 compressed
bytes; all new frames remain preserved. The old information file remains
2,636,133,318 bytes. Railway reports 8.710774784 GB used of 10 GB: approximately
1.289 GB nominal capacity remains. The filesystem startup sample independently
reported 1,414,885,376 free bytes. No historical space was reclaimed.

### Remaining approval boundary

Recommended first recovery: losslessly archive ONLY the inactive
`/data/btc15_information_frames_v1.jsonl` (2.636 GB) on the existing volume,
stream-verify the decompressed SHA-256 against the original, update the evidence
reader to include that exact archived file, and only then replace its uncompressed
representation. Abort without removing the original if capacity, hash or reader
verification fails. No new storage/service cost and no discarded records. Exact
recovered bytes can only be known after compression. The separate 918 MB retired
qualification CSV is another protected archive candidate, not approved for removal.

Historical archiving/replacement has NOT been executed. User approval is required
by the explicit task instruction. The result and process/storage evidence are in
`evidence/infrastructure_20261009/result.json`. No long live testing campaign ran.
