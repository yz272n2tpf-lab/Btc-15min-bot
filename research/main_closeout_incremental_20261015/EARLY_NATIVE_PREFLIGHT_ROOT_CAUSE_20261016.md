# BTC15 EARLY authentic recording — verified October 13 failure causes (2026-10-16)

**Decision: NO-GO to activate 24-hour native EARLY campaign until the recorder's existing loss/capture stops are corrected.** Do not confuse this with the isolated 600k synthetic reader/capacity qualification, which PASSED.

## Verified authenticated read-only connection, same morning

- SSH `ssh.railway.com`: first-contact ED25519 key pinned with owner approval. Fingerprint `SHA256:+S1xg92FrnHz6pY3bpkmh1OGtWQGNANXilPzlxA7B1g` (TOFU, not independently published vendor fingerprint).
- Isolated 100,000 MB `early-probe-scratch` volume; server key and private SSH credential remain there.
- MAIN and V81 each matched six non-secret exact Railway deployment identity fields over authenticated SSH.
- A single October 13 native `identity.json` file from each role was copied into isolated Railway, compared with its remote SHA-256; both transfers PASS (MAIN: 1,321 bytes, `690a01e658287b567fc5ef52969293edbaf4ff9b311791e89e02b4c8edeacb7e`; V81: 1,327 bytes, `2b1e1180317f192dad34d6ae168675069563db57526601f6e18cfface8892221`). No full dataset transferred; no Codespaces use, MAIN/V81 writes, or recorder stop.
- Both native source containers currently have `BTC15_RECORDING_ENABLED == "1"`, and their configuration hashes validated; both are pinned to preflight `PF_20261013_4d0f8ed15e`, profile `preflight`, duration 1,200 seconds. The old preflight campaign is completed/failed, not advancing into a 24-hour capture.

## October 13 preflight: preserved terminal/health/queue evidence

### MAIN capture
- Health snapshot elapsed **35.16 s**: `losses={"OVERSIZE": 1}`, `queued_bytes=3,051,852`, `peak_queued_bytes=4,105,048`, max hook 0.695 ms, `archive_failed=false`.
- Terminal elapsed **40.51 s**: `failure="DRAIN_TIMEOUT"`, `reason="LATE_INCOMPLETE_SEAL"`, `status="INCOMPLETE"`, `records=2,942`, `queued_bytes=0`, losses include `OVERSIZE=1` and `CLOSED=1`.
- `seal.json` exists but is explicitly **INCOMPLETE**.
- The first loss was an oversize event; later drain/terminal handling did not recover a qualified capture.

### V81 capture
- Health snapshot elapsed **10.13 s**: `losses={"QUEUE_BYTES": 1466}`, peak queued **33,554,430 bytes** against **33,554,432-byte** limit, current queue **33,552,298 bytes**, 3,530 records, `archive_failed=false`, hook over-1ms 8/19,022.
- Terminal snapshot elapsed **15.13 s**: `failure="DRAIN_TIMEOUT"`, **1,470** queue-byte losses, ~**30,106,258** bytes still queued, 5,904 records, `stopped=false`; `seal.json` **missing**.
- Root problem is live producer volume outpacing the off-path bounded writer, not merely insufficient final reader disk or a short shutdown timeout.

### Information capture
- Ran the full **1,200 s** preflight with terminal status **SEALED**, `losses={}`, `archive_failed=false`, `queued_bytes=0`, 4,492 records; its `seal.json` exists and is SEALED.

## Causal software path, source review
- `ops/live_recording/capture.py` Gate.watch treats *any* queued evidence loss as `RECORDER_LOSS_OR_FAILURE` and stops capture; it calls `stop(..., timeout=5)` and reports `DRAIN_TIMEOUT` if off-path writer cannot finish in 5 seconds.
- `btc15_quote_proof_offpath_v1.py` caps the recorder's queue at 32 MiB, counts `QUEUE_BYTES` / `OVERSIZE` losses and flushes immutable records via the existing journal.
- Increasing only disk storage or only the five-second shutdown timeout **does not repair** lost MAIN observations or dropped V81 input.
- `ops/live_recording/reader.py` requires **all three role seals SEALED** and exact native/provenance associations. Missing V81 seal / MAIN incomplete seal is a definitive fail.

## Narrow engineering next step (no new EARLY model/validator)
1. Determine the size/record kind of the MAIN oversize observation (without changing native source or weakening provenance/oversize guard).
2. Bound and optimize the existing V81 source-observation enqueue/serialization/write path so it can keep up with the original quote/input rate without dropping or synthesizing evidence; merely raising the queue cap can hide but not eliminate the rate mismatch.
3. Make the existing recorder's stop/flush/seal protocol durable under the observed backlog, preserving the original failure reason; prove zero loss and all three SEALED in the existing native preflight before a 24-hour campaign.
4. Only after that, prepare a new `day` campaign config with exact source build and deployment identities and a controlled, explicit production restart/rollover plan. Authentic 24h still not started.
5. Use already-qualified isolated Railway reader and verified SSH transport; no further 600k synthetic capacity test.

**Production MAIN/V81/BRTI/cockpit were not changed, deployed, restarted or asked to stop.** The production project's pending changes remain staged/unapplied. Strict signal-only/NO ORDERS.
