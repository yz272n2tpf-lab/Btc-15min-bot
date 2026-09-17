# Sentinel V1 bounded remediation V3 verification

Result: **READY FOR THIRD INDEPENDENT READ-ONLY REVERIFICATION**.
No deployment or certification is authorized by this result.

## Authority, branch and scope

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Authorized branch: `integrity-sentinel-recorder-v1` only.
- Verified starting head: `a9ac1fbd6fc0975e230e6bcc37a49ecbee25f375`.
- Mandatory authority, unchanged: `integrity_sentinel/SECOND_REVERIFICATION_FAILURE_REMEDIATION_V3.md`.
- Hardened integrity base: `850c8d870ee6b639bb51df8603cc35e8149229cc`.
- Production main: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`, unchanged.
- Integrity tree: `cb6c41f4bd62246baa272f94f33e54a8a54238ba`, identical to the hardened base and starting head.
- The commit containing this report is the V3 remediation commit; its exact SHA is supplied in the completion response.

All seven changed paths are under `integrity_sentinel/`:

1. `runtime_v1.py`
2. `watchdog_health_v3.py`
3. `test_watchdog_v3.py`
4. `adversarial_watchdog_v3.py`
5. `WATCHDOG_SCHEMA_V3.json`
6. `REMEDIATION_V3_PROBE_RESULTS.json`
7. `REMEDIATION_V3_VERIFICATION.md`

The existing 74 Sentinel tests, prior adversarial modules, recorder core, storage protection, control attestation, membership extraction, source adapters, and all `integrity/` files are unchanged. Hash checks cover all 566 tracked files outside `integrity_sentinel/`.

## Frozen producer schema evidence

Read-only Git object inspection used the exact frozen deployment SHAs recorded by the preceding independent reverification. No service was imported, started, polled, or changed. `WATCHDOG_SCHEMA_V3.json` records Git blobs, whole-file SHA-256 hashes, original line numbers, and verbatim function excerpts. These were extracted anew from Git; their ASTs match the earlier preserved source functions.

| Service | Frozen commit | Source and relevant lines | Actual watchdog location |
| --- | --- | --- | --- |
| Early | `98d4cc8685d85bcab07b99448161c6d868c32b52` | `BTC15_EARLY_FORWARD_SCORECARD_V1.py`: `runtime_health` at 452, worker loop at 481, handler at 584 | Root `/state.watchdog` |
| Final | `5a767fd40d394f86e9012bd96a9efefabfd081bf` | `BTC15_FINAL_FORWARD_SCORECARD_V4.py`: handler at 210; calls V3 `runtime_health` | Root `/state.watchdog` |
| Final watchdog implementation | Same Final commit | `BTC15_FINAL_FORWARD_SCORECARD_V3.py`: `runtime_health` at 105, worker loop at 134 | Returned to Final V4 root watchdog |

Both actual `/state` handlers return HTTP 200 with root `ok=true`, independently of watchdog health. Neither inspected frozen producer emits `live.watchdog`. Sentinel additionally supports that explicit nested envelope conservatively; this is a compatibility location, not a claim about the frozen producers. If both locations exist, both are checked independently. A healthy one cannot override a negative or malformed one.

Both watchdog producers emit exactly these 11 fields:

| Field | Producer meaning / V3 handling |
| --- | --- |
| `healthy` | Boolean calculated from worker alive and known age within threshold. Present value must be exactly `True`; missing or malformed fails. |
| `observer_worker_alive` | Boolean worker state. Explicit false or a non-boolean value fails, including contradictions with `healthy=true`. |
| `observer_age_sec` | Age of the most recent iteration; can be null before any iteration. Present value must be a finite nonnegative number. Null is insufficient. |
| `observer_stale_sec` | Producer's configured stale threshold. Present value must be a finite positive number. No threshold/cutoff is changed or inferred. |
| `observer_last_exception` | Current worker exception string, cleared to null after a successful iteration. A nonempty exception fails even when `healthy=true`; malformed values also fail. |
| `observer_restarts` | Historical count, retained unchanged; a past restart does not itself mean current worker failure. |
| `observer_iterations` | Historical count, retained unchanged. |
| `observer_successes` | Historical count, retained unchanged. |
| `observer_last_iteration_utc` | Producer timestamp retained unchanged; not converted into provider freshness. |
| `observer_last_success_utc` | Producer timestamp retained unchanged; not converted into provider freshness. |
| `active_generation` | Worker generation retained unchanged. |

Age greater than the producer threshold fails even with a contradictory healthy flag. When one age/threshold field is supplied without its counterpart, health fails as incomplete. The producer permits equality at the stale threshold; V3 preserves that rule.

The frozen code does **not** emit textual watchdog `status` or `state`. Its real negative forms are worker-alive false, age beyond threshold, `healthy=false`, and a current `observer_last_exception`. Tests also cover defensive compatibility `status`/`state` fields: negative, unknown, or malformed values cannot override health. These tests are not represented as deployed textual states.

## Change in behavior

Watchdog validation runs on every parsed observation before normalization or membership extraction, including parsed HTTP error responses. Failures carry a stable location/field reason, such as `watchdog.healthy:false`, `live.watchdog.observer_worker_alive:false`, `watchdog.observer_age_sec:stale`, or `watchdog.observer_last_exception:present`.

Required Early/Final sources with no watchdog fail with `watchdog:missing`. An existing watchdog without `healthy` fails with `.healthy:missing`. Neither wrapper health nor a prior healthy cycle fills in missing watchdog evidence. Optional fields are not synthesized. A minimal explicit `healthy=true` is an assertion from the source; any other supplied watchdog fact must also pass its checks.

Every tested explicit negative case has source `ok=false`, a watchdog reason in `source_failures`, HTTP 503 from Sentinel `/health`, and `/state.ok=false`, despite HTTP 200, positive wrappers, and valid membership records. Validation never rewrites the original payload or response bytes. Ledger observations retain the full body, SHA-256, byte count, headers, URLs, status, parse result, timing, and failure reasons. Derived membership remains linked to its immutable observation; it is not certification.

A later genuinely healthy membership cycle may restore current source health. A successful telemetry-only cycle cannot erase an earlier membership failure. Another failed source or any existing recorder/control/storage/ledger/contract gate still prevents operational health. Tests verify earlier ledger bytes remain an identical prefix after the unhealthy and recovery cycles, and the resulting ledger verifies on reopen.

## Exact verification results

Environment: Python 3.12.14, Requests 2.34.2. Source transports are in-memory fixtures; public endpoint probes use actual HTTP on loopback. The interpreter's audit guard rejects external DNS and connections, including child interpreters used by V2 probes. All injected damage affects disposable synthetic ledgers only.

| Required check | Result |
| --- | --- |
| Compile every Sentinel Python file | **18/18** |
| All Sentinel unit/regression tests | **296/296**: 74 unchanged tests + 222 new V3 tests |
| All hardened integrity tests | **62/62** |
| `python -m integrity.adversarial_hardening_v1` | **7/7** |
| `python -m integrity_sentinel.adversarial_hardening_v1` | **28/28** |
| `python -m integrity_sentinel.adversarial_remediation_v2` | **9/9** |
| `python -m integrity_sentinel.adversarial_watchdog_v3` | **216/216** |
| Original prior verifier's false-health function rerun | **16/16** |
| Original prior verifier's redirect function rerun | **80/80** |
| Original prior verifier's raw-retention function rerun | **6/6** |
| Original membership/provider probe rerun | **PASS**, all 5 membership events preserved/deduplicated; missing provider facts remain UNKNOWN |

Unit suites used `python -B -m unittest discover -s integrity_sentinel -p 'test*.py' -v` and the equivalent `-s integrity` command. Compilation used `py_compile.compile(..., doraise=True)` over every Sentinel Python file, with bytecode output outside the repository. Tests did not write bytecode into `integrity/`.

### Dedicated independent V3 results

The dedicated probe imports neither unit-test fixtures nor the watchdog validator. It independently supplies Requests transport fixtures, replays the pinned producer functions in isolated namespaces, and calls Sentinel endpoints over loopback. Replaying individual source functions does not import or start any source service or worker.

Every individual result, source, location, failure reason, and lifecycle assertion is in `REMEDIATION_V3_PROBE_RESULTS.json` under `v3_adversarial`.

| Probe group | Result |
| --- | --- |
| Root and live envelopes: 48 cases per location for each of Early and Final | **192/192** |
| Conflicting root/live watchdogs: either location negative, both sources | **4/4** |
| Missing watchdog: both required sources | **2/2** |
| Healthy → unhealthy → gated recovery → fully healthy, historical evidence preserved: both sources | **2/2** |
| Prior 16-case false-health matrix with complete healthy controls | **16/16** |
| Total | **216/216** |

The 48 cases per location comprise: producer healthy, producer dead, producer stale, producer current exception, explicit healthy false, contradictory flags, healthy-but-dead, healthy-but-stale; seven malformed healthy values (`0`, `1`, strings `true`/`false`, null, list, object); fourteen malformed age/threshold cases including huge integer overflow; sixteen negative/malformed status/state cases; and null/list/empty watchdog objects. The healthy positive controls succeed; every negative case fails health and preserves the immutable observation.

The independently rerun prior false-health function itself was not edited. Only its healthy Early/Final baseline responses were supplied with the now-required actual producer watchdog object. Its fault injections and endpoint expectations were unchanged. The committed V3 probe also includes the same 16 scenario classes for future reproduction: outage, payload staleness, observation staleness, HTTP-200 explicit failure, membership failure, dead/stale recorder, write failure, low disk, disk-query failure, ledger corruption, anchor corruption, unresolved durability marker, missing/mismatched control, and contract disagreement. The prior script's SHA-256 and complete rerun results are recorded in the JSON report.

### V2 blocker regressions

Both original V2 blocker reproductions pass unchanged:

- **Durability:** final checkpoint directory-fsync failure for each of telemetry and membership. For each ledger, injection and two reopen/cycle checks occur in three distinct Python processes. All source/storage controls are otherwise healthy. `/health` remains 503, `/state.ok` remains false, the unresolved marker remains, and every synthetic ledger/anchor/marker digest remains unchanged across reopens. No ordinary cycle clears or adopts the failed append.
- **Redirects:** all 56 V2 cases pass, including malformed Location, Kalshi, Coinbase, HTTP, non-Railway, alternate Railway, and other blocked destinations. The complete first response remains captured, with exactly one GET and zero redirect hops. The prior independent verifier additionally passes all 80 redirect combinations across 301/302/303/307/308.

## Remaining limitations

- Kalshi freshness remains **INSUFFICIENT**; missing facts remain **UNKNOWN**.
- Coinbase freshness remains **INSUFFICIENT**; missing facts remain **UNKNOWN**.
- Sentinel cannot certify evidence. The permanent rule remains **Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence**; Sentinel's `certifiable_evidence` remains false even when its own operation is healthy.
- Healthy recording still requires an independently captured control-plane snapshot matching the frozen manifest. This task verified pinned frozen producer code; it did not refresh a live control-plane snapshot or authorize use of an old snapshot for a future window.
- Coordinated replacement or rollback of all local provenance requires an external trusted witness.
- Prior five-minute offline capacity results do not establish long-run capacity. No new soak or certification window was started. Full-ledger verification and complete response retention retain their existing cost limits.
- Existing POSIX durability/storage assumptions remain. Unresolved durability markers still require separately authorized, evidence-preserving recovery.

## Safety confirmation

Only the authorized branch and the seven Sentinel paths above were changed. Production main and `integrity/` remain unchanged. No merge, deployment, redeployment, Railway mutation, restart, service change, variable/configuration/volume/domain edit, production/frozen-service mutation, real-evidence change/reset, cutoff change, certification window, provider polling, strategy change/promotion, order, or trading action occurred. All networked service tests used synthetic source transports and loopback endpoints. The only remote write authorized for this task is the remediation commit pushed to the named Sentinel branch.

SENTINEL V1 REMEDIATION V3 PASSED — READY FOR THIRD INDEPENDENT READ-ONLY REVERIFICATION
