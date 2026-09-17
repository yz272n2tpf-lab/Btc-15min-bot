# Nextgen body dedup V1 verification

**NEXTGEN BODY DEDUP V1 FAILED — DO NOT DEPLOY**

The immutable storage and adversarial correctness checks pass. The bounded task's cadence requirement is not cleared: a realistic-size initial Nextgen snapshot causes a long membership-event append cycle and stale-source health failures. Storage reduction alone does not solve that throughput limit. The failed candidate is preserved for review on its isolated branch; no deployment or certification is authorized.

## Exact scope

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- New branch: `integrity-sentinel-nextgen-body-dedup-v1`, based directly on `b75c0cee90a114590db612f87e33cc10bf959ccb`.
- Protected verified branch: `integrity-sentinel-recorder-v1` remains `b75c0cee90a114590db612f87e33cc10bf959ccb`.
- Production main remains `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.
- All changes are under `integrity_sentinel/`; `integrity/` and every tracked file outside that directory are unchanged from the base.
- Runtime SHA-256: `5f1e76da16d303e30531a23112fb99ad40dd24a5e34dca7e9c2b637c75b08f00`.
- Body-store SHA-256: `91b21e8a5ee2c60d66b453d5cc942c007ee16f4e87e03269175ec58684ed59c1`.
- Final candidate Git SHA is the commit containing this report and is supplied in the completion response.

See [design](NEXTGEN_BODY_DEDUP_V1_DESIGN.md) for format, durability ordering, failure policy and replay API; [complete results](NEXTGEN_BODY_DEDUP_V1_RESULTS.json) contains every suite output and raw measurement.

## Functional and adversarial results

| Required check | Result |
| --- | --- |
| Compile every Sentinel Python file | 22/22 PASS |
| Every Sentinel unit/regression test | 317/317 PASS (296 unchanged + 21 new) |
| All hardened integrity tests | 62/62 PASS |
| `integrity.adversarial_hardening_v1` | 7/7 PASS |
| Sentinel adversarial V1 | 28/28 PASS |
| Sentinel adversarial V2 | 9/9 PASS |
| Sentinel adversarial V3 | 216/216 PASS |
| Separate independent storage-dedup suite | 20/20 PASS; includes 18 body-publication fsync boundaries |
| Small 305-second sustained run | PASS at this size only |
| Realistic-size 305-second sustained run | **FAIL: cadence/freshness** |

New tests cover identical bodies with distinct envelopes; a one-byte change; a changed membership record; HTTP 503 with the exact same last-good bytes; malformed, wrong-type and interrupted bodies; missing, modified, truncated and symlinked objects; valid restart/reopen; missing catalog, unknown object, forged valid-chain reference and membership linkage; short write/fsync failures for objects and observation references; every body-publication fsync boundary; concurrent store instances and repeated observations; exact-ID/full-record provenance; source scoping; original cadence; and low-disk guards. The separate probe imports no unit-test fixture or body-store verification implementation for its body/hash/provenance assertions. Reopen checks use fresh spawned processes with healthy synthetic controls and require unchanged evidence bytes and zero fetches after damage. The fsync-boundary subprobe explicitly targets the store API.

Original marker/anchor implementation, watchdogs, redirect protections, disk guards, control checks, health cutoffs, strategy extraction, orders=false and certifiable_evidence=false remain unchanged. Damaged referenced content fails closed through the runtime's membership ledger gate. No old envelope or existing evidence is migrated or rewritten. No automatic body removal or GC exists.

## Size and measurement basis

Python 3.12, Requests 2.34.2; Linux/POSIX local container filesystem. All data are synthetic. Source transports are in memory, with an interpreter audit hook blocking external DNS/connections even in child processes. Existing HTTP endpoint tests use loopback only. No producer is imported or run.

Pinned Nextgen source `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1` provides the family/lane/record topology and per-record field shapes. The saved September 17 final environment audit records a historical successful Nextgen body of **1,621,486 bytes**. This is not a new live observation. The larger fixture is **1,634,996 bytes** (about 0.83% larger), with 3,072 synthetic family/lane membership events. The smaller fixture is **136,884 bytes**, with 256 events. Exact contracts and values are fabricated. Other source fixtures are deliberately small; real Combined size remains unknown.

Application byte counts instrument successful `os.write` return values and include raw bodies, all seven synthetic feeds, initial events, anchors and transient markers. Retained bytes, filesystem allocated blocks and inode counts are separately in the JSON. Filesystem journal/device write amplification is excluded. RSS is process peak resident memory, not a measured live heap. Timing comes from wall/process clocks. Large runs overlap in a shared executor, so they do not establish dedicated-hardware performance; their severe misses prevent a pass claim.

## Smaller controlled storage comparison

Each row uses 24 membership observations per source and 48 telemetry cycles, preserving the 2:1 telemetry/membership ratio while running without sleeps. Base and candidate are separate processes using the same fixture/harness. GB/day is decimal, extrapolated at 8,640 membership observations/day and includes the measured cold-start event cost. It is a finite-window projection, not a long-run capacity claim.

| Body pattern | Base application bytes | Dedup application bytes | Projected application GB/day, base → candidate | Cross-observation result |
| --- | ---: | ---: | ---: | --- |
| All bodies identical | 8,821,279 | 1,321,600 | 3.1757 → 0.4758 | 85.02% |
| One body per 6 observations | 8,821,282 | 1,735,592 | 3.1757 → 0.6248 | 80.32% |
| Every body different | 8,821,276 | 4,495,622 | 3.1757 → 1.6184 | No reuse savings claimed |

**Every-response-different has zero body reuse. No dedup savings are claimed for it.** Its raw measured counts differ because the candidate stores a single raw representation instead of both base64 and parsed JSON. That format effect must not be presented as evidence of repeated-response deduplication. Errors/partial/parse failures remain inline and do not benefit from the successful-body path.

| Pattern / implementation | Mean CPU ms/cycle | Mean wall ms/cycle | Peak RSS MB | Files / directories / objects | Reopen verification ms |
| --- | ---: | ---: | ---: | --- | ---: |
| identical / base | 252.02 | 252.77 | 57.43 | 4 / 0 / 0 | 262.49 |
| identical / dedup | 96.84 | 97.70 | 38.50 | 7 / 1 / 1 | 47.49 |
| change6 / base | 242.07 | 242.95 | 57.02 | 4 / 0 / 0 | 316.47 |
| change6 / dedup | 95.63 | 96.11 | 38.61 | 10 / 1 / 4 | 51.35 |
| unique / base | 245.93 | 246.41 | 56.89 | 4 / 0 / 0 | 258.09 |
| unique / dedup | 101.51 | 101.97 | 41.89 | 30 / 1 / 24 | 57.49 |

The base uses four persistent ledger/anchor files. With dedup, there are six fixed persistent files plus one file per unique body and one extra directory. At steady 10-second observations: an identical body needs one object total; a new body every six observations means about 1,440 new objects/day; every response different means 8,640 new objects/day. All are retained permanently. Catalog/ledger byte growth continues in every case. The initial large-body event population is additional. There is no inode or history-growth cap.

## Sustained tests and the blocking finding

The smaller candidate run lasted **305.011 seconds**: **61/61** telemetry cycles, **31/31** observations for each of Early/Final/Combined/Nextgen, **61/61** healthy cycles, six body objects, maximum cycle **1141.97 ms**, peak RSS **40.43 MB**, successful reopen. This cannot be generalized to the historical 1.62 MB body size.

Both larger runs use 305 seconds of scheduled work at the unchanged 5-second telemetry and 10-second membership settings, with producer-shaped bodies changing every six membership observations. Their elapsed run times are base **305.530s**, candidate **305.410s**. An in-progress cycle is allowed to finish; the timer does not interrupt an append.

| Implementation | Initial cycle seconds | Telemetry cycles / expected | Membership observations per source / expected | Healthy cycles / actual | Cycles exceeding 5s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact pinned base | 205.521 | 21 / 61 | 11 / 31 | 20 / 21 | 1 |
| Dedup candidate | 136.200 | 35 / 61 | 18 / 31 | 34 / 35 | 1 |

| Implementation | Application bytes | Retained bytes | Window-extrapolated application GB/day | Mean CPU / wall ms per cycle | Peak RSS MB | Files / directories / objects | Reopen ms |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Exact pinned base | 48,494,679 | 46,363,921 | 38.0904 | 10986.01 / 10999.63 | 210.22 | 4 / 0 / 0 | 1525.45 |
| Dedup candidate | 11,908,877 | 9,714,185 | 5.7163 | 4382.67 / 4390.80 | 105.98 | 9 / 1 / 3 | 296.03 |

The large runs miss scheduled observations; their byte/day extrapolations must not be mistaken for successful-cadence production estimates. The candidate's first long append cycle causes all seven `source_unhealthy` freshness reasons despite healthy fixture responses. Subsequent short cycles can restore current health, but cannot recreate polls skipped during that initial append work. Both implementations verify successfully on reopen, so this is a throughput/cadence failure, not an undetected body-integrity failure.

The unchanged ledger verifies its complete history for each append. Initial extraction of thousands of events therefore retains a substantial repeated-scan cost; body dedup reduces the repeated body component but does not remove per-event history scanning. Reopen/health also verify all retained objects. This task does not broaden into ledger batching, reduced verification, changed health thresholds, slowed polling or a different evidence model. A separate bounded design and new adversarial verification are needed before cadence can be cleared at realistic size/history.

For context only, holding the historical 1,621,486-byte body size constant yields 32.689181 GB/day of Nextgen base64+parsed payload at 10s before metadata. With raw bodies stored once, body-object bytes are `actual_unique_bodies_per_day × 1,621,486`; per-fetch envelopes, events, other feeds and filesystem costs must still be added. The prior audit's other five measured feeds already contributed 2.101965 GB/day, with Combined unknown. A hypothetical 480 unique bodies/day would be 0.778313 GB/day of raw Nextgen objects, **not a measured change rate or a total storage forecast**. No volume recommendation or deployment clearance follows from this arithmetic.

## Reproduction

Run from the candidate repository with `requests` installed and external networking blocked:

```bash
python -B -m unittest discover -s integrity_sentinel -p 'test*.py' -v
python -B -m unittest discover -s integrity -p 'test*.py' -v
python -B -m integrity.adversarial_hardening_v1
python -B -m integrity_sentinel.adversarial_hardening_v1
python -B -m integrity_sentinel.adversarial_remediation_v2
python -B -m integrity_sentinel.adversarial_watchdog_v3
python -B -m integrity_sentinel.adversarial_body_dedup_v1
python -B -m integrity_sentinel.measure_body_dedup_v1 --mode identical
python -B -m integrity_sentinel.measure_body_dedup_v1 --mode change6
python -B -m integrity_sentinel.measure_body_dedup_v1 --mode unique
python -B -m integrity_sentinel.measure_body_dedup_v1 --mode change6 --sustain-seconds 305
python -B -m integrity_sentinel.measure_body_dedup_v1 --mode change6 --records-per-lane 192 --sustain-seconds 305
```

Compilation uses `py_compile.compile(..., doraise=True)` over all 22 Sentinel Python paths, with outputs outside the repository. For the base comparison, extract exactly `b75c0cee90a114590db612f87e33cc10bf959ccb` to a scratch tree and copy only the two offline fixture/measurement harness modules into that scratch copy. No candidate production module is used in the base. A measurement command's zero exit code means results were collected; it does not mean cadence passed. Check healthy-cycle counts, per-source observation counts and cycle durations.

## Safety confirmation

All new work is confined to the new Sentinel branch and Sentinel paths. The verified branch, production main and `integrity/` remain unchanged. No Railway API/action, deployment, redeployment, restart, domain, volume, configuration/variable change, real-evidence change, cutoff change, provider polling, certification window, strategy modification, order or trading action occurred. All fault injection and cleanup involved disposable synthetic data. No merge or pull-request message was issued.

**NEXTGEN BODY DEDUP V1 FAILED — DO NOT DEPLOY**
