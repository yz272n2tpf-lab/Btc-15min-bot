# BTC15 EARLY native evidence — bounded reader inventory real-data acceptance (2026-10-16)

## Decision

**PASS — first bounded structural stage of the EXISTING reader on immutable real MAIN/V81 evidence.**

**NOT YET QUALIFIED:** complete 24-hour native recording, official contract-level Kalshi quote replay, original FINAL/EARLY/SCALP lifecycle associations, missing-source recovery, trading strategy profitability or production deployment. Do not label this result "the 24h EARLY validator passing."

## What was implemented

- Existing module `ops/recording_workflow/evidence.py` gained `streaming_window_inventory`.
- It scans original `.jsonl.gz` source members in original verified session/sequence order (sort by first record sequence, never random filename suffix), validates every original per-record SHA-256 and previous-hash chain, and checks START/clean STOP, evidence class, file checksums before and after, no duplicates/out-of-order sequence, and explicit lost-evidence indicators.
- It bounds each incremental inventory slice to <=20,000 original envelopes and <=8 MiB decoded data, with 900-second **observed-clock** coarse bucketing. Every source record is counted and referenced by original `file`/line range. It does **not** claim that these are official Kalshi contract windows (not all events have timestamps).
- Original raw gzipped archive remains immutable; no trading source input or model inference; no per-record SQLite index written in this stage.
- Any gap remains a reported gap; bad SHA/sequence, missing STOP, source-file mutation or output collision prevents a successful final manifest. `complete_market_evidence=false`, `early_strategy_qualified=false`, `actual_contract_alignment_verified=false` explicitly.
- Seven new focused tests passed, as did the four prior batching tests: GitHub Actions run `38929497607`, total **11/11 PASS**. Tests include comparability with original index count, corrupt envelope SHA, dropped original sequence, incomplete sessions, loss preservation, finite windows and no overwrite.

## Actual Railway measurements

Isolated project `btc15-early-capacity-test`, existing `early-probe-scratch` 100,000 MB volume. Deployment `dc94917a-2e10-433c-b3a0-0b3bc36b7b5b` status SUCCESS, same immutable original October 13 MAIN/V81 gzipped evidence already preserved in isolated volume.

| Item | MAIN | V81 |
|---|---:|---:|
| Records scanned, SHA/sequence verified | **2,942** | **26,484** |
| Decoded evidence bytes | 8,576,026 | 24,097,297 |
| Original source archive segments | 1 | 2 |
| Bounded structural windows | 3 | 4 |
| Maximum records in one slice | 2,722 | 9,040 |
| Maximum decoded bytes in one slice | 8,388,037 | 8,388,331 |
| New compact window inventory bytes | **2,111** | **3,036** |
| Prior full per-record SQLite index bytes | 1,454,080 | 12,648,448 |
| Original evidence-gap envelopes retained | **1** | **83** |
| Records without their own observed receipt clock | 889 | 8,889 |
| Observed-order clock regressions | 0 | 0 |
| Streaming stage wall-time | 0.287 s | 2.329 s |
| Measured process maximum RSS | ~19 MiB | ~19 MiB |

- MANIFEST SHA-256 MAIN `b9c6c356a44db9eb0a4198d2f6207e6313e0edf1025035eb953fd73a84cb401b`.
- MANIFEST SHA-256 V81 `9ec775debc320e264d26014dd6648a6a0080d5f9bfd1426ce1a7f8860ae63cb9`.
- The two index representations are **NOT semantically equivalent**. The small inventory supports structural audit/segment location, while the old index supports per-record dependency lookup needed by the current `CampaignVerifier`. Do not advertise the smaller file as a drop-in full-reader optimization.
- Both original 2026-10-13 sessions were incomplete as capture campaigns and contain original evidence loss; structural per-record integrity PASS is **not** source completeness or an EARLY result.

## Remaining required engineering (bounded quote and native lifecycle semantics)

1. Teach the EXISTING `ops/live_recording/reader.py` `CampaignVerifier` and its `ops/recording_workflow/whole_run.py` pipeline to consume bounded time/record partitions while continuing the original quote-book snapshots, dependent event hashes, source clocks, official contract open/target, native decisions, HOLD/WATCH/PROTECT/EXIT states and settlement linkages **without** one giant `raw`/dependency SQLite database.
2. Check per-boundary carry state with original event identities and support delayed quote acceptance or outcome publication that crosses 15-minute windows. An unclocked event cannot be assigned official contract time without independent evidence.
3. Keep whole-session and end-to-end completeness criteria unchanged; a sequence/capture gap in one slice must make the containing campaign NO-GO, not silently qualify other slices as complete.
4. Make the native V81 quote-record producer viable in its own constrained volume using controlled batching and/or independently authorized lossless streaming; separately identify MAIN's original oversized event. Review real worst bursts and producer sizes.
5. Only once the end-to-end bounded reader and native writer have passed can a **separately reviewed production recorder activation** start authentic 24h capture. Signal-only, NO ORDERS; no changes to source freshness limits or ladder thresholds.

## Safety

No Codespaces computation, no MAIN/V81/BRTI/cockpit changes or restarts, no production volumes resized, no model/strategy tuning and no trading orders. Isolated Railway research service only and research branch changes.
