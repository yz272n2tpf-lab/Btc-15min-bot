# Nextgen body dedup batched V2 verification

**NEXTGEN BODY DEDUP BATCHED V2 FAILED — DO NOT DEPLOY**

The original realistic cold-start bottleneck is fixed and the exact 305-second
fixture passes. The history-growth gate remains blocked: full-history verification
still grows with retained evidence and exceeds the unchanged 5-second telemetry
interval in the larger tested histories. No readiness or deployment claim follows
from the cold-start improvement or passing integrity suites.

## Candidate and protected refs

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Candidate branch: `integrity-sentinel-nextgen-body-dedup-batched-v2`.
- Direct base: `7c98f5e54288904534bca6a6cae22eff1823f880`; only this new branch is changed.
- Protected Sentinel: `b75c0cee90a114590db612f87e33cc10bf959ccb`.
- Failed V1 dedup: `7c98f5e54288904534bca6a6cae22eff1823f880`.
- Production main: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.
- The final candidate SHA is the commit containing this report; supplied in the
  completion response. Protected remote refs were checked before work and are
  checked again after candidate publication.
- All changed/new tracked files are under `integrity_sentinel/`. `integrity/`
  and all tracked files outside Sentinel remain unchanged.

The [design](NEXTGEN_BODY_DEDUP_BATCHED_V2_DESIGN.md) explains admission bounds,
durability ordering, observation-first commitments and recovery policy. The
[complete results](NEXTGEN_BODY_DEDUP_BATCHED_V2_RESULTS.json) include raw output
for every suite, all compiled source SHA-256 values and every measurement sample.

## What changed

`append_batch` keeps individual rows, sequences and hashes, while taking one ledger
lock, verifying the existing ledger/anchor/durability/body/provenance gate once,
and using one seven-fsync transaction for the entire observation's new events.
It writes bounded 1 MiB chunks with the unchanged storage guard before each.
Admission limits are 8,192 rows and 32 MiB encoded bytes; oversized batches fail
closed and do not silently drop or split events.

The runtime filters previously seen IDs before the batch and marks them seen only
after durable completion. New observations commit the count and ordered-ID digest
of their expected derived rows. This closes the pre-intent crash/disk failure gap:
an observation with missing derived events remains unhealthy across restart even
if no batch marker could be created. Each event is still a separate full record,
with exact contract, record SHA, observation ID/hash and Nextgen body SHA linkage.

The source text of single-record `append()` is unchanged. The original immutable
body store and its verifier, watchdogs, redirects, storage guard thresholds,
control attestation, exact-ID extraction and source adapters are unchanged.
Telemetry persistence and 5-second/10-second schedules are unchanged. The new
membership verifier adds checks for declared batches; it never bypasses the V1
body or hash-chain gates. No cache, truncation, adoption or automatic repair exists.

## Exact realistic 305-second fixture

The exact V1 fixture generator and transport are unchanged: `synthetic_audit(192)`
is **1,634,996 bytes**, with **3,072 initial membership events**, all seven synthetic
sources and a new body revision every six membership observations. Only the
source-level revision changes; event records do not change after initial loading.
The scheduling policy matches the unchanged service loop. No source provider or
Railway endpoint was contacted. No additional test workload was launched alongside
the final timed run; the shared executor is not a dedicated production benchmark.

| Required cadence/health check | Final candidate result |
| --- | ---: |
| Sustained scheduled duration | 305.010 seconds |
| Telemetry | 61/61 |
| Early observations | 31/31 |
| Final observations | 31/31 |
| Combined observations | 31/31 |
| Nextgen observations | 31/31 |
| Healthy cycles | 61/61 |
| Cycles longer than 5 seconds | 0 |
| Fresh-process full verification | PASS; all files unchanged |

**Initial large cycle: 0.456 seconds wall,
0.455 seconds CPU.** The derived batch itself takes
**0.163 seconds wall / 0.163
seconds CPU**, writes 4,496,970 application bytes,
and performs exactly seven fsyncs. These are reported separately from percentiles.

Cycle wall p50/p95/max: **0.456 / 1.331 /
1.378 seconds**. Cycle CPU p50/p95/max:
**0.455 / 1.331 / 1.376
seconds**. Maximum scheduling lateness: 0.460 ms.
No missing scheduled observations or false stale-source health occurred in this run.

Fresh-process reopen verification: 332.373 ms wall,
332.372 ms CPU (533.520
ms including process startup and checks). It verified telemetry, the membership
chain, anchors, durability markers, all batch obligations and all 6
immutable objects, with all persisted file hashes unchanged.

## History growth — remaining failure

Before each growth measurement, the harness records complete earlier synthetic
observations, immutable bodies and distinct membership records through the normal
runtime. It then measures a new 3,072-event batch plus subsequent cycles. The rows
are not pre-written shortcuts or dummy padding. Each size runs in its own process.

The first table row is the 61-cycle sustained empty-history run; the next three
pre-populated cases measure six unpaced cycles (three membership observations).
The final row repeats the 24,576-event history with 35 seconds of scheduled work. The unpaced
cases measure cycle budgets, not 305-second scheduled counts. Each reported
initial cycle includes the new batch after the indicated pre-existing event count;
subsequent cycles verify that additional history too. All history runs passed
integrity/fresh-process reopen and remained healthy, but the larger histories
exceeded the 5-second cadence budget. These misses block the overall verdict.

The additional scheduled growth probe directly confirms the effect: telemetry
**5/7**, membership observations
**3/4 for each source**,
with **5/5 healthy completed cycles**. Its elapsed
time is 37.166 seconds; an in-flight cycle is allowed to finish.
This uses unchanged 5/10-second scheduling and the same exact fixture.

| Pre-existing events | New batch wall / CPU s | Initial full cycle s | Cycle wall p50 / p95 / max s | Reopen verification s | 5s cycle budget |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 0.163 / 0.163 | 0.456 | 0.456 / 1.331 / 1.378 | 0.332 | PASS |
| 3,072 | 0.302 / 0.301 | 1.618 | 1.122 / 2.300 / 2.300 | 0.616 | PASS |
| 12,288 | 0.762 / 0.762 | 5.473 | 3.510 / 5.525 / 5.525 | 1.524 | FAIL |
| 24,576 | 1.337 / 1.337 | 10.010 | 6.105 / 10.010 / 10.010 | 2.633 | FAIL |
| 24,576 (35s scheduled) | 1.382 / 1.382 | 10.225 | 9.562 / 10.225 / 10.225 | 2.683 | FAIL |

The batch transaction scales as O(H + U + B), for ledger history H, retained body
bytes U and new batch size B. It removes repeated per-event verification and fsync
but does not bound H or U. Ordinary observation appends and health checks still
verify retained history. There is no evidence of constant-cost throughput as
history grows. Addressing that limit requires a separately scoped design; no
freshness relaxation, slower polling, removed fsync, dropped event, history deletion
or verification shortcut was used here.

## Resource measurements

| Pre-existing events | Measured application bytes | Total retained bytes | Measured retained growth | Peak RSS MiB | Files / subdirs / bodies | Inodes incl. root |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 15,145,579 | 14,864,068 | 14,858,780 | 71.43 | 12 / 1 / 6 | 14 |
| 3,072 | 6,215,303 | 12,332,788 | 6,186,495 | 75.39 | 8 / 1 / 2 | 10 |
| 12,288 | 6,218,513 | 30,773,363 | 6,189,583 | 79.50 | 11 / 1 / 5 | 13 |
| 24,576 | 6,218,511 | 55,365,912 | 6,189,581 | 84.77 | 15 / 1 / 9 | 17 |
| 24,576 (35s scheduled) | 6,209,689 | 55,360,318 | 6,183,994 | 83.91 | 15 / 1 / 9 | 17 |

The sustained run projects **4.2212 GB/day application
writes** and **4.1413 GB/day retained growth** when
extrapolating its finite window including the initial event batch. Excluding the
initial cycle gives **2.5903 / 2.5098
GB/day** respectively. All are decimal GB. The assumed one-new-body-per-six-polls
pattern produces about 1,440 new immutable object files/day at unchanged 10-second
polling. Every body different would provide zero cross-response reuse; this run
does not establish the real source's change rate.

Application bytes count successful `os.write` results during measured cycles,
including all seven source ledgers, events, markers and anchors; they exclude
runtime initialization/history preparation and filesystem journal/device write
amplification. Retained bytes and allocated blocks are measured separately. RSS
is process high-water and includes history preparation. The JSON contains cycle
CPU arrays, allocated bytes, per-history projections and all reopen metrics.
Unpaced growth-run projections are finite-window arithmetic, not successful
sustained-cadence forecasts. Other source fixtures are deliberately small; these
numbers are not a production volume recommendation or total real-feed forecast.

## Required suites and fault coverage

| Required suite | Result |
| --- | ---: |
| Compile every Sentinel Python file | 25/25 PASS |
| Every existing Sentinel unit/regression test | 317/317 PASS |
| All `integrity/` tests | 62/62 PASS |
| Integrity adversarial V1 | 7/7 PASS |
| Sentinel adversarial V1 | 28/28 PASS |
| Durability V2 | 9/9 PASS |
| Watchdog V3 | 216/216 PASS |
| Body-dedup V1 | 20/20 PASS |
| New independent batch-throughput adversarial suite | 23/23 PASS |

The new suite uses its own fixture/serializer/hash oracle, not production hash
helpers or existing unit-test fixtures. It includes real repeated individual
appends for all 3,072 rows and checks exact ledger and anchor byte equivalence.
This is an independent test implementation, not a separate human/code-review
certification.

Coverage includes 3,072 rows; zero/one event; duplicate filtering before batch;
per-row sequence/hash continuity; exact record/event/contract/observation/body
provenance; bounded admission; beginning/middle/end short writes; a valid-row
partial batch followed by process death; death after ledger fsync and before
acknowledgement cleanup; all seven fsync failure boundaries; pending/committed
anchor short writes and replacement failures; cleanup failure; ENOSPC; low disk
before/during batch; concurrent batch/single writers in separate processes;
committed observation with pre-intent failure or failed large batch; corrupt body
references; wrong order/count/parent/record/digest; extra rows; missing exact ID;
and successful/failed large-batch fresh-process reopens. Failed opens and runtime
cycles make zero fixture fetches and do not change any retained file hash.

Generic core pre-intent admission failure leaves an unchanged acknowledged prefix;
actual membership pre-intent failure is persistently blocked by the previously
committed observation obligation. No partial batch is silently adopted, truncated,
retried or repaired. `orders=false` and `certifiable_evidence=false` remain intact.

## Reproduction

Run from the candidate checkout with Python 3.12 and Requests 2.34.2. Validation
used an interpreter audit hook rejecting non-loopback DNS/connections; fixtures
replace HTTP transport in memory. Existing endpoint tests use loopback only.

```bash
python -B -m unittest discover -s integrity_sentinel -p 'test*.py' -v
python -B -m unittest discover -s integrity -p 'test*.py' -v
python -B -m integrity.adversarial_hardening_v1
python -B -m integrity_sentinel.adversarial_hardening_v1
python -B -m integrity_sentinel.adversarial_remediation_v2
python -B -m integrity_sentinel.adversarial_watchdog_v3
python -B -m integrity_sentinel.adversarial_body_dedup_v1
python -B -m integrity_sentinel.adversarial_batch_throughput_v2
python -B -m integrity_sentinel.measure_batch_throughput_v2 --seconds 305
python -B -m integrity_sentinel.measure_batch_throughput_v2 --seconds 0 --history-batches 1 --cycles 6
python -B -m integrity_sentinel.measure_batch_throughput_v2 --seconds 0 --history-batches 4 --cycles 6
python -B -m integrity_sentinel.measure_batch_throughput_v2 --seconds 0 --history-batches 8 --cycles 6
python -B -m integrity_sentinel.measure_batch_throughput_v2 --seconds 35 --history-batches 8
```

Measurement exit code 1 marks a failed cycle budget, even when integrity is valid.
Compilation used `py_compile.compile(..., doraise=True)` with all output outside
the checkout. Every compiled source hash was matched again when building this report.

## Safety confirmation

Only the new V2 candidate branch and Sentinel files were changed. No verified or
failed V1 branch, production main, `integrity/`, real evidence, cutoff, provider
polling, certification window, strategy, orders or trading was modified. No Railway
API/action, deployment, redeployment, restart, domain, volume, configuration or
variable action occurred. No merge or outbound issue/PR/comment/message was sent.
All fault injection affected disposable synthetic test files only.

**NEXTGEN BODY DEDUP BATCHED V2 FAILED — DO NOT DEPLOY**
