# Integrity Sentinel / Recorder V1 — Verification Failure Remediation Authority

Status: **BLOCKED — DO NOT DEPLOY** until every blocking item below is fixed and independently reverified.

Authority base:
- Sentinel verification-failed head: `771037b00155a24b22f5c3c6cc696e961c84468b`
- Hardened reconciler base: `850c8d870ee6b639bb51df8603cc35e8149229cc`
- Production main remains: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`

Permanent project rule:

> **Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence.**

The Sentinel is an evidence recorder only. It must never manufacture PASS, declare CLEAN, promote strategy logic, reset cutoffs, or place orders.

## Required blocking fixes

### 1. Redirect-safe outbound network enforcement
- Disable automatic redirects on all source GETs, or validate every redirect hop before following it.
- Any redirect to non-HTTPS, non-`*.up.railway.app`, embedded-userinfo, Kalshi, Coinbase, or any other non-approved host must fail closed.
- Preserve GET-only behavior.
- Add tests for direct URLs and redirect targets, including plain HTTP and provider hosts.

### 2. Fail-closed `/health` and `/state`
- Public health must incorporate recorder-loop liveness/freshness, source availability, required-source status, contract agreement, control attestation status, ledger integrity, storage status, and membership-source health.
- A source JSON payload explicitly reporting failure must not become source `ok=True` merely because HTTP/JSON parsing succeeded.
- A green endpoint alone must never imply certifiable evidence.
- `/health` must return non-200 when required health conditions fail; `/state` may remain readable but its top-level `ok` must fail closed.

### 3. Recorder-loop and write-failure liveness
- Track recording-thread alive status, last-start, last-success, last-cycle, failure count, and last exception type.
- Any ledger-write, disk-inspection, serialization, or unexpected recorder-loop exception must flip health to fail closed and remain visible until a genuinely successful subsequent cycle is recorded.
- The HTTP thread must never remain green on stale cached state after the recorder thread has died or stalled.

### 4. Strong append-only ledger integrity
- Detect and reject short writes; do not advance in-memory sequence/hash/counter until the entire record is durably written and fsynced.
- Reject missing final newline / partial tail before appending.
- Do not silently accept complete trailing-record deletion or complete truncation as a valid continuation of an existing ledger.
- Add a durable sidecar/checkpoint or equivalent continuity anchor so truncation/removal of complete trailing rows is detectable across reopen/restart.
- `status()` must not default `chain_valid=True` without verification/continuity proof.
- Reopen must prove continuity before recording.

### 5. Control-plane attestation must be complete and actual
- Expected manifests must require non-null, non-blank values for every required identity field unless a field is explicitly modeled as non-applicable with a separate representation.
- Empty/blank expected manifests must never produce PASS.
- Missing actual control facts => UNKNOWN/FAIL-closed for health; explicit mismatch => FAIL.
- Runtime must ingest or be supplied a separately captured actual control snapshot and compare it to the frozen expected manifest; merely recording expectations is insufficient.
- Control mismatch or missing attestation must make Sentinel health fail closed.

### 6. Exact membership extraction for deployed payload shapes
- Combined: explicitly support deployed `scorecard.contract_rows` and any verified exact-ID containers used by the deployed scorer.
- Nextgen V2: descend `audit_records -> family -> lane -> records` (or the exact verified deployed shape) and extract explicit contract IDs without inference or rescoring.
- Preserve Early and Final extraction behavior.
- Add tests using the real deployed payload shapes.

### 7. Complete raw-response evidence retention
- Preserve an immutable observation envelope for every fetch attempt, including successful empty membership responses.
- Retain HTTP status, headers/provenance as appropriate, body bytes/text or a complete faithful retained representation, body hash, parse outcome, parse/type error, source identity, timestamps, latency, and normalized fields when available.
- HTTP error bodies, malformed JSON bodies, and wrong-type JSON bodies must not be discarded.
- Known HTTP status must survive JSON/type failures.
- Membership recording must preserve the surrounding source observation/provenance envelope in addition to selected membership events.

### 8. Correct feed-specific freshness semantics
- Remove the `source_age_sec -> kalshi_age_sec` alias. Generic/unified source age is not Kalshi fetch freshness.
- Only explicit, provider-specific Kalshi freshness/age/success timestamp may populate Kalshi fields.
- Coinbase must remain UNKNOWN until an explicit Coinbase-specific age/freshness/success timestamp is supplied by an approved Railway source.
- HTTP success must never manufacture provider freshness.
- The Sentinel may record insufficient fields, but must not relabel them.

### 9. Storage guard must cover all writes
- Low-disk FAIL must stop both telemetry and membership writes except, if safely possible, one bounded pre-reserved failure marker that cannot worsen ENOSPC risk.
- Every ledger append path must check storage/write availability consistently.
- Disk-query failures must fail health closed.
- Storage WARN may continue recording; Storage FAIL may not continue membership capture.

### 10. Strict identities, counters, and cross-source contract agreement
- Contract IDs must accept only strings matching the expected BTC15 ticker/ID representation; booleans, numbers, mappings, lists, blanks, and conflicting explicit ID fields must fail closed rather than stringify/choose by precedence.
- Conflicting `contract` / `contract_id` / `ticker` values within a payload must be surfaced as an identity conflict.
- Cross-source explicit contract disagreement within the same Sentinel cycle must be recorded and must fail health closed.
- BRTI counters must reject booleans, negatives, non-integers, NaN/infinity, and malformed types.

## Non-blocking hygiene fix

### 11. Empty user-info URL syntax
- Reject any URL containing user-info syntax, even if username/password are empty (for example `https://@host/...` or `https://:@host/...`).

## Required adversarial regression tests

Do not weaken existing tests. Add explicit reproductions for all verification failures, including:

1. Railway URL redirecting to Kalshi.
2. Railway URL redirecting to Coinbase.
3. Railway URL redirecting to plain HTTP/non-Railway host.
4. One required telemetry source unavailable while `/health` is queried.
5. Explicit source payload stale/failure while HTTP is 200.
6. Ledger append/write exception followed by `/health`.
7. Recorder thread/cycle stale or dead.
8. Short `os.write()`.
9. Missing final newline.
10. Removal of complete trailing row(s).
11. Complete ledger truncation.
12. Empty/null/blank control expectations.
13. Missing actual control snapshot.
14. Explicit control mismatch.
15. Real Combined `scorecard.contract_rows` membership extraction.
16. Real Nextgen nested audit-record extraction.
17. HTTP error body retention.
18. Malformed JSON body retention with known HTTP status.
19. Wrong-type JSON body retention.
20. Successful empty membership observation envelope retention.
21. Generic `source_age_sec` must not populate Kalshi age.
22. Missing Coinbase provider-specific freshness remains UNKNOWN.
23. Low disk blocks membership writes.
24. Invalid contract-ID types.
25. Conflicting explicit IDs inside one payload.
26. Cross-source contract disagreement.
27. Invalid BRTI counters (bool/negative/fractional/malformed/non-finite).
28. Empty user-info URL syntax.

## Required verification before any deployment

- Compile every Sentinel `.py` file.
- Run all Sentinel tests.
- Run all hardened `integrity/` tests and `python -m integrity.adversarial_hardening_v1`.
- Run independent temporary adversarial probes reproducing every item above.
- Confirm branch changes remain confined to `integrity_sentinel/`.
- Confirm no Railway, production, evidence, cutoff, strategy, or trading action occurred.
- Confirm Kalshi evidence remains **INSUFFICIENT** unless a provider-specific approved source exists.
- Confirm Coinbase evidence remains **INSUFFICIENT** unless a provider-specific approved source exists.
- Confirm BRTI `/state` reads remain snapshot-only and do not trigger upstream provider requests.

Only after independent read-only reverification passes may this branch advance to a **pre-deployment** gate. Passing this document does not itself authorize deployment or start a certification window.
