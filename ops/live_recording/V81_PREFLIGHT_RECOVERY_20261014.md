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

## Mandatory gates before any new live preflight or 24-hour test

1. Preserve all raw previous segments and failure receipts, marking missing events as unfilled gaps.
2. Measure realistic quote/native evidence distribution and sustained/peak writer throughput without lost observations, while proving no cadence or decision-path drift.
3. Review appropriate explicit role-specific recording budgets and sufficient V81 storage. Do not mask queue losses, disable safeguards, downsample, or remove original evidence to claim success.
4. Obtain a genuine complete 20-minute live preflight with MAIN, V81, Information, final hash seals, independent retrieval and verified reader/report.
5. Qualify the day-profile reporting workspace: FINISH_CAMPAIGN currently reserves roughly 59 GiB for the 24-hour profile, exceeding the 32 GB Codespace ceiling.
6. Obtain separate approval for any production code/configuration changes. The four pending unrelated Railway changes must remain staged and untouched.

**Conclusion:** offline repair candidate is real and tested; live capture and full-day readiness remain unqualified.
