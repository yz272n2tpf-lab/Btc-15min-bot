# BTC15 decisive capture writer qualification — FAIL

Candidate: **d61c021cb405b08603864d077f03474473d2a5f3**, parent **e050501a93d175a2863f0712c119dbf94c210f11**. Payload SHA-256: `cc8966338df3bceb608017fec3fd9db4a3e6e6beec98272eb9751fa85065cf2e` (113,876 bytes). **Never deployed.**

## Implemented architecture

Native hooks now perform a bounded causal value snapshot and nonblocking handoff. Dedicated capture workers perform canonical JSON encoding, hashes/HMAC, raw-quote base64 encoding, protected-generation hash/link materialization and compression. Workers send authenticated batches of up to 64 original event envelopes. A dedicated writer authenticates batch metadata and appends compressed members in sequential groups. The existing gzip/JSONL archive and original per-event authentication remain readable. A separate reader/accounting process prevents census/HTTP work from holding the writer's interpreter lock, and immutable retired reports are cached.

This removes per-event JSON decode/re-serialization/compression from the receiver, redundant event serialization, and repeated retired-report parsing from the writer's execution path. It does not qualify end-to-end durability by itself.

FIFO limit remains **16 MiB**; the new limit conservatively charges retained snapshot heap, rather than serialized packet bytes. The retry/flush allowance remains five seconds. No FIFO enlargement or longer retry window was used.

## Focused and preservation checks

- Local: 4/4 pipeline regressions and 4/4 strategy-preservation checks passed.
- Hosted exact candidate: the same 8/8 checks passed.
- Immutable snapshots, off-producer serialization, preserved protected-generation hash/publication linkage, original receive values, authenticated frame tamper/binding rejection, explicit overflow and deadline flushing were exercised.
- Native/protected/V8.1 original strategy statements and quote source operations remained unchanged. Nine original payload modules remain byte-identical. Only capture runtime/writer changed, plus the new capture wire module.
- Strategy source commits remain MAIN `abe212b513827c8cec28a2f64e0161e79296bd82`, V8.1 `b05723ec622f901a05402ecf27f4d33505753ef1`.

## Decisive hosted result

Workflow **36723160219**, job **109913176344**. Artifact **11102201473**, SHA-256 `06bcab72d7a2d69949c0ee3579aa868b837c2f2fe066044311229c89e72edfb1`.

The test targeted 1.5 million quote packets per side at 12,000 packets/s, 2,250-record bursts, 5,000 short-lived streams, concurrent accounting reads and two 250 ms receiver pauses. MAIN failed during the first imposed writer pause/recovery, after **5.308307 seconds and 64,939 offers**. V8.1 was skipped immediately; no further repair, test rerun or deployment followed.

| Measurement | Result |
|---|---:|
| Offered quote rate | 12,233.47 packets/s |
| Writer checkpoint rate before pause | 12,146.89 records/s, including churn |
| Writer checkpoint interval | 53,968 committed records / 4.442948 s |
| Offered / accepted quote packets | 64,939 / 64,938 |
| Delivered to socket | 62,350 |
| Explicit rejected packet | 1, sequence 64,939, CAPTURE_BUFFER_FULL |
| Maximum FIFO occupancy | 2,844 snapshots / 16,775,334 charged bytes |
| Pending at failure snapshot | 2,588 / 15,265,318 charged bytes |
| Backpressure retries / measured wait | 2 / 0.098832 seconds |
| Created / active / retired streams | 209 / 2 / 207 |
| Retired flushed / incomplete | 207 / 0 |
| Active-sender high-water / bound | 4 / 16 |
| Admission rejections | 0 |
| Writer's latest committed checkpoint | 60,748 records; zero invalid frames or observed sequence gaps |
| Writer CPU used at that checkpoint | 0.169995 seconds |
| Writer maximum pending persistence batch | 1,614 records / 243,196 compressed bytes |

The writer demonstrated approximately the offered rate before the pause, but only over a short interval. CPU-normalized figures are not treated as a sustained capacity qualification. The sample does not establish the required long-run stable backlog.

**Exact remaining failure boundary:** the bounded snapshot handoff exhausted its byte budget while downstream reception was deliberately paused. Snapshots charge roughly 5.9 kB each; the 16 MiB queue reached 2,844 snapshots before rejecting the next offer. This is explicit burst/pause absorption failure, not an unexplained kernel drop. The pending counter had already fallen below its high-water mark when the failure report was taken. No claim is made that receiver throughput remains the same bottleneck as before.

Nine interim aggregate-versus-individual count checks produced no mismatch. The failure population satisfies 209 = 2 + 207, and every retired stream was flushed. Final paginated unique-census reconciliation and full archive validation were not reached. The active quote stream's final flush is **unqualified**; pending packets must not be presumed persisted.

Bounds remain 16 active senders and 16,384 created streams per producing process, 16 MiB charged FIFO per sender, bounded serialization work, 64 records / 262,144 bytes per frame, and a 2 MiB / 4,096-record persistence batch. Full sustained resource/RSS qualification was not reached.

## Production and stop condition

No Railway calls, configuration changes, capture installation or live qualification occurred in this mission. The original launchers restored in the preceding mission remain the production configuration; no new restoration was necessary. No strategy tuning, signal-event wait, orders, clock research or historical strategy replay occurred.

**SUSTAINED CAPTURE DURABILITY: FAIL**

**READY TO RESUME EVENT-LEVEL GROUND ZERO: NO**
