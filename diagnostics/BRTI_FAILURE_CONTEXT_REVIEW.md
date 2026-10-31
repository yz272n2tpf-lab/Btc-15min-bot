# BRTI startup failure context — source-only review

## Scope and status

`brti_failure_context_review.patch` is a review artifact, not an installer or startup runner. It has NOT been applied on DigitalOcean. This review does not authorize or perform a new launch, reset, rearm, permit change, or production edit. Prior blocked installer and startup-capture operations are not included or reproduced here.

The live startup fault is still unknown. Successful component and isolated transport tests do not identify the original failure.

## Verified source basis

The preserved `kit/tools/brti_health.py` has SHA-256 `7c994fb5daacca0dff6a1982e9e90d94d85dfca9af3fb26633668fc5cace409d`, matching the prefix printed in the user's server audit. Its `wait_ready` function currently keeps only the most recent failed `check_once` exception, then raises the generic timeout with that exception as its cause. The controller prints only the outer error string after shutdown.

## Proposed change

Report failures from inside the actual readiness loop, before controller shutdown. Emit only allowlisted exception types, recognized validation codes, and file/line locations from seven known installed source paths. Do not emit exception messages, locals, credential values, response bodies, market prices, or endpoint addresses.

Deduplicate repeated details; cap output at eight distinct records, four exceptions per chain and four known file/line locations per exception. Protect the reporting operation so failure to print does not replace the original startup failure.

The original `check_once`, conflict propagation, quarantine condition, retry sleep, deadline condition and final timeout/cause are retained. No new provider requests, service changes, synthetic data, installer, manifest rewrite, controller invocation, or launch capability is added.

## Local verification performed in this session

Eight targeted tests passed after correcting duplicate-location handling in the reporting helper:

1. All pre-existing functions other than the reporting additions to `wait_ready` have identical abstract syntax trees.
2. Successful readiness returns the identical result object with no failure log.
3. Simulated failed readiness preserves the original timeout and exception cause.
4. An integrity quarantine still stops immediately with the original exception.
5. Failure of stderr output does not mask the original failure.
6. Arbitrary error messages and test credential strings are omitted.
7. Known file/line locations and exception chains are captured; cycles are bounded.
8. Repeated detail is deduplicated, and distinct output is capped.

These are local simulations of reporting behavior. They do not establish the cause of the DigitalOcean failure, verify actual server deployment, or demonstrate a working live bot.

## Fingerprints

- Original health source: `7c994fb5daacca0dff6a1982e9e90d94d85dfca9af3fb26633668fc5cace409d`
- Proposed source after this review patch: `47cd70bb33a6d4d39c3436e09db2b76e4a94a213cc41c7c5d1eb493c1c0814e0`
- Patch bytes: `7e7bc3e6ade8a6c492d2af9e94f8e8d3b281a7e1878d2f9fd14d07fc99979660`

## Unresolved deployment requirement

A permitted, reviewed release installation is still required. The installed release binds its source files through integrity manifests. Do not manually overwrite the health file, skip integrity checks, or treat this review upload as clearance for a previously blocked action. No verified permitted installation procedure is supplied by this document. No additional component tests are needed merely to demonstrate this reporting helper again.
