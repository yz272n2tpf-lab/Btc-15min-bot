# Sentinel V1 bounded hardening verification

Result: **READY FOR INDEPENDENT READ-ONLY REVERIFICATION**.
No deployment, certification window, strategy promotion, or CLEAN classification is authorized by this result.

## Authority and scope

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Only writable branch: `integrity-sentinel-recorder-v1`.
- Verified starting head: `c34e9831fe11564e04dad11329ff175b9c8c85c1`.
- Mandatory authority: `integrity_sentinel/VERIFICATION_FAILURE_REMEDIATION_V1.md` (unchanged).
- Hardened integrity base: `850c8d870ee6b639bb51df8603cc35e8149229cc`.
- Production main observed: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.
- This task's changes, and the Sentinel delta from the hardened base, are confined to `integrity_sentinel/`. The inherited `integrity/` implementation remains byte-identical to the hardened base. Comparing the entire branch with older production main also includes that pre-existing hardened implementation; it is not a change made by this task.
- The delivered commit containing this report is identified by its exact SHA in the completion response.

## Changes

1. All redirects are refused, including otherwise approved Railway redirects. Each actual GET URL is revalidated immediately before use; returned destination is checked too. No redirected destination/hop is followed. HTTPS Railway hosts only, port 443 only, no user-info syntax (including empty forms), control characters, backslashes, or fragments.
2. `/health` returns 503 and top-level `/state.ok` is false for required-source failure/staleness, membership failure, contract disagreement, missing/mismatched control capture, storage failure, ledger failure, or recorder death/staleness/unrecovered exception. `/state` remains readable. `certifiable_evidence` is always false.
3. Recorder tracks thread liveness, last start/cycle/success/failure, failure count, and last exception type. Errors remain visible and unhealthy until an actual subsequent successful recording cycle; historical failure details remain available after recovery.
4. Ledger verifies newline framing, chain, sequence, byte count, and a durable continuity anchor. It reserves an uncommitted next anchor before appending, checks complete writes, fsyncs records/checkpoints/directories, then durably marks the anchor committed. It only advances counters after that acknowledgement; a complete-looking row after failed fsync is refused on reopen too. Partial/short writes, missing newline, deleted complete rows, and full ledger truncation/removal fail closed across restart. Status verifies instead of assuming validity. A failed write cannot be adopted by a same-process status query.
5. Expected identity fields must be nonblank. Only `cutoff_utc` can explicitly be non-applicable using `{"not_applicable":true,"reason":"..."}`, and actual facts must match this representation. Runtime accepts a separately supplied snapshot via constructor or `SENTINEL_CONTROL_SNAPSHOT`; it requires a timezone-aware non-future `captured_at_utc` and actual facts for all configured sources. Expectation and actual snapshot are recorded by value. No capture is manufactured from expectations.
6. Exact Combined `scorecard.contract_rows` and Nextgen `audit_records -> family -> lane -> list` or `records` wrapper are supported. Early/Final behavior remains. Missing/invalid schemas and conflicting dictionary-key/row IDs fail closed. Historical membership IDs are not compared with the current telemetry contract.
7. Every fetched response gets an immutable observation envelope, including HTTP errors, malformed/wrong-type JSON, empty membership, non-finite JSON, and interrupted transfers. Fields include source, URLs, GET method, timestamps, latency, HTTP status, headers, base64 body bytes, byte count/hash, completeness, parsing/validation results, and normalized facts. Body bytes represent the HTTP entity after Requests content decoding; compressed wire framing is not claimed. Received partial bytes and known status survive interrupted reads. Membership events point back to observation ID and ledger-record hash; repeated observations remain recorded even when event IDs are deduplicated.
8. Generic `source_age_sec` and ambiguous `market_age_sec` never become Kalshi freshness. Only explicit provider-specific fields qualify as such. Missing Kalshi/Coinbase freshness remains UNKNOWN; HTTP success does not manufacture it.
9. All ledger creation/append/checkpoint paths enforce disk availability. WARN can record; FAIL/disk-query failure blocks both telemetry and membership. No emergency failure-marker write is attempted on low disk. Healthy storage snapshots continue to be recorded.
10. IDs require bounded uppercase `KXBTC15M-` ticker syntax without coercion or whitespace repair. Conflicts across explicit root/market/live ID fields are rejected; cross-source telemetry disagreement is durably recorded and unhealthy. All ten known shared-BRTI sequence/error/attempt counters reject bool, negative, fractional, string/malformed, null, and non-finite values.
11. Empty user-info URL forms are rejected explicitly.

## Verification on the final code

| Gate | Result |
|---|---|
| Compile every Sentinel Python source using Python `compile(..., 'exec')` | PASS — 13/13 files |
| Every Sentinel unittest (`test_*.py`) | PASS — 64/64 |
| Every hardened integrity unittest (`test_*.py`) | PASS — 62/62 |
| `python -m integrity.adversarial_hardening_v1` | PASS — 7/7 groups |
| Separate `python -m integrity_sentinel.adversarial_hardening_v1` | PASS — 28/28 probes |
| Git whitespace/diff check | PASS |
| Task paths and hardened-base Sentinel delta | PASS — only `integrity_sentinel/` |
| Hardened `integrity/` unchanged | PASS |

The original 18 Sentinel test methods and assertions are retained. The existing control happy-path fixture now uses explicit non-applicability for its cutoff instead of a forbidden null exemption. There are 46 additional regression tests. The separate probe harness imports neither those tests nor their fixtures; it uses real Requests redirect handling with an offline transport, loopback HTTP for health/state checks, and temporary synthetic ledgers. This is a separate probe rerun in the implementation session, **not the subsequent independent read-only reverification**.

## Every Sentinel adversarial reproduction

| # | Probe | Result |
|---|---|---|
| 1 | Railway redirect to Kalshi | PASS |
| 2 | Railway redirect to Coinbase | PASS |
| 3 | Redirect to HTTP, non-Railway, or another approved Railway hop | PASS — no hop followed |
| 4 | Required telemetry source unavailable while health queried | PASS |
| 5 | HTTP 200 with explicit failure/staleness or stale provider age | PASS |
| 6 | Write exception followed by health; subsequent genuine recovery | PASS |
| 7 | Recorder dead or stale | PASS |
| 8 | Short `os.write()` | PASS |
| 9 | Missing final newline | PASS |
| 10 | Complete trailing-row deletion | PASS |
| 11 | Complete ledger truncation | PASS |
| 12 | Empty/null/blank control expectations | PASS |
| 13 | Missing actual control snapshot | PASS |
| 14 | Explicit control mismatch | PASS |
| 15 | Combined `scorecard.contract_rows` | PASS |
| 16 | Nextgen nested family/lane list and records wrapper | PASS |
| 17 | HTTP error body retention | PASS |
| 18 | Malformed JSON retained with known HTTP status | PASS |
| 19 | Wrong-type JSON body retention | PASS |
| 20 | Successful empty membership observation retained | PASS |
| 21 | Generic source age cannot populate Kalshi age | PASS |
| 22 | Missing Coinbase freshness remains UNKNOWN/INSUFFICIENT | PASS |
| 23 | Low disk blocks membership and other evidence writes | PASS |
| 24 | Invalid contract-ID types/syntax | PASS |
| 25 | Conflicting IDs inside one payload | PASS |
| 26 | Cross-source current-contract disagreement | PASS |
| 27 | Invalid BRTI counters | PASS |
| 28 | Empty user-info URL syntax | PASS |

Additional regressions cover checkpoint short writes, ledger/checkpoint removal, checkpoint and ledger fsync failures, non-finite JSON, interrupted response body retention, real recorder-loop thread death, stale source timestamps, disk-inspection failure, serialization/unexpected-loop errors, source config validation bypass, missing membership schemas, event provenance/deduplication, and membership dictionary-key ID conflicts.

## Hardened integrity adversarial results (unchanged implementation)

| Finding | Result |
|---|---|
| Protected output/input overlap | PASS — 10 cases; source bytes unchanged |
| Invalid numeric measurements | PASS — 40 cases |
| Single sample cannot establish complete feed coverage | PASS — Kalshi/BRTI/Coinbase all INVALID_FOR_CERT |
| Explicit parity failure with zero cumulative counter | PASS — INVALID_FOR_CERT |
| Intermediate cumulative-counter reset | PASS — unknown delta, INVALID_FOR_CERT |
| Explicit feed trouble survives adaptation | PASS — INVALID_FOR_CERT |
| Recorded rollover lag dominates inferred lag | PASS — 35.7 sec retained, INVALID_FOR_CERT |

The positive integrity control remains CLEAN. Machine-readable details for both probe suites are in `HARDENING_PROBE_RESULTS_V1.json`.

## Provider evidence and remaining limitations

- **Kalshi: INSUFFICIENT. Coinbase: INSUFFICIENT.** No live provider-specific source was added, polled, or approved by this work. Synthetic provider fields in tests are not real evidence. Explicit fields, when later supplied by approved sources, still require hardened reconciliation and complete coverage; Sentinel never declares CLEAN.
- BRTI `/state` was statically checked at source commit `98cb9e538d584ad326d19af10924960dbff42672`: the handler calls `poller.snapshot()`, which copies locked in-memory state/counters and performs no upstream request. The Sentinel changes do not touch that code. Nextgen source shape was checked at `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`. Combined structure follows the mandatory remediation authority. No live endpoint was fetched to obtain fixtures.
- A local continuity anchor detects ledger-only truncation/removal/rollback. Coordinated rollback or removal of both ledger and anchor, or an entirely replaced volume, needs an external trusted witness. This change does not claim cryptographic protection against a host administrator replacing all local evidence.
- Existing unanchored ledgers and interrupted checkpoint transactions are refused; there is no automatic migration, truncation, reset, or repair. A storage/write failure can prevent persistence of observations; health fails closed instead of claiming they were captured.
- Control attestation compares an externally captured snapshot at startup. It cannot authenticate the capture independently or discover later live control-plane changes without a new capture. This work does not authorize obtaining/mutating production control configuration.
- Each append and public health query fully verifies the relevant ledger. Growth, memory use for full response retention, and sustained cadence need bounded-volume/soak validation before deployment. The operational freshness watchdog defaults to 30 seconds; it does not relax the hardened reconciler's evidence-coverage limits or any strategy cutoff.
- Linux/POSIX file locking/fsync semantics are assumed. Runtime/volume behavior still needs independent review and a separately authorized pre-deployment gate. No rollout or certification window starts here.

## Every changed path in this task

- `integrity_sentinel/control_attestation_v1.py`
- `integrity_sentinel/recorder_core_v1.py`
- `integrity_sentinel/runtime_v1.py`
- `integrity_sentinel/source_adapters_v1.py`
- `integrity_sentinel/test_control_attestation_v1.py`
- `integrity_sentinel/identity_v1.py`
- `integrity_sentinel/test_hardening_v1.py`
- `integrity_sentinel/adversarial_hardening_v1.py`
- `integrity_sentinel/HARDENING_PROBE_RESULTS_V1.json`
- `integrity_sentinel/HARDENING_VERIFICATION_V1.md`

## Safety confirmation

Only the authorized Sentinel branch is committed/pushed. No main or hardened-integrity edits, merge, Railway action, production/frozen-service action, deployment/redeployment/restart, configuration/variable/volume/domain change, evidence/cutoff reset, strategy change/promotion, direct Kalshi/BRTI/Coinbase request, or trading/order action occurred. Failure injections modified only temporary synthetic test data. No source evidence was edited.

**SENTINEL V1 HARDENING PASSED — READY FOR INDEPENDENT READ-ONLY REVERIFICATION**
