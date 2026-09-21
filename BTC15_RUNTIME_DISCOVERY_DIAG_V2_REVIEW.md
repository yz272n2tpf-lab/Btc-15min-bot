# Runtime discovery diagnostic binding V2 — review only

Status: NOT DEPLOYED. Production strategy and deployed files unchanged by this branch.

## Established defect

Pinned production commit: `191fa114b9910b4a02c8ed201a29fd3d41d4e268`.
Main source Git blob: `5893985d7f4f442ef48f64e38f9da92bc171dd76`.

The main Python file defines `kalshi_get` twice. The first definition (near line 143) contains `MARKET_LIST_RESPONSE` instrumentation. The last definition (near line 2002) has no instrumentation and replaces that binding before the continuous loop calls `get_active_market`. This is an established measurement defect, NOT the established cause of the production rollover delay.

## Proposed narrow correction

Add the passive V2 helper, then use the hash-guarded patch script ONLY in an isolated checkout. It replaces only the final top-level `kalshi_get` function. It preserves the request URL, method, signed headers, params object, timeout, one-request count, status-before-JSON order, returned data identity, and original exception object. Every diagnostic call is isolated from production failures.

No discovery, selection, polling, retry, quote, target, BTC, BRTI, EARLY, FINAL, SCALP, or position-manager rules are changed. No extra HTTP request is added.

Events: request start, response receipt, decoded expected-opening ticker presence, categorized request failure. HTTP receipt is captured before status checking/JSON parsing. Cache headers are allowlisted and bounded. No request/auth headers, raw payloads, outcome labels, or prices are logged. Malformed metadata gives UNKNOWN, not false absence.

A bounded queue separates stdout from the producer. Full/contended queue drops diagnostic events; an event-loss counter is included in later events. Lost diagnostics invalidate completeness claims, never justify bypassing source safety. The helper cannot guarantee zero CPU or scheduling overhead; live qualification must measure that separately.

Request start is function-entry observation and includes subsequent argument construction/signing. It is not an outbound network packet timestamp. Decoded ticker presence establishes what this exact response contained, not when an external exchange first made the ticker or a complete quote book available.

## Review-only validation

Local synthetic/extracted-function tests: 29 passed, 0 failed; 1 full-source test skipped because the local container has no repository checkout. The GitHub validation workflow must run all 30 tests with the actual pinned source, apply the patch in its disposable checkout, then run the existing diagnostic, quote-provenance, parity regressions and dashboard static gate. Do not label a queued/unrun workflow as passed.

The workflow has read-only repository permissions. No deployment, main-branch update, service restart, environment change, strategy scoring, or clean-sample access is part of validation. The branch contains a patch proposal; the deployed main source remains unpatched.

## Before any later deployment

Require successful full-source tests, unchanged-source verification, review of residual instrumentation overhead and trace completeness, and exact current production SHA recheck. Archive current EARLY diagnostic run metadata first. Record any production restart interval because a read-only downstream collector may still see a source interruption even when its own deployment is untouched. Do not retrospectively recategorize missed contracts as fully observed.

Deployment qualification must show V2 discovery events from the actual continuous loop, correlate those events with selection/subscription/quote-consumption events, and preserve source/quote/target safety checks. Existing SOURCE_SNAPSHOT_WRITTEN is a source-file write, not proof of dashboard publication. Existing BOTH_SIDES_READY is not by itself proof of timestamped executable quotes; use TIMESTAMPED_BOOK_USABLE and consumption evidence separately.

Root cause of late discovery/cache behavior remains unresolved pending actual runtime request/response records. No performance or profitability claim. SIGNAL ONLY / NO ORDERS.
