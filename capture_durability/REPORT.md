# BTC15 sustained quote-capture durability — FAIL

Candidate: `e050501a93d175a2863f0712c119dbf94c210f11`, based on qualified capture `90a24b1189a6bae8403e46149313716d19f56229`. Payload SHA-256: `bc4fb4aa3344723b021034e314aef7d494a9e8bc07c8c2a38fa0972a3a2b272a` (99,191 bytes). **Not deployed.**

## Demonstrated loss boundary and limit of diagnosis

The retained live quote sender reports show 16,777,215-byte high-water marks against 16,777,216-byte FIFO limits on both MAIN and V8.1. Their rejected/producer-dropped totals equal the archive's missing sequences: MAIN 15,657; V8.1 761. Both senders were still active and later drained; the writer had zero invalid packets and was below quota during these gaps. The observed losses occurred at sender byte-queue admission under downstream backpressure, not unreported datagram loss after successful delivery or short-lived producer retirement. The earlier independent population/report-file reads mixed census times, explaining MAIN's 4,692/4,698 mismatch.

The candidate replaces the sender's fixed 1 ms EAGAIN sleep with connected-socket writability waiting, off the strategy thread. An isolated 100,000-datagram boundary benchmark improved from 55,404 to 499,790 packets/s. **This is not proof that the fixed sleep was the sole underlying live bottleneck.** The subsequent complete writer/churn stress still overflowed. The precise remaining contribution of receiver validation, compression/storage and concurrent accounting throughput has not been isolated. Investigation stopped at the requested failed qualification gate.

The prior window eventually reached its 512 MiB storage quota on both sides. That later shutdown is separately explicit in retained final manifests; it does not explain the earlier, below-quota loss counts above.

## Passive-only changes

Only `capture2/runtime.py` and `capture2/writer.py` changed within the eleven-module deployment payload:

- Readiness-driven off-thread retries; unchanged 16 MiB / 16,384-record sender limits and 16 active-sender / 16,384 created-stream limits per process.
- Persistent rejection reason/sequence and backpressure-wait counters.
- Atomic per-process census containing active reports and immutable retired-report references. Receiver streams ahead of that census explicitly prevent complete accounting.
- Active drops now fail accounting closed; archive heads advance only after writes; uncommitted valid packets are explicit.
- Bounded five-second transport-only shutdown flush grace.

All nine other payload modules, strategy hooks outside the two transport/accounting classes, and composition/source pins remain unchanged. No order paths or ladder changes were introduced.

## Qualification

Local focused regressions: **2/2 passed**. Hosted focused regressions: **2/2 passed**. Hosted workflow run **36719920775**, job **109902111805**, exact candidate above.

The sustained test targeted 1,500,000 quote packets per side at 9,000 packets/s, 2,250-record bursts, 5,000 short-lived producer streams, two 250 ms receiver suspensions and concurrent accounting reads. Retained live maxima were MAIN 2,156 packets/100 ms and 8,757 packets/s; V8.1 683/100 ms and 5,249/s. These are transport fixtures, never fresh signal/event proof.

**MAIN failed after 70.615 seconds at offer 636,286**, before the required volume:

| Counter at failure | Value |
|---|---:|
| Offered / accepted | 636,286 / 636,285 |
| Delivered to socket | 623,537 |
| Explicit FIFO rejection | 1 |
| Pending records / bytes | 12,748 / 16,776,368 |
| Backpressure retries | 4,025 |
| Writability wait | 27.088 seconds |
| Created / active / retired | 2,588 / 4 / 2,584 |
| Unique individual census entries | 2,588 |
| Retired flushed / incomplete | 2,584 / 0 |
| Active-sender high-water / bound | 7 / 16 |
| Admission rejections | 0 |

Aggregate and individual census population reconciled at the failure cut. The in-flight quote stream did not reach orderly terminal qualification. Full archive continuity and the 1.5M target were not qualified. **V8.1 sustained test skipped after MAIN failed.** No further repair or live capture qualification was attempted. A superseded test-only commit (`18eea6e...`, identical payload) also overflowed at 530,940 offers / 58.899 seconds; it is not a separate qualified candidate.

## Preservation and restoration

Qualified strategy sources remain MAIN `abe212b513827c8cec28a2f64e0161e79296bd82` and V8.1 `b05723ec622f901a05402ecf27f4d33505753ef1`. Original production launch commands were restored using fresh configuration deployments: MAIN `3c066b20-a80b-47d2-82a3-f3edf6e8b0b2`; V8.1 `03790550-1e34-421d-b9f0-8261ca8d7bb5`. Both are SUCCESS at the exact strategy commits; both `/health` endpoints return 200 and both capture manifests return 404. Configured start commands match the originals byte-for-byte. The existing activation marker was changed solely to trigger restoration; no strategy variable changed. Evidence is in `results/restoration.json` and `results/restoration-http.json`.

The complete pre-existing V8.1 archive was retrieved before replacing its container: 536,866,178 bytes; SHA-256 `aba02b2e114a8b492e32521626d411922d88cded0b7183b5df75043ba72677ef`; every retrieved tail chunk hash and gzip integrity verified. This was evidence preservation, not a new capture window. The MAIN archive remains on its persistent volume. Final manifests and all final individual transport reports were retained for both prior runs.

**SUSTAINED QUOTE-CAPTURE DURABILITY GATE: FAIL**

**READY TO RESUME EVENT-LEVEL GROUND ZERO: NO**
