# Native diagnostic failure corrections — 2026-10-17

**FAIL / NOT READY for a diagnostic rerun.** Offline fixes are tested; the exact
native candle/publication traces and native latency attribution remain unproven.
No production operation, configuration change, capture, order, or research-service
restart was performed. This is a source patch, not an activated installation.

Baseline: `research/native-diagnostic-result-20261017`,
`8fa2da1543888653ab909c494b29f8ce013b73cb`.
Result branch: `research/native-diagnostic-fixes-20261017`.
The commit containing this report is the result source identity.

## Four failures and narrowly scoped corrections

| Failure | Finding and correction | Verification status |
|---|---|---|
| MAIN QUOTE_ACCEPT / V81 QUOTE_RECEIVE latency | The quote callbacks enqueue immutable fields; they do not serialize, compress or fsync. However, the inherited `Queue.put_nowait` acquires `Queue.mutex` with a blocking acquisition. A focused test demonstrates that wait. Recorder-only admission now acquires that mutex without waiting, preserving the same queue and limits. Contention records `ADMISSION_BUSY` and stops capture; it is never concealed as success. Slow quote hooks now record thread CPU and off-CPU time separately. | **PARTIAL.** Blocking path removed and tested. Native maxima of 72,054,830 ns / 21,521,287 ns cannot be attributed to that mutex from aggregate counters. No claim that native overhead now meets 5 ms. |
| MAIN candle chronology, sequence 308 | Pinned `completed_candles` shifts both native clocks to bucket end but explicitly retains the current bucket; native decisions filter it later. The reader incorrectly required every cache row to have ended at cache acceptance. It now preserves a valid current bucket as an uncompleted cache observation, without original-completed credit. It still rejects a bucket starting after acceptance. Completed provenance now requires the exact HTTP row received at/after bucket end and by cache acceptance; decision associations explicitly require candle clocks at/before the decision. | **PARTIAL.** Producer semantics and focused replay pass. Sequence 308's actual row, acceptance time and matching upstream response are not locally available. Its exact trace is not claimed resolved. |
| Admitted versus durable charge | `Archive.observe` removes `raw` and adds metadata for quote/HTTP observations. The old wrapper recomputed charge **after** this mutation, comparing unlike definitions. Charge is now computed on the immutable admission fields **before** observation processing. Existing proof jobs receive the same original admission charge after processing. Signed deficits expose over-credit. A clean seal now additionally requires exact admitted/processed/durable count and charge equality, empty queue/buffer, and no archive failure/loss. | **PASS offline; native byte-by-byte reconciliation pending.** Batching, wire deduplication, proof jobs, drain, seal, counter corruption, processing exceptions and fsync failure are covered. Original terminal counters are not rewritten or called recovered evidence. |
| Seven information publication failures | Existing `DurablePublisher.offer` labels every false return `INPUT_NOT_PUBLISHED`. The original publisher can return false for no source progress or for a fail-closed validation rejection. The saved failures contain only that generic reason. No evidence justifies reclassifying these seven events. | **BLOCKED.** No speculative publisher/association change. All seven failures remain failures and continue to make the existing windowed reader INCOMPLETE. |

Information failures: session `fa9847b012c249da8107f9e0767c84f2`, sequences
**141, 158, 185, 189, 209, 215, 227**. Candle failure: session
`6e5064b7967a49cc95acfe1964bd4ae1`, sequence **308**, partition 2.

The candle correction does not promote an old partial bucket when time advances.
It retains the recorded clocks and values and requires qualifying original HTTP
provenance. Unknown schemas, wrong clock relationships, changed OHLCV, missing
receipts and future decision inputs still fail. The original diagnostic remains
INCOMPLETE regardless of any corrected reader interpretation.

## Authentic counters retained exactly

These values come from the committed original terminal receipts, not a rerun.

| Role | Admitted observations | Durable observations | Admitted charge bytes | Old durable charge bytes | Old charge difference |
|---|---:|---:|---:|---:|---:|
| MAIN | 3,000 | 3,000 | 12,257,232 | 10,275,140 | 1,982,092 |
| V81 | 30,644 | 30,644 | 67,731,083 | 45,850,179 | 21,880,904 |
| Information | 146 | 146 | 19,358,782 | 19,358,782 | 0 |

All three receipts report zero terminal queue items/bytes/unfinished observations
and empty loss counters. Equal counts and a charge-definition defect do **not**
prove raw evidence completeness. We have not reconciled each original admission
against its captured bytes, repaired any original counter, or recovered any input.

## Tests and integrity

`test-results.txt`: **25 tests passed in 1.467 s**, Python 3.12.14, offline only.
Eighteen new regressions plus six existing candle tests and one existing
unbuffered-versus-batched envelope/hash-chain comparison were run. The new
multibatch test uses 1,200 declared synthetic admissions; no capacity campaign,
native capture, or 600,000-record test was run.

Covered: quote string/bytes charge mutation; exact multibatch accounting and
wire deduplication; pending and failed fsync credit; writer failure; proof-job
charge; complete drain/seal; counter discrepancy forcing INCOMPLETE; signed
over-credit; old blocking versus new immediate mutex rejection; queue limits,
ordering and losses; the unchanged 5 ms wall guard even with low thread CPU;
current/future/final candle receipt cases; exact decision cutoff rejection;
preservation of seven information failures; and authentic terminal counter checks.

Existing reader replay over the **same synthetic compressed files** produces
byte-identical window/issue/association ledgers on two fresh executions; completed
checkpoint resume returns the same result. Input SHA-256 hashes remain unchanged.
The existing 1,500-envelope comparison confirms identical raw envelopes and
hash chains between the original and batched journal. These are fixture proofs,
**not replay of the inaccessible authentic diagnostic segments**.

`evidence-and-scope.json` records original receipt hashes and protected source
attestation. All **23** files covered by the original result's SHA256SUMS still
match. The exact installed MAIN and V81 package copies were checked: all **38
MAIN / 14 V81 protected files** match their pinned hashes, and the three modified
recorder/reader modules have identical pre-patch bases in both packages.

Only these existing files change:

- `ops/live_recording/burst_journal_research.py`
- `ops/live_recording/capture.py`
- `ops/live_recording/reader.py`

FINAL, EARLY, SCALP, Kalshi integration, native clocks, entry policies, freshness
thresholds, the 5 ms guard, 1 ms p99 guard, signal-only controls and native proof
writer implementation remain unchanged. Actual timing performance is unqualified.
No historical artifact, volume or staged production change was touched.

## Exact missing observations; smallest next action

The sealed raw files exist in the prior research-volume inventory but are absent
from this checkout and `/research-evidence` is not mounted here. The connected
Railway interface exposes logs/configuration operations, not a file-read or exec
operation. The prior finisher exported reports, not these raw segments. No
service was restarted or reconfigured to obtain them.

Supply a **read-only export of the three existing sealed segments** and their
role identity/seal/terminal files from
`/research-evidence/DIAG_20261017_e2294683_f7c32d04-reader/raw/`.
The segments total **10,890,786 bytes**. Their exact relative paths, byte counts
and SHA-256 hashes are in `evidence-and-scope.json`. No new capture is required
for this export.

- MAIN: exact sequence 308 payload and preceding original Coinbase response
  records, to join bucket start/end, OHLCV, HTTP receipt and cache acceptance.
- MAIN/V81: exact quote/HTTP payloads, to reconcile the original charge difference
  admission by admission without changing a single recorded byte.
- Information: full vector chains and input/publication references surrounding
  all seven listed sequences, to reconstruct original input hashes and preceding
  publications. If these do not disambiguate a false return, the missing
  observation is the original publisher's **no-progress versus validation-reason
  branch**, together with its health readings and validation/publication clock.
  Those are not present in the generic failure records; no reason will be invented.
- Latency: the old run did not capture per-overrun thread CPU, queue-mutex wait
  or scheduler/GIL attribution. Existing raw bytes cannot recreate that timing.
  The mitigation and new slow-hook telemetry are candidates for a separately
  approved diagnostic only after the accessible-evidence failures are resolved.

The new mutex behavior deliberately trades a potentially blocking recorder call
for an explicit capture failure on contention; it has not demonstrated loss-free
native operation. This risk, the untraced seven publication failures and the
unreplayed authentic candle trace prevent a PASS. No deployment authorization
or diagnostic activation is requested by this result.
