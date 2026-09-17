# Sentinel V1 bounded remediation V2 verification

Result: **READY FOR SECOND INDEPENDENT READ-ONLY REVERIFICATION**.
This result does not authorize deployment, certification, or strategy promotion.

## Authority and scope

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Only changed/pushed branch: `integrity-sentinel-recorder-v1`.
- Verified starting head: `27272bee15f579b2cd0f5a5e879485983b217890`.
- Mandatory authority, unchanged: `integrity_sentinel/REVERIFICATION_FAILURE_REMEDIATION_V2.md`.
- Hardened reconciler base: `850c8d870ee6b639bb51df8603cc35e8149229cc`.
- Production main: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`, unchanged.
- `integrity/` tree: `cb6c41f4bd62246baa272f94f33e54a8a54238ba`, identical at the hardened base, starting head, and remediation commit.
- The exact delivered commit SHA is reported in the completion response. The commit containing this report is the remediation commit.

Permanent rule remains:

**Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence.**

Sentinel is a recorder only; `certifiable_evidence` remains false. An operationally healthy recorder alone cannot certify evidence.

## Blocker 1: persistent durability uncertainty

Every append now creates an exclusive `<ledger>.durability-pending.json` intent marker. Its contents and directory entry are fsynced **before** either ledger or anchor mutation. The marker records the previous acknowledged endpoint, candidate endpoint, timestamp, and unresolved durability state. Genesis creation uses the same protection.

The existing pending/committed anchor protocol is preserved. The marker is removed only after the final committed checkpoint's directory fsync returns successfully. Any failure before that point leaves the already durable marker in place; handling the exception does not depend on successfully writing a new fault record to a failing disk.

There is deliberately no further durability acknowledgment after marker unlink. Unlink is cleanup following an already acknowledged transaction. If cleanup is lost in a crash, the marker may reappear and conservatively refuse an otherwise complete append. This false alarm is preferable to forgetting an unacknowledged write. If marker creation/fsync itself fails, no ledger/anchor mutation follows. A failure before creating any marker leaves only the previously acknowledged endpoint, not a new append to adopt.

Any marker presence, including an empty or malformed marker, blocks verification and appends. Strict ledger open still raises. Runtime uses a diagnostic-only failed open so it can serve `/health` 503 and `/state` with `ok:false`; `chain_valid` is false and `durability_uncertain` exposes unresolved markers. Startup does not append a control attestation to failed ledgers. An ordinary cycle refuses further recording while either ledger is failed.

No recovery command, automatic migration, marker clearance for failed writes, evidence truncation, rewrite, or adoption is implemented. Recovery requires a separately authorized, explicitly audited offline action preserving the ledger, anchor, and fault provenance for review. Merely restarting or restoring source availability is not recovery. This task performs no such recovery.

## Blocker 2: first response survives malformed redirects

`NoRedirectSession` overrides Requests' redirect resolver with an empty iterator. Requests otherwise invokes that resolver even when `allow_redirects=False`, to prepare `Response.next`; malformed Location parsing could therefore throw before `fetch` retained the first response.

The normal Requests adapter, streaming, TLS verification, timeout, and environment behavior remain in use. The Sentinel captures status, headers including Location, response/request URLs, GET method, body bytes/base64/count/SHA-256/completeness, timestamps, latency, JSON parse result/error, and transport/validation error before health evaluation. All 3xx responses remain `RedirectBlocked`. No Location is resolved, prepared, or followed, including an otherwise approved Railway destination.

## Verification

Environment: Python 3.12.14, Requests 2.34.2, Linux/POSIX filesystem semantics. All source transports are offline fixtures; HTTP endpoint checks use loopback only. No production/provider endpoint is contacted.

| Check | Result |
| --- | --- |
| Compile every Sentinel Python file | 15/15 |
| All Sentinel unit/regression tests | 74/74 (64 unchanged existing tests + 10 added tests) |
| All hardened integrity tests | 62/62 |
| `python -m integrity.adversarial_hardening_v1` | 7/7; synthetic positive control remains CLEAN |
| `python -m integrity_sentinel.adversarial_hardening_v1` | All prior 28/28 probes, unchanged |
| `python -m integrity_sentinel.adversarial_remediation_v2` | 9/9 dedicated probes |
| Dedicated redirect cases within those probes | 56/56; exactly one GET per case, zero hops |

Unit suites run with `python -m unittest discover -s integrity_sentinel -p 'test_*.py'` and `python -m unittest discover -s integrity -p 'test_*.py'`. Compilation uses `py_compile.compile(..., doraise=True)` over every Sentinel `.py` file. Existing test files and the prior 28-probe implementation are unchanged. Machine-readable results are in `REMEDIATION_V2_PROBE_RESULTS.json`.

### Dedicated durability reproduction

For **both telemetry and membership ledgers**, the probe:

1. Establishes healthy operation using synthetic sources and controls.
2. Injects exactly one final checkpoint directory fsync failure after the complete ledger row and committed-looking anchor are present and match by sequence/hash/byte count.
3. Confirms the original process reports `/health` 503 and `/state.ok=false`.
4. Exits that Python interpreter entirely.
5. Opens in a second interpreter: strict ledger open rejects, diagnostic runtime reports failed chain/durability status, `/health` stays 503, and `/state.ok` stays false.
6. Runs a normal cycle with otherwise healthy source/storage fixtures; the unresolved fault blocks recording and source polling. Health remains failed.
7. Repeats reopen/cycle in a third interpreter with the same result.
8. Confirms every synthetic ledger, anchor, and marker file has an identical SHA-256 across injection completion and both reopen/cycle processes. No evidence is truncated, rewritten, or adopted.

Additional regressions cover marker short writes, marker file/directory fsync failure, marker creation failure, cleanup failure, malformed marker content, initialization acknowledgment failure, and healthy restart/append. Existing short-write, ledger-fsync, tail deletion, truncation, missing-newline, anchor, and rollback protections remain tested.

### Dedicated redirect reproduction

Real Requests Session dispatch with a streaming in-memory adapter returns 301 and 302 first responses. Both valid object JSON and malformed JSON bodies are tested. Cases include malformed IPv6 Location and undecodable Location, Kalshi, Coinbase, HTTP, non-Railway, alternate Railway, BRTI, custom port, empty/nonempty user-info, fragment, backslash, and control-character destinations.

All 56 cases persist the complete first-response envelope in the ledger, including raw Location as represented by Requests, even when JSON parsing fails. They retain status and body bytes/hash/count/completeness, report `RedirectBlocked`, expose unhealthy endpoints, and make exactly one GET to the configured source. The adapter verifies TLS verification remains enabled and the configured timeout is passed through. Unittest regressions also cover relative and same-source redirects and ensure no `Response.next` request is prepared.

## Remaining limitations

- **Kalshi provider-specific freshness: INSUFFICIENT. Coinbase provider-specific freshness: INSUFFICIENT.** No new explicit provider evidence was obtained. Missing facts remain UNKNOWN and block certification. Generic source freshness is not provider freshness.
- Healthy operation still requires a separately captured, independently sourced control-plane snapshot matching the frozen expected manifest. Sentinel cannot independently authenticate that capture or discover later live control-plane changes from a startup snapshot.
- Coordinated rollback/removal of the local ledger and continuity anchor (and any local marker), or replacement of the whole volume, still requires an external trusted witness. Local markers do not protect against an administrator replacing all local provenance.
- The previous five-minute synthetic load run does not establish long-run capacity. Full-ledger verification costs grow with evidence, full response retention uses memory, and the added durability operations add I/O cost. Later separately authorized soak/capacity validation remains necessary.
- POSIX fsync/locking and underlying storage honoring successful fsync are assumed. Crash-reappearing cleanup markers can cause conservative false alarms requiring explicit audited recovery. No automatic recovery or production rollout is authorized.

## Exact changed paths

- `integrity_sentinel/recorder_core_v1.py`
- `integrity_sentinel/runtime_v1.py`
- `integrity_sentinel/test_remediation_v2.py`
- `integrity_sentinel/adversarial_remediation_v2.py`
- `integrity_sentinel/REMEDIATION_V2_PROBE_RESULTS.json`
- `integrity_sentinel/REMEDIATION_V2_VERIFICATION.md`

## Safety confirmation

All changes are confined to `integrity_sentinel/` on the authorized branch. `integrity/`, mandatory authorities, prior tests/probes, and production `main` remain unchanged. No Railway action, production/frozen-service action, deployment/redeployment/restart, configuration/variable/volume/domain change, real evidence mutation/reset, cutoff change, certification window, direct provider polling, strategy change/promotion, order, or trading action occurred. Failure injection affected only temporary synthetic fixtures. No merge occurred.

SENTINEL V1 REMEDIATION V2 PASSED — READY FOR SECOND INDEPENDENT READ-ONLY REVERIFICATION
