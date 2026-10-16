# BTC15 EARLY — after-100GB-resize readiness receipt (2026-10-16)

**Decision:** FINISHER SOFTWARE/STORAGE PREPARED; **NO-GO to start 24h authentic EARLY capture** until secure evidence transfer and native producer activation are proven.

## Verified directly in isolated Railway service
- Project `btc15-early-capacity-test`, project ID `87ad03d5-e1d6-47d6-b1ea-159cd7594686`, environment `test`.
- Existing capacity probe service `existing-reader-capacity-probe` with research-only Dockerfile `Dockerfile.btc15-early-finish`. No new validator or collector.
- Mounted volume `early-probe-scratch`: **100,000 MB**, mount `/research-evidence`.
- Runtime readiness deployment `b8b33b67-ea12-43f4-a2a5-da9333e45804` (SUCCESS) printed:
  - free_bytes: **95,312,441,344** (approx. 88.8 GiB).
  - reserve_required_bytes: **63,350,767,616** (59 GiB).
  - Extra above reserve: **31,961,673,728 bytes** (approx. 29.8 GiB).
  - `storage_reserve_pass=true`, `ssh_client_available=true`, `original_finish_importable=true`, `existing_qualification_report_preserved=true`, `validator_rerun=false`, `production_access_attempted=false`.
- Previous synthetic capacity qualification report confirmed 600,000 inputs, 600,004 protocol-inclusive envelopes independently read, 66/66 partitions, `issue_counts={}`. Do not repeat.

## Transport prerequisites, not yet met
- Original `ops/live_recording/finish.py` authenticates SSH via a private `ssh_key` path and an independently pinned `known_hosts` file, plus explicit reviewed run configuration with two production SSH targets and matching campaign identities. Merely having `ssh` installed is **not** an authenticated successful transfer.
- The isolated Railway service currently exposes only Railway platform variable names; no campaign configuration, private-key/host-key path setup is in its declared service variables. Dockerfile only adds SSH client and reporting software. This review **did not** probe production SSH, inspect or expose key material, or retrieve authentic captures.
- Railway documentation (`https://docs.railway.com/cli/ssh`) requires registering an SSH public key with Railway; no SSH key registration action is offered by the connected Railway integration.
- The existing finisher's SSH `finish` operation actually *requests recorder sealing/stopping*. It must NOT be invoked as an initial read-only connectivity test.

## Native capture status
- MAIN/V81 live releases contain optional `ops.live_recording.bootstrap.start` capture hooks, gated by `BTC15_RECORDING_ENABLED == '1'` and strict campaign/config/manifest/build/deployment checks. The connected Railway OAuth integration only shows variable names, not their values.
- MAIN storage inventory repeatedly reports `btc15_recordings` **12,123,786 bytes unchanged** over 441 five-minute logs across Oct 15–16. MAIN continues serving contracts. Thus advancing full-fidelity live recording is **not** demonstrated.
- Authentic capture is hard-bound to existing MAIN/V81 production service and volume IDs. The isolated Railway test service cannot replace native capture by itself. A controlled production change/restart would be required to enable a new 24h campaign if currently off; this has **not** been authorized or performed in this pass.
- The main project's pre-existing four pending staged changes remain untouched.

## Remaining work (not another validator)
1. Provision a **reviewed and auditable read-only authentication/transfer path** from sealed native producer evidence to the existing isolated Railway finisher. Validate SSH key registration, pinned host fingerprint and a non-mutating bounded identity check before any 24h capture.
2. Prepare an explicit one-campaign `day` configuration with correct MAIN/V81/information role identities, deployment hashes, distinct run ID and 24h stop/seal parameters. No loosening of freshness or capture checks.
3. Review and separately authorize controlled MAIN/V81 recorder activation, including backup/restart rollback and source/clock comparison; do not apply production pending patch.
4. On successful authentic capture activation and verified 24h storage throughput, run 24h and finish with the **existing** reader on Railway. Compare EARLY entries, 25–35c value, publication timing, opportunity coverage, HOLD/WATCH/PROTECT/EXIT and final settlements.
5. Fail closed on missing quote/source/receipt or dropped evidence; PASS only complete true-source scope.

**No changes** to production services, production variables, journals, models, signal thresholds or orders. Only isolated test service Docker image/readiness checks and this research document were prepared.
