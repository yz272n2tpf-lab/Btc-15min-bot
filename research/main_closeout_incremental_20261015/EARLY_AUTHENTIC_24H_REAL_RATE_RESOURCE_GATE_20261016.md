# BTC15 EARLY 24-hour acceptance — real native producer and reader capacity gate (2026-10-16)

**Decision: NO-GO for starting the authentic 24-hour campaign using the current preflight/day budgets.** Do not rerun the successful 600,000 synthetic capacity test. No strategy change, new validator, or production change.

## Grounded evidence

1. Existing synthetic Railway writer/indexer/reader: PASS 600,000 input records / 600,004 total, all 66 partitions, zero reported issue counts. Preserved on isolated 100,000 MB volume.
2. Authenticated read-only SSH transfer of two original capture identity files from MAIN and V81 into isolated Railway, exact SHA-256 validated. Later copied preserved, incomplete Oct-13 MAIN/V81 gzip archives into isolated research-only paths. Production volumes/files unchanged.
3. Real V81 preserved sample: 26,484 logical JSONL envelopes, 24,097,297 decoded bytes, 16,100,237 original gzip bytes over **15.13449 seconds** of preflight before loss/stop. Existing recorder batching produced **2,453,132 gzip bytes** (84.8% less) while verifying byte-for-byte identical decoded stream SHA-256 `391c4810cc3f4c7828aa1132781084a6b6f22ecef11ee01810bef60622d8b382`. Source copy 2 files, 104 complete gzip batch members, sample-only writer rate 18,526 envelopes/s.
4. Real MAIN preserved sample: 2,942 envelopes, 8,576,026 decoded bytes, 3,552,791 original gzip bytes over **40.50538 seconds**. Batching produced **2,043,489 gzip bytes** (42.5% less), decoded SHA-256 `27f425257292ef1a5329b814eaf784adb708a9c7af275c15881ffe1da2be73d4`; writer 5,349 envelopes/s. MAIN still has one unidentified `OVERSIZE` drop; do not falsely credit as a complete preflight.
5. Information role: 4,492 envelopes, 101,587,622 decoded bytes, 8,560,065 compressed bytes over 1,200.515 s, fully SEALED, no gaps.
6. Existing native `ops.recording_workflow.evidence.index_run(...,profile='day')` executed read-only against copied original samples on isolated Railway:
   - MAIN: 2,942 indexed rows, 1,454,080-byte index, **494.249 bytes/row**.
   - V81: 26,484 indexed rows, 12,648,448-byte index, **477.588 bytes/row**.
   - Each source index's SHA-256 verified. Samples retain original evidence gaps; **neither is a qualified continuous cohort**.
   - Trial deployment `e0946b1e-5c71-4df6-aa83-989d7c903da7` completed successfully and saved `INDEX_MEASUREMENTS.json` under the isolated 100GB volume.
7. V81 quote sequence logs over a separate ~16.6-minute window show high activity (median observed sequence rate ~1,021 seq/s), though **sequence deltas must not be equated with exact quote-capture counts**.

## Conditional, NOT guaranteed 24-hour extrapolation

Time window 86,940 seconds. Source observation rate assumed equal to each captured incomplete sample's average. Margined projection = ×1.5.

| Role | Projected records (raw) | Projected records (1.5×) | Projected batched compressed (raw) | 1.5× compressed | 1.5× decoded bytes | Existing role day caps |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| MAIN | ~6.31 million | ~9.47 million | ~4.08 GiB | ~6.13 GiB | ~25.7 GiB | 3 million records / 1 GiB compressed / 6 GiB decoded |
| V81 | ~152.14 million | ~228.21 million | ~13.12 GiB | ~19.69 GiB | ~193.4 GiB | 1.5 million records / 0.5 GiB compressed / 3 GiB decoded |
| INFORMATION | ~0.325 million | ~0.488 million | ~0.577 GiB (existing nonbatched) | ~0.866 GiB | ~10.3 GiB | 1.5 million records / 0.5 GiB compressed / 3 GiB decoded |

**These sample intervals are incomplete, rate-varying, and V81 dropped 1,470 observations. Treat the projections as a reason to size carefully, never proof that live capture will actually sustain that exact rate.**

- V81 production volume 5,000 MB, recently using ~3.19 GB, **cannot** retain an isolated 24h archive of ~14–21 GB in-place. The 100GB separated Railway reader volume does NOT increase V81 source capacity.
- MAIN production volume 20,000 MB, recently using ~9.16 GB, so its available headroom is finite too. Do not resize/restart without specific authorization.
- Existing full-day reader caps: **6 million source records in aggregate**, **12 GiB decoded total**, **3 GiB index** and **48 GiB working DB**. Even the conditional **unmargined V81** alone would exceed the record and decoded quotas.
- If the observed V81 index bytes/record were sustained, an unbounded monolithic V81 day index would project ~72.7 **billion** bytes (~67.7 GiB) before any working verifier DB. With 1.5× record margin: ~109 **billion** bytes (~101.5 GiB). The existing isolated 100GB volume does NOT prove sufficient for monolithic real-data indexing.
- The October13 information role 20-minute result does not prove a full day; previous 600k synthetic fixture did not contain this native quote volume.

## Scoped engineering route — fix EXISTING recorder and reader, not build another validator

1. Preserve source/original quote evidence losslessly; do not resample timestamps, invent prices or ignore original quote/proof gaps. Existing off-path batching has passed 4/4 focused regression tests and byte-for-byte comparisons on original MAIN/V81 samples.
2. Keep MAIN oversized-event gate strict until its rejected event kind/charge are safely identified in a separately authorized short native preflight.
3. Replace the full-day **monolithic, per-quote-record index/verification working set** with bounded, contract-time-window streaming in the existing index/reader, carrying quote-book state, original source timestamps, official contract binding, native journal identities, and predecessor hash continuity across windows. Never certify a window unless the whole source segment chain / required dependencies are accounted for. This is substantial reader engineering **not yet implemented**.
4. Use the existing authenticated, checksum-proven Railway SSH transfer and isolated processing volume. A larger V81 production volume or an independently approved lossless streaming/archive policy will still be needed to retain a real 24h raw native quote archive. Deletion of production evidence is forbidden without explicit separate approval.
5. Only after a verified no-loss preflight, updated rate projections, and valid full-seal/replay acceptance: authorize controlled MAIN/V81 producer changes and run the real 24-hour approximately 96-contract EARLY evaluation with existing scoring.

## Status and safety

- Current product: **NO-GO for authentic 24h start.**
- Existing 600k synthetic capacity qualification: **PASS**.
- Existing research batching regressions: **4/4 PASS**, but authentic 24h data capture remains unproved.
- Existing real V81 quote stream: **previous recorder lost events**; original missing messages cannot be inferred.
- **No production deploy/restart, changes to credentials or data, strategy thresholds, signal-only mode or orders.**
