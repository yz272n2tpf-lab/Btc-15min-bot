# BTC15 Stage 1 — Consolidated BRTI startup investigation (2026-10-29)

**Status: BLOCKED / NOT PRODUCTION-READY.** This is a non-deploying research and diagnostic record on a separate GitHub branch. No DigitalOcean, Railway, permit, model or order-execution changes are authorized by this document.

## Evidence from failed 9:30 PM EDT finite pilot

- 9:28:30 PM EDT original guarded controller started once, with child umask `0022`.
- Root-created `/run/btc15-pilot/session.json` became readable to the four intended service accounts. Prior 5 PM `0700/0600` permission failure was corrected in this run.
- BRTI owner and local TLS service started; controller returned `BRTI_STARTUP_FRESHNESS_TIMEOUT`, protected stop occurred; MAIN/V81 were **not** started.
- The post-failure read-only host audit reported NTP synchronized; selected certificates valid for 2 hours; source syntax checks passed; 1 BRTI feed startup; no 60-second heartbeats; no explicit refusal messages or HTTP 429 messages in that short journal window. **Zero 429 log matches is not proof that zero 429 HTTP responses happened.**
- Owner-start marker `/run/btc15-pilot-brti/owner-started.json` exists. BRTI service has `RuntimeDirectoryPreserve=yes` and the owner uses `O_EXCL` to refuse same-path reuse. This is a potential **next-run rearm blocker**, not the root cause of the already-started 9:30 run. Preserve/archive evidence under fresh authorization; do not unlink it casually.

## New data-freshness mismatch: strong hypothesis, NOT established live cause

The currently preserved DigitalOcean owner service configuration sets `BRTI_SHARED_MAX_QUAL_AGE_S=1.35`, polls approximately once per second, and reads Kalshi's CF Benchmarks `/values` endpoint at `PER_SECOND` resolution. The original controller permits only about **10 seconds** for qualified BRTI health; the poller's normal detailed heartbeat is delayed **60 seconds**.

Five older snapshots in the saved `BTC15_Next_Launch_Packet_20261028.zip` were marked qualified with a **5000 ms** age bound; their observed ages were:

| Preserved sample | Age (ms) | Older 5000 ms bound | Current 1350 ms bound |
|---|---:|---|---|
| cached_feed_20261028T193237Z | 1750.1 | Pass | **Fail** |
| cached_feed_20261028T193433Z | 2168.6 | Pass | **Fail** |
| cached_feed_before_1623 | 1868.8 | Pass | **Fail** |
| cached_feed_before_1808 | 2299.1 | Pass | **Fail** |
| cached_feed_before_1845_handoff | 2384.5 | Pass | **Fail** |

**Reproduced offline using the original BRTI poller:** For each age, a synthetic successful upstream response produces `status=PRIMARY_OK`, `upstream_ok=1`, but `clean_for_qualification=False` at 1.35 s. At 5.0 s the same sample qualifies. No credentials, upstream requests or orders were used in this reproduction.

**Limits:** The older snapshots came from another historical feed configuration, and 5 non-random observations do not measure the DigitalOcean feed's latency distribution. The 9:30 run could instead have failed due to HTTP authentication, response parsing, transport readiness, rate limiting, or other causes. The host audit could not distinguish these because the service had already stopped and the first detailed heartbeat is scheduled after the controller's 10-second wait.

## Safe consolidated repair path

1. **Observe without weakening qualification:** Prepare a candidate that produces a bounded first-10-second internal status: poll attempts/successes, last error *class* (not secrets/URLs), last source age, qualification reason, and local HTTPS reachability. Preserve Kalshi timestamps and every no-orders/anti-duplicate gate. Test all error branches offline. Do not change production without a reviewed release manifest and hashes.
2. **Validate freshness feasibility:** Compare actual DigitalOcean source timestamps and receive times under explicit authorization, then assess whether 1.35 s can be met while preserving entry/final-outcome integrity. Do not simply widen to 5 s or substitute another source, especially for final settlement probability.
3. **Safe rearm:** On fresh approval, archive prior consumed receipt, closed session, and preserved BRTI runtime marker with verifiable fingerprints. No deletion or permit reuse. Check cold-service and duplicate-owner gates before any start.
4. **One coordinated acceptance:** Only after offline tests and release review, perform one finite, separately authorized validation and report: owner count=1; qualified BRTI freshness; TLS; MAIN; V81; FINAL/EARLY/SCALP publications; durable journals/scoring; zero orders; automatic hard stop.

## Required status before proceeding

- [x] 5 PM permission cause fixed and shown readable in 9:30 pilot
- [x] Read-only host check executed
- [x] Historic freshness mismatch reproduced offline
- [ ] True 9:30 BRTI upstream error class / source-age distribution identified
- [ ] First-10-second bounded diagnostic and all failure branches validated offline
- [ ] Safe rearm review with preserved runtime owner marker
- [ ] One freshly authorized finite live acceptance passed
- [ ] Stage 2 and Stage 3 tests passed

**Rule:** HOLD. No repeat live launch, no Railway restart, no default-branch merge, no order placement, and no 24/7 production activation until the corresponding acceptance gate passes.

## Offline candidate prepared (not installed)

The separate review-only patch `diagnostics/brti_health_observe_offline_candidate.patch` adds a **single bounded local HTTPS /state diagnostic on failed startup**. It logs only allowlisted health status, age, and attempt/error counters; never credential contents, price, raw JSON, or external requests. Original `BRTI_STARTUP_FRESHNESS_TIMEOUT`, 10-second qualification deadline, no-orders protections, and freshness threshold remain unchanged.

- Baseline source regression suite: **11/11 passed offline**.
- Candidate no-network regression tests (HTTP 429 class, stale-but-upstream-OK status, no secret strings, non-root refusal, timeout preservation, no upstream/orders): **6/6 passed offline**.
- Preserved five age fixtures replayed through the original poller: **0/5 qualify at 1.35s; 5/5 qualify at 5.0s** despite synthetic upstream success. This does not establish live Kalshi latency.
- Exact original health source SHA256 begins `7c994fb5daacca0d`; the proposed changed source SHA256 begins `9846b32695528086`. **Do not install it by overwriting the release file:** a fresh manifest, host checks, review and explicit separate authorization are required.
