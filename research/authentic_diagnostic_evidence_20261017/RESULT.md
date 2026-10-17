# Authentic diagnostic evidence investigation — 2026-10-17

**NOT READY for one corrected native diagnostic with the current package.**
The raw-evidence access blocker is cleared. The candle and charge corrections
in `f1a234e670890f64a5a0eff11704dfbfde9bcd16` are now supported by the authentic
recording. The seven information failures are actual publisher rejections with
unrecorded reasons, not missing input vectors or duplicate-input skips. Native
hook latency remains unqualified. The smallest remaining change is bounded,
capture-only observation of the original publication outcome and its actual
validation readings; the precise contract is below. No strategy repair is
justified by this recording.

Result branch: `research/authentic-diagnostic-evidence-20261017`. The commit
containing this report identifies the investigation. Its parent is the supplied
`f1a234e670890f64a5a0eff11704dfbfde9bcd16`. No existing production, recorder,
reader, validator or strategy file changes in this commit. The prior fixes and
all previous results remain intact. This is not an authorization to deploy.

## Original bytes recovered

Exactly **10,890,786 compressed bytes**, all three segments, were extracted from
`/research-evidence/DIAG_20261017_e2294683_f7c32d04-reader/raw/`.
All original sizes and SHA-256 hashes match `evidence-and-scope.json` in the
parent investigation. Nine identity/terminal/seal files also match; total
transfer is 12 objects / 10,909,351 bytes. Record hashes, contiguous sequences,
previous-hash chains, final seal hashes, configuration and runtime bindings
were verified. The three streams contain 50,412 original envelopes totaling
54,287,776 uncompressed bytes.

| Role | Original relative segment path | Bytes | SHA-256 |
|---|---|---:|---|
| MAIN | `main/source.segments/20261017-a04257833f454c39aeac18b2316a6d83-f947dfca.jsonl.gz` | 2,475,953 | `f8b106347fa7020375b7656dc90106ab7feada4c0698371c1c9fa85808c0267b` |
| V81 | `v81/source.segments/20261017-06ac374debbf4e4ab11f2346ddf4498b-58722f85.jsonl.gz` | 8,105,094 | `2d30908bb04dcd8cc415d28934908958182e2cb2461939a5722fc5af79f55dd4` |
| Information | `information/information.segments/20261017-6298839aa7bd475db3675721e190ddf2-93e0f8cc.jsonl.gz` | 309,739 | `02c6a32b8435e2a7a48e2b7b0287b02ab6288a8f2e75c4769f6c3e5ebea3e83d` |

One authorized extraction used the existing research service
`1fff593b-8b09-4cc4-8c51-f9603082657f`, volume
`2dba2ef6-b84d-4abf-9d04-58a1e77082c5`, deployment
`904b2d25-16e9-4069-8b53-bddbde44ab07`. Source stayed pinned to
`950e4b5e401d501bb26b5a66473e06500e8c08ac`. Its inline standard-library exporter
verified every object before emitting any bytes and used O_RDONLY, O_NOFOLLOW
and O_NOATIME. The export took **54.2033 seconds**, with a 175-second alarm and
180-second external deadline. No SSH, producer access, native capture or
source writes occurred. The research start command was restored exactly;
readback shows no staged research patch, restart NEVER and zero running
replicas. No production operation or volume mutation occurred. No new service
or volume was created. Billing was not re-investigated or claimed verified.

## Four findings

### Hook latency — native result remains FAIL

The original MAIN QUOTE_ACCEPT maximum was **72,054,830 ns**; V81 QUOTE_RECEIVE
was **21,521,287 ns**, both above the unchanged 5,000,000 ns limit. The raw health
records contain aggregate wall measurements, not per-overrun queue wait,
thread CPU or scheduler/GIL observations. Therefore those exact overruns
cannot honestly be attributed to a particular blocking operation.

The parent fix removes a demonstrated blocking Queue.mutex acquisition in
recorder admission, adds slow-hook CPU/off-CPU metrics and fails explicitly on
contention. Focused tests pass. It does not prove native timing or loss-free
operation. No serialization, compression or fsync is moved onto a native
callback. A corrected diagnostic must retain the original 5 ms and p99 guards
and measure native performance; old missing timing observations cannot be
recreated offline.

### MAIN sequence 308 — authentic interpretation PASS

Record `1b7b43398fbfb5d53b6f570dbb3c02b27b20d64d9f715ec2bc701a1e28f3224a`,
row 254, contains the current bucket, not a future bucket start:

| Observation | Original Unix seconds |
|---|---:|
| Bucket start | 1792240980.0000000 |
| Original HTTP receipt, MAIN sequence 34 | 1792240994.6833951 |
| Cache acceptance, MAIN sequence 308 | 1792241018.1594200 |
| Native bucket end and source clock | 1792241040.0000000 |

Original HTTP response SHA-256 is
`0410120b0ca785807fda325717d81c117d03e6adc8a2204c6986f18bb2a11aa1`.
Its first wire row is `[1792240980,81398.47,81398.48,81398.48,81398.47,0.01092997]`
in upstream start/low/high/open/close/volume order. It matches the captured
native OHLCV exactly. The pinned producer shifts clocks to bucket end while
retaining the current bucket. The old reader's requirement that every cache
row end by cache acceptance was wrong. The parent correction preserves this
row as **uncompleted at acceptance**, without completed-original HTTP credit.

The single MAIN original journal record, sequence 329, is UNAVAILABLE with
`QUOTE_SOURCE_UNAVAILABLE`; it supplies no applicable MAIN feature decision.
All 79 captured information anchors were inspected. The partial row is absent
before its end and appears in 15 later anchors, first at decision
1792241041.159097. Native cutoff behavior is preserved. Later passage of time
does not prove the earlier partial HTTP row became final OHLCV: the corrected
reader still requires final-time original provenance. No clocks, candles or
decisions were rewritten or promoted.

### Durability charge definitions — exact reconciliation PASS

Every admitted observation was reconstructed from the exact archived payloads,
wire-byte dictionaries and existing information-vector decoder. Each original
payload/input hash was verified. Admission counts and charge totals match
**for every recorded kind**, not just in aggregate. The old post-Archive.observe
mutation formula reproduces both terminal deficits exactly.

| Role | Admitted observations | Immutable admission charge | Original old durable charge | Exact definition difference |
|---|---:|---:|---:|---:|
| MAIN | 3,000 | 12,257,232 | 10,275,140 | 1,982,092 |
| V81 | 30,644 | 67,731,083 | 45,850,179 | 21,880,904 |
| Information | 146 | 19,358,782 | 19,358,782 | 0 |

Archive.observe removes raw quote/HTTP fields and adds archive metadata. The
old processed-charge calculation ran after that mutation. Quoted wire messages
have both byte/string bounds calculated; per-kind recorded admission totals
equal the string bound exactly, disambiguating the admitted representation.
The parent fix computes the original admission charge before processing and
requires exact terminal equality. Batching, drain, fsync failure and seal tests
pass. All original counters and INCOMPLETE seals are preserved. This is a
counter-definition reconciliation, **not recovered evidence or a clean-run
claim**. Zero reported queue losses does not supply observations after capture
stopped.

### Information publication — seven genuine rejections; reasons missing

All 79 original inputs reconstruct to their recorded hashes: 72 published and
seven returned false. Each failed input is immediately followed by its original
failure. Replaying only the existing pure quote/source-progress functions shows
genuine progress against the previous successful publication in all seven.
The no-progress false branch is excluded. The original publisher's remaining
false branch is a validation/evaluation rejection. There is no evidence that
these were recorder association defects or that an input is missing.

| Failure sequence | Exact input sequence | Previous published input | Minimum freshness slack at captured cut (s) |
|---:|---:|---:|---:|
| 141 | 140 | 138 | 2.338511 |
| 158 | 157 | 155 | 2.306690 |
| 185 | 184 | 181 | 0.795261 |
| 189 | 188 | 181 | 0.023982 |
| 209 | 208 | 205 | 1.136391 |
| 215 | 214 | 212 | 2.729060 |
| 227 | 226 | 222 | 1.375409 |

Exact input/record hashes, prior frame IDs, owner epochs and clocks are in
`findings.json`. Positive slack at capture does not prove freshness at either
native validation or publication. In particular, 23.98 ms is not evidence that
sequence 189 actually expired. Native rejection reasons, both health reads and
validation clocks were never recorded; their values cannot be inferred.
All seven remain INFORMATION_FAILURE under the existing quarantine rules.

Corrected replay exposes a separate, explained source-coverage gap at the first
information input, sequence **38**. Its BRTI source timestamp is 1792241020.0,
receipt 1792241021.5875683, value 81405.28. MAIN's capture-stop boundary is
1792241021.5355039: the required receipt is **52.0644 ms later**, with no matching
original BRTI SOURCE observation in the complete MAIN segment. Native owners
continued after the latency stop as designed. A copied input field cannot be
substituted for that original source receipt. The strict association failure is
correct. V81 also ends with QUOTE_RECEIVE sequence 45830, followed by the latency
boundary and STOP, without captured owner acceptance; that failure is retained.

## Focused replay and regressions

The existing `ops.live_recording.finish --read-only ... --profile early_diagnostic`
ran twice, sequentially, into fresh output directories over identical hardlinked
raw bytes. No replacement reader or quarantine bypass was used. Summary,
window, issue, association and V81 association ledgers are byte-identical
(`replay-equivalence.json`). The measured second execution took **27.0865 s**,
peak RSS **36,220 KiB**, work database **105,029,632 bytes**. These are observations
for this exact recording, not capacity projections.

Result: **INCOMPLETE / NO_GO**, with **27 verified V81 causal associations**,
27 lifecycle PASS records, one correctly retained current cache candle,
7,199 completed cache observations with original HTTP credit, and 50,399 cache
observations with unknown qualifying upstream receipt. **195 records remain
quarantined**. All seven publisher failures remain. Missing MAIN applicable
decisions, information associations and authoritative settlement remain missing.
No 20-minute or 10-hour readiness is claimed.

| Same captured bytes | Original reader receipt | Corrected authentic replay |
|---|---:|---:|
| Candle sequence 308 record-verification failures | 1 | 0 |
| V81 causal matches | 0 | 27 |
| Quarantined records | 50,099 | 195 |
| Information publication failures | 7 | 7 |
| Qualification | INCOMPLETE | INCOMPLETE |

**32 focused tests pass in aggregate:** seven authentic-evidence regressions,
18 parent-fix regressions, six existing candle regressions and the existing
1,500-envelope batch/hash-chain comparison. The first command ran 31 actual
tests successfully but had one incorrect test-class selector (loader error).
That error is preserved in `test-results.txt`; the corrected single selector
passed in `test-selector-correction.txt`. No diagnostic or failing native run
was repeated to obtain a pass. No capacity or infrastructure test was run.

All 23 original result artifacts still match; 38 MAIN and 14 V81 protected
package files and the original three information modules match pinned hashes.
FINAL, EARLY, SCALP, Kalshi integration, native clocks, entry policies, source
freshness, timing thresholds and signal-only behavior are unchanged. Historical
volumes and the four staged production changes were not modified.

## Exact remaining action

The raw-evidence investigation is complete. Another access probe or general
readiness cycle cannot resolve observations that were never captured.

Before packaging one separately authorized corrected diagnostic, add a bounded
recorder-only publication-outcome observation tied to the existing input hash:

1. Original return/exception, the actual native unavailable reason, and an
   unambiguous no-progress versus rejection outcome; preserve false as false.
2. The **actual** health-reader return values and clock values used by the
   original pre-evaluation and post-evaluation validations, in call order.
3. Original prior publication key/frame ID and resulting frame ID, plus outcome
   stage; do not re-evaluate, refetch health, invent clocks or change thresholds.

Retain the parent's hook CPU/off-CPU telemetry. To attribute an overrun rather
than merely detect it, preserve a bounded overrun sample with role/hook/event
identity, wall/thread-CPU interval and queue-admission outcome. The 5 ms stop
must remain effective. A healthy overlapping capture must retain original
source acceptances needed by information inputs; an early producer stop must
continue to invalidate downstream associations, not trigger invented evidence.

These are narrowly identified missing observations, not implemented changes in
this investigation. Their recorder-only implementation, focused equivalence
checks and exact installation identities are the remaining pre-rerun blocker.
Native latency and clean associations are then measured by the separately
authorized diagnostic itself. No production activation is requested now.

The sequence remains: corrected 60-second diagnostic → 20-minute preflight →
fixed **10-hour EARLY** evaluation → evidence-based improvements → complete
signal-only production acceptance and forward review.
