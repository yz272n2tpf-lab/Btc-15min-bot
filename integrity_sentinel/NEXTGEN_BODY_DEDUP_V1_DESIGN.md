# Nextgen body dedup V1 — isolated candidate

Base: `b75c0cee90a114590db612f87e33cc10bf959ccb`.
Branch: `integrity-sentinel-nextgen-body-dedup-v1`.
See `NEXTGEN_BODY_DEDUP_V1_VERIFICATION.md` for the acceptance decision and measured limits. This design is not deployment or certification authority.

## Scope and observation contract

Only `nextgen_membership`, kind `membership`, request path `/audit` is eligible. Telemetry remains 5 seconds; Early, Final, Combined and Nextgen membership remain 10 seconds. URLs, timeouts, scheduling, control attestation, watchdog validation, source-health rules, disk thresholds and permanent no-orders/no-certification state are unchanged. Concurrent membership calls on one runtime are serialized without coalescing observations.

Every fetch still produces its own timestamped `SOURCE_OBSERVATION` before its derived membership events. It retains the UUID, cycle, request/response URL, HTTP method/status, response headers, start/end timestamps, latency, completeness, exact entity-byte SHA-256 and byte count, body representation, parse outcome/error, validation error when present, source failure reasons, normalized facts and safety flags.

Only complete 2xx JSON objects with no parse, validation, transport or source-health failure are externalized. Failed HTTP responses, redirects, partial transfers, malformed JSON, wrong-type JSON and source-health failures retain their own original inline bytes/payload; they never use a prior response. A no-response attempt remains a no-response attempt.

A successful externalized envelope has `body_ref = {scheme: NEXTGEN_SHA256_V1, sha256: ..., bytes: ...}`, `payload_storage: NEXTGEN_SHA256_V1`, and null `body_base64`/`payload`. The immutable object is the exact Requests-decoded HTTP entity bytes (the same representation captured by the base), not normalized JSON, selected IDs, an ETag or the producer's source hash. Even a whitespace byte changes the key. Original bytes permit exact JSON reconstruction. Raw-byte storage also removes the base's second persisted parsed representation; this encoding effect is distinct from cross-observation deduplication.

`NextgenBodyStore.resolve(observation)` verifies and returns the bytes for that specific envelope. `parse_body(raw)` provides the same strict object parse, including rejection of non-finite numbers. Membership extraction still uses the original per-fetch parsed payload. Before storage, a strict parse of the actual bytes must match that payload canonically; a mismatch aborts. Event identity, full record and exact contract ID are unchanged. Each new event retains its observation UUID and ledger record hash, and gains `observation_body_sha256` when its parent is externalized. Unchanged membership events retain their original first-observation linkage, as in the base; repeated observation envelopes are never omitted.

## Storage and ordering

Lazy-created `nextgen-bodies-v1/` contains:

- `<sha256>.body`: one raw object, exclusively created with mode 0400, never overwritten or removed by Sentinel.
- `catalog.jsonl` and its original-style continuity anchor: immutable-object digest/length registration through the unchanged `AppendOnlyHashChainLedger` implementation.
- A transient `durability-pending.json` intent during object publication; the catalog also uses its own original ledger durability marker during its append.

Object publication is serialized across store instances/processes with POSIX directory `flock`, plus an in-process lock. The order is durable intent → exclusive body creation → body fsync → directory fsync → durable catalog append/anchor → directory fsync → intent cleanup → observation reference append using the existing membership ledger durability protocol. Every write is guarded by the unchanged disk guard. Existing bodies are read and verified before reuse, never rewritten.

Only completed-transaction transient intent cleanup uses unlink. There is no garbage collection, retention pruning, referenced-body deletion, rewriting, automatic repair or evidence migration. A durably cataloged object whose observation append fails is retained for independent inspection. An unregistered object, extra file, pending intent or catalog/object mismatch fails closed. A failure before any intent/evidence exists can leave an empty directory; no evidence was adopted or lost in that case.

## Integrity and reopen

`NextgenMembershipLedger` invokes the existing full ledger/anchor verification and adds catalog verification, SHA-256/length verification of every cataloged object, strict reference/metadata agreement and observation/event linkage checks. Body symlinks are refused. It does this on startup, append verification, status/health and each recording cycle. Missing, changed, truncated or mismatched content prevents the membership ledger from reporting valid. Startup's existing diagnostic failure path then blocks source polling, and public health remains failed. Tests check that healthy controls and later cycles cannot clear such faults, including two fresh processes.

The original recorder core, anchor/marker code, watchdog validator, source adapters, storage guard, control attestation and all `integrity/` code remain byte-identical. The subclass adds a gate; it does not weaken or replace those checks. Legacy inline Sentinel observations remain readable without rewriting. Generic old chain-only readers do not validate external body dependencies: candidate replay/verification must use the new body-aware ledger/resolver. No reconciler adoption or certification is claimed.

The trust boundary remains the existing POSIX filesystem/durability model. Coordinated malicious replacement of all local evidence and anchors requires an external trusted witness; local hash chains cannot prove against it. Hash-addressed objects are not a hardware WORM facility. Verification reads the actual bytes rather than treating file permissions or an in-memory cache as proof.

## Measurement contract

`measure_body_dedup_v1.py` uses all seven synthetic source transports and a nested family/lane/record Nextgen body modeled on pinned Nextgen `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`. It never imports/runs a producer or contacts a service. The same harness is run against the exact base and candidate packages in separate Python processes. The benchmark reports retained bytes, application `os.write` bytes including ledger/anchor/intent writes, allocated blocks, files/directories, object growth, CPU/wall time, process peak RSS and reopen integrity/time. Disk-controller/filesystem journal write amplification is not measured.

The smaller fixture has 16 records × 4 synthetic lanes × 4 producer-shaped families. The larger fixture has 192 records per lane and is sized near the prior audit's 1,621,486-byte Nextgen body. All records/prices/outcomes are fabricated. The prior size is historical evidence from the saved September 17 environment audit, not a new live measurement. Other source fixtures are deliberately small: projections are benchmark-mix figures, not seven-source production capacity estimates. Combined's real size remains unknown.

Identical, one-version-per-six-observations and every-response-different cases are reported separately. No cross-observation body savings are claimed when every response differs. Every unique body adds a permanent file; there is no cleanup. Daily figures are decimal-GB extrapolations of finite measured windows, include cold-start event costs, and are not long-run forecasts. The unchanged full-ledger scans and the new full object verification both grow with retained history. In particular, a storage reduction must not be mistaken for a guarantee of the requested live observation cadence.
