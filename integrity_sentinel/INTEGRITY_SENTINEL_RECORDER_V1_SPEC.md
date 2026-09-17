# BTC15 Integrity Sentinel / Prospective Evidence Recorder V1

## Purpose

Prevent a repeat of the September 15–17 forensic problem: a test may run and produce useful research artifacts while the historical logs are too sparse to prove that the resulting sample is certification-grade.

This recorder is **not trading logic**. It does not select signals, score a strategy, promote a lane, or place orders. Its only job is to create enough prospective, timestamped evidence that every future 15-minute contract can be judged by the hardened rule:

> **Operational Health PASS + Evidence Integrity PASS + CLEAN = certifiable evidence.**

## Design conclusions from the 169-contract reconciliation

The historical audit produced 169/169 full-system contracts quarantined. The main instrumentation gaps were not strategy outcomes; they were inability to prove dense per-feed coverage and historical operational/configuration/cutoff facts. Shared-BRTI heartbeat logging was approximately one minute, while the hardened default requires observation gaps <=10 seconds. Exact membership IDs were also missing from historical captures for Early, V1 experiment controls, and Nextgen V2 even though several live state endpoints retain those records.

V1 therefore records at a default 5-second cadence and separately captures immutable exact-ID membership records.

## Safety architecture

1. Standalone isolated service/branch first. No production/frozen service is modified by this branch.
2. GET-only reads of existing `*.up.railway.app` state endpoints.
3. Configuration rejects direct Kalshi, Coinbase, or other non-Railway hosts.
4. Reading the shared BRTI `/state` endpoint does **not** trigger an upstream request; `brti_shared_feed_v1.py` explicitly serves `poller.snapshot()`.
5. No order endpoints and no non-GET methods.
6. Raw source JSON is retained by value, plus a SHA-256 and conservative normalized facts. Missing fields remain missing.
7. Sentinel-owned JSONL ledgers are append-only and hash chained. Existing records are verified on startup. The runtime never truncates or rewrites.
8. Strategy membership is copied only from already-recorded membership containers. No membership is inferred from price/performance and no signal is rescored.

## Ledgers

### `telemetry.jsonl`

At every high-frequency cycle, each source yields either `SOURCE_SAMPLE` or `SOURCE_ERROR`, including wall-clock observation time, cycle ID, source name, canonical contract when known, HTTP status/latency, full JSON payload and payload SHA-256, and conservative normalized evidence facts.

The initial telemetry sources are production main dashboard state, shared BRTI `/state`, and generalized scalp combined state. The raw payload is retained specifically so a later extractor improvement can recover a fact without changing the original sample.

### `membership.jsonl`

Exact-ID immutable membership events are copied from Early `/state` call/settlement records, Final `/state` lock/settlement records, combined scorecard state where exact records are present, and Nextgen V2 `/audit` audit records.

Records are deduplicated by SHA-256 of source + container + exact contract ID + original record. On restart, prior membership IDs are recovered from the ledger.

## What V1 solves now

- dense prospective BRTI state/counter recording;
- source-response failures as first-class evidence;
- canonical contract/timer snapshots;
- exact Early/Final/Combined/Nextgen membership where exposed;
- append-only provenance instead of relying on sparse Railway console logs;
- no extra direct market-provider request pressure from the Sentinel.

## What still must be proven before deployment/certification

V1 deliberately does **not** pretend that the current source endpoints expose every required fact. Before any new certification clock starts:

1. Verify the production main payload exposes enough Kalshi freshness/age facts; if not, add a separately tested read-only telemetry surface at the source rather than infer health.
2. Establish a prospective Coinbase freshness source for every component that actually depends on Coinbase, preferably by exposing state from an existing poller rather than adding another external poller.
3. Confirm every GET endpoint is side-effect-free and does not cause upstream market requests. Shared BRTI is already verified in source; the remaining endpoints require the same review.
4. Create a frozen control-plane attestation containing actual service IDs, deployment IDs, branch/SHA, start commands, expected versions, cutoffs and volume identities before the window begins; verify it again after the window.
5. Monitor disk usage so Sentinel storage itself cannot recreate the prior `ENOSPC` failure class.
6. Wire the Sentinel ledger into the hardened reconciler and prove synthetic clean, stale, missing-feed, restart/config-drift and disk-failure cases.
7. Run an isolated shadow soak before trusting any Sentinel-produced CLEAN label.

No existing evidence window is reset or promoted by this design.
