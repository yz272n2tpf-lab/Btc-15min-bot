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
