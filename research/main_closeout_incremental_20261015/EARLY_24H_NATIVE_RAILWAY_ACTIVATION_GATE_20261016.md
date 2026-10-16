# BTC15 existing EARLY 24-hour Railway capture/finish integration — 2026-10-16

**Status: NO-GO for starting authentic 24-hour capture yet. Synthetic capacity PASS already; do not rerun or build another validator.**

## Verified production architecture

- The existing source hooks are deployed in release `release/btc15-recorder-main-20261013` / `release/btc15-recorder-v81-20261013`. MAIN, V81, primary BRTI feed, and cockpit have latest successful deployments.
- `ops/live_recording/bootstrap.py` installs active capture only if `BTC15_RECORDING_ENABLED == "1"` and the configuration file exists, its hash matches, its role identities match, its reviewed release files pass attestation, and it owns a *new* campaign run directory.
- `ops/live_recording/policy.py` hard-binds authentic capture to production MAIN/V81 service IDs, volume IDs, build commits, and `/data`. The isolated Railway 64-GiB capacity service **cannot** act as an equivalent native capture producer just by running that module.
- Both MAIN and V81 expose the `BTC15_RECORDING_ENABLED`, `BTC15_RECORDING_CONFIG`, and `BTC15_RECORDING_CONFIG_SHA256` variable **names**. OAuth does not disclose values, so activation/actual configured run remains unknown.
- MAIN storage logs over 441 observations Oct 15-16 show the `btc15_recordings` tree unchanged at **12,123,786 bytes**; live MAIN processing continued. Thus there is **no observed advancing full-fidelity capture** in that period.
- The current three-role native reader requires MAIN, V81 and information capture, including original BTC/BRTI, Kalshi orderbook/proofs, EARLY lifecycle, SCALP, accepted native events and settlements.

## Existing finishing workflow

- `ops/live_recording/finish.py` already contains the private sealed-object transport and the **existing** independent verifier. It requires SSH access with an account-registered key, a pinned known_hosts file and a signed exact run configuration; no need to implement another validator.
- Its day-profile working-space reserve is **63,350,767,616 bytes = 59 GiB** (48-GiB reader DB + 3-GiB index + 6-GiB raw/archive/copies + 2-GiB reserve).
- The isolated capacity project's `early-probe-scratch` volume currently has **61,397,381,120 free bytes**, about **57.2 GiB**, so the existing 24-hour finisher refuses it by design.
- Original isolated Railway image lacked `ssh` client. This was corrected in **research-only** `Dockerfile.btc15-early-finish`, commit `5acde49c89ede3dcbc0f2753fcc125917cf970cc`: adds OpenSSH client and ReportLab while preserving pinned application requirements. Railway build **SUCCESS** at deployment `0a7e55a7-867c-40d1-bfc4-f46c1da7d98b`; runtime confirmed `ssh_client_available: true`, `original_finish_importable: true`, `existing_qualification_report_preserved: true`.
- This image makes the original finisher software available on Railway. It does **not** establish credentials, origin host-key trust, a read-only successful transfer, or sufficient free space.

## Exact remaining gates before a truthful live 24-hour GO
1. Keep historical `PF_20261013_4d0f8ed15e` capture immutable. Prepare a **new** `day` campaign ID and correct audited identities/manifest/config hashes for all three roles.
2. Resolve runtime capture activation status (the variable values are hidden from connected tools). Activation in MAIN/V81 requires carefully controlled production service redeploy/restart; do not silently change these frozen services.
3. Provide the existing finisher with authorized, authenticated read-only source access (registered SSH key and independently trusted host keys, or another reviewed secure mechanism); **do not bypass SSH host verification**. Establish full-seal to isolated volume transfer without Codespaces.
4. Increase isolated **reader** volume capacity so actual free bytes exceed 59 GiB reserve *plus working/growth margin*. Avoid overwriting or deleting original 600k evidence.
5. Use the existing bounded capture, runtime rate watch, stop/seal and reader. Check true source freshness and quote/contract identity, no source/proof drops, timing impact; stop on failure rather than silently counting incomplete contracts.
6. On complete authentic 24-hour evidence, evaluate EARLY's early low-price entries, timing, HOLD/WATCH/PROTECT/EXIT, missed opportunities and final settlements on the same 96+ contract cohort.

The existing 600,000-source-row test is **PASS for synthetic storage/index/reader**, not native capture authenticity, worst-case burst tolerance, or strategy performance.

## Production safety
No MAIN/V81/BRTI/cockpit deployments, restarts, staging commits or variable changes were made in this assessment. The production project's four previously staged MAIN-shadow changes remain untouched. No trading orders.
