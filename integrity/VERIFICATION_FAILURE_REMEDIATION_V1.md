# Evidence Integrity Verification Failure Remediation V1

Status: REQUIRED HARDENING BEFORE ANY DEPLOYMENT OR REAL EVIDENCE RECONCILIATION

Branch: `evidence-integrity-reconciler-v1`

This document records the independent read-only verification findings against head `a186c5f41a5c638f1a5893c138082aee85bf7528` and defines the minimum fixes required before the integrity pipeline may be used for certification decisions.

## Non-negotiable safety envelope

- No production changes.
- No Railway changes or redeployments.
- No trading or order placement.
- No automatic promotion.
- No mutation, deletion, reset, or silent overwrite of source evidence.
- Missing/invalid facts must never default to healthy.
- Certification remains: `Operational Health PASS + Evidence Integrity PASS + CLEAN classification`.

## Required fixes

### 1. Prevent source-evidence overwrite through CLI output paths

Before any write, canonicalize all input and output paths.

Reconciler:
- Reject `--output` or `--summary` when either resolves to `--input` or `--policy`.
- Reject `--output` and `--summary` when they resolve to each other.
- Prefer fail-closed behavior when a derived output already exists unless an explicit safe overwrite option is intentionally added for derived outputs only.

Bundle builder:
- Compute every generated target path before writing.
- Reject when any target path resolves to any `--log`, `--operational-manifest`, or `--policy` input.
- Source inputs must be protected even if they live inside `--out-dir` and have a generated filename such as `assessments.jsonl`.

Regression tests must reproduce the exact overlap cases and prove zero source mutation.

### 2. Reject invalid numeric integrity measurements

All age/gap/rollover metrics used for certification must be finite and non-negative.

`NaN`, positive/negative infinity, negative ages, negative source gaps, and negative rollover lag must never produce CLEAN.

Invalid explicit numeric measurements should fail closed as UNKNOWN or INVALID_FOR_CERT; they must not be interpreted as small/good values.

### 3. Require per-feed coverage, not one isolated fresh sample

A required feed cannot be certified from one fresh measurement inside an otherwise long contract window.

For each enabled required feed (Kalshi, BRTI, Coinbase), aggregate enough information to prove interval coverage, including at minimum:
- sample count,
- start-side coverage,
- end-side coverage,
- maximum feed-specific observation gap.

Expose a tri-state per-feed coverage result. Reconciler must require complete coverage for every enabled feed. One Coinbase measurement in a 169-observation contract must not certify.

### 4. Parity failure must be monotonic negative evidence

If any explicit `parity_ok=False` observation exists, aggregate parity failures must be at least 1 regardless of a zero cumulative counter.

When both cumulative counters and explicit PASS/FAIL events exist, combine them conservatively so explicit failure can never be masked.

### 5. Detect any intermediate counter reset

BRTI cumulative counters must be checked pairwise in timestamp order.

Any decrease between adjacent points is a reset, even if the final counter later exceeds the first counter. Expose reset metadata and fail certification for the affected interval (or otherwise make it non-CLEAN fail-closed).

The reproduced `1000 -> 1 -> 1840` sequence must not yield a normal delta or CLEAN classification.

### 6. Preserve explicit feed-trouble flags through aggregation

`brti_clean=False` is hard negative evidence and must survive log parsing, observation normalization, contract aggregation, and reconciliation.

At minimum aggregate `brti_feed_clean` tri-state and make explicit False invalidate BRTI evidence. Do not let a fresh numeric age override explicit unclean status.

Equivalent explicit negative status flags that are already captured (for example direct-BRTI readiness or Coinbase timeout evidence) should remain fail-closed rather than being silently dropped.

### 7. Enforce recorded rollover lag downstream

Do not replace an explicit recorded rollover lag with a smaller lag inferred from a later synthetic/attached observation.

Aggregate rollover integrity conservatively from all supported evidence, including recorded `exact_ticker_rollover_quote_lag_sec` and applicable `combined_first_seen_lag_sec` plus any derived first-seen lag.

The certification field must use the conservative worst known applicable lag. A recorded 35.7-second exact-ticker quote lag must not become a 1-second aggregate lag or CLEAN classification.

## Mandatory regression acceptance

Add dedicated tests for every finding above. The next verification must include both the existing 34 tests and the new hardening tests.

Acceptance requires:

1. Every Python file under `integrity/` compiles.
2. All integrity tests pass.
3. Independent adversarial probes for the seven cases above no longer produce CLEAN or source mutation.
4. Branch continues to differ from `main` only under `integrity/`.
5. No network mutation, order code, production mutation, or automatic promotion is introduced.
6. No Railway action is performed.
7. Dual-gate truth table still passes for PASS/FAIL/UNKNOWN combinations.

Until all acceptance conditions pass, this branch is development tooling only and must not be used to certify historical or future contracts.
