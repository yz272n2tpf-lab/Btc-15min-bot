# BTC15 V81 October 14 preflight: measured failure and guarded recovery

**Status: INCOMPLETE / 24-HOUR NO-GO. Production frozen.** No merge, Railway configuration change, restart, redeploy, or production evidence certification is authorized by this candidate.

## Observed evidence (not inferred)

- Campaign ID: PF_20261013_4d0f8ed15e; configured preflight duration 1,200 seconds.
- V81's persisted terminal-status.json, independently fetched with authenticated SFTP, reported:
  - failure = DRAIN_TIMEOUT; stopped = false; no seal.json at the inspected location.
  - elapsed approximately 15.13449 seconds, records = 5,904, raw_bytes = 5,683,274, compressed_bytes = 3,587,665.
  - writer QUEUE_BYTES loss count = 1,470; peak queue 33,554,430 bytes with a 33,554,432-byte queue limit.
  - archive_failed = false in that terminal snapshot; partial compressed segments and receipts were saved.
- Native MAIN and V81 service deployments stayed online and signal-only. This is not proof of a complete capture.
- FINISH_CAMPAIGN returned STOP_OR_SEAL_INCOMPLETE for V81 and the independent report did not complete. Missing events cannot be reconstructed from that partial recording.

## Rate arithmetic: initial 15 seconds only

The observed failure-window averages were ~390 V81 records/s, ~375,518 raw bytes/s, and ~237,052 compressed bytes/s. These are **not qualified steady-state rates**. Were they hypothetically sustained:

| Metric | 20-minute equivalent | Day profile (24h + 9m) |
| --- | ---: | ---: |
| Records | ~468,000 | ~33.9 million |
| Compressed bytes with OLD per-record gzip | ~271 MiB | ~19.2 GiB |
| Reviewed V81 profile cap | 75,000 records / 64 MiB | 1,500,000 records / 512 MiB |

The V81 role gets one quarter of the profile's 300,000 total preflight or 6,000,000 total day record allowance. Faster I/O cannot by itself solve these record quotas without explicit profile and capacity qualification. Batched gzip can change real compressed-byte rates, but it cannot just discard or omit original records to satisfy a budget.

V81 has a separate 5 GB Railway persistent volume; prior free-space measurements were approximately 2.9 GiB. MAIN has been expanded to 20 GB. Neither is the independent reporting workspace.

## Research branch only

Branch: research/btc15-v81-incomplete-drain-recovery-20261014 (based on deployed V81 commit c14b3f9b04caea13e62bcdd6fb0e5990049aa17b).

- Preserve truthful shutdown status. Shut source admission once and seal only after the off-path writer actually exits. Dropped events leave the session INCOMPLETE.
- Isolate batch compression and fsync to the V81 recorder's evidence journal. Preserve exact canonical JSONL sequence and hashes. No change to strategy, signal-only execution, quote-proof owner queue, MAIN/Information journal implementation, or order behavior.
- Interrupted batch writes fail closed; never append behind possibly torn gzip data or falsely attest a complete history.
- Offline regressions check codec and chain, multi-segment rollover, synthetic throughput near ~590 events/s with zero losses, interruption, and prior proof-owner behavior.

The fixture contains synthetic repeated text, so its compression ratio is **not** a verified projection of live V81 disk usage, and neither CPU nor cloud filesystem behavior is guaranteed by local CI.


## Additional finding: recorder loss-counter polling was not reliable

The inherited quote-proof writer uses an itertools.count() per loss class. Its
reader also invokes next() on the iterator. Repeated status polling therefore
advances the same counter, even without a gap() call, and exposes a delta rather
than a monotone cumulative loss. That behavior is unsafe for a recorder health
gate that calls status() repeatedly. It can produce phantom losses and make
persisted counters different from true lifetime event drops. Accordingly the
prior reported 1,470 QUEUE_BYTES figure is a **diagnostic reading**, not an
independently reconciled lifetime drop count. The near-full 32 MiB queue and
INCOMPLETE receipt are genuine failure evidence.

The candidate now uses RecorderOffPathProofWriter only for the off-path evidence
recorder. Its cumulative loss snapshot subtracts polling increments while
preserving actual gap() increments. The authoritative/native quote-proof writer
class and queue stay untouched. Offline tests verify repeated zero-loss polls
remain zero, and an actual oversize drop remains visible even after 75 status
reads and produces an EVIDENCE_GAP in the archive.

## Latest tests and capacity screening

- CI: https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38664161191
- 19 / 19 offline tests passed; no Railway or live data was used.
- A 6,000-event high-entropy synthetic quote workload with 4 ms artificial
  fsync latency finished in about 12.53 seconds, with zero admission losses,
  20,050,023 compressed bytes, and 1,561,920 peak queued bytes.
- A separate 9,000-event compressible fixture finished in about 15 seconds with
  zero observed losses. Their very different compression ratios demonstrate
  why the synthetic compression result cannot be substituted for genuine data.
- The new read-only v81_capacity_review.py rejects malformed or incomplete
  measurements; a saved failure-window receipt remains NO_GO_UNQUALIFIED for
  both current profile capacities. This tool cannot grant any campaign approval.

Neither synthetic workload proves real Railway disk throughput, true quote
payload distribution, post-rollover state, 20-minute continuous sealed capture,
or 24-hour suitability. Both profile records and decoded-byte caps still need
explicit review with measured real-source data; batching alone cannot resolve
those hard ceilings.

## Mandatory gates before any new live preflight or 24-hour test

1. Preserve all raw previous segments and failure receipts, marking missing events as unfilled gaps.
2. Measure realistic quote/native evidence distribution and sustained/peak writer throughput without lost observations, while proving no cadence or decision-path drift.
3. Review appropriate explicit role-specific recording budgets and sufficient V81 storage. Do not mask queue losses, disable safeguards, downsample, or remove original evidence to claim success.
4. Obtain a genuine complete 20-minute live preflight with MAIN, V81, Information, final hash seals, independent retrieval and verified reader/report.
5. Qualify the day-profile reporting workspace: FINISH_CAMPAIGN currently reserves roughly 59 GiB for the 24-hour profile, exceeding the 32 GB Codespace ceiling.
6. Obtain separate approval for any production code/configuration changes. The four pending unrelated Railway changes must remain staged and untouched.

**Conclusion:** offline repair candidate is real and tested; live capture and full-day readiness remain unqualified.
