# BTC15 Evidence Integrity Reconciler V1

## Purpose

Deterministically classify every BTC 15-minute contract's **evidence quality** without modifying source data, strategy code, frozen controls, or production.

This tool implements the permanent project rule:

> **Operational Health PASS + Evidence Integrity PASS = valid evidence.**

A Railway `SUCCESS` status, a live process, or growing sample counts are never sufficient on their own.

## Safety

- Read-only analysis.
- No orders.
- No production changes.
- No automatic promotion.
- No deletion or rewriting of source observations.
- Original input records are preserved verbatim inside every assessment.
- Any contract that is not unequivocally clean is quarantined from certification.

## Contract classifications

### `CLEAN`
Both mandatory gates pass and no warning-level degradation is present.

Only `CLEAN` contracts are certifiable.

### `PARTIAL`
Both hard gates pass, but a warning-level issue exists (for example an elevated BRTI 429 share while freshness remained within the configured limit).

`PARTIAL` evidence is preserved for research but not certification.

### `INVALID_FOR_CERT`
At least one known hard requirement failed. Examples:
- stale BRTI/Kalshi/Coinbase data beyond the policy threshold;
- storage unavailable;
- collector/scorer not advancing;
- runtime/config mismatch;
- invalid prospective cutoff;
- missing start/end observation;
- incomplete continuous path;
- excessive source gap;
- late rollover;
- parity failure under a strict policy.

### `UNKNOWN`
At least one required measurement is missing and no known hard failure has already been established.

Unknown is never silently treated as clean.

## V1 policy defaults

Conservative defaults:
- Kalshi maximum age: 5 seconds
- BRTI maximum age: 5 seconds
- Coinbase maximum age: 5 seconds
- maximum source gap: 10 seconds
- maximum rollover lag: 15 seconds
- BRTI 429 warning share: 5%
- any parity failure is a hard certification failure

These are **reconciliation policy defaults**, not strategy parameters. They can be overridden in an explicit JSON policy file for a specific evidence family without changing strategy logic.

## Input contract record

One JSON object per line. Required fields depend on the configured policy.

Example:

```json
{
  "contract_id": "KXBTC15M-26SEP162315-15",
  "service_deployment_ok": true,
  "process_alive": true,
  "storage_ok": true,
  "collector_advancing": true,
  "scorer_advancing": true,
  "runtime_config_match": true,
  "cutoff_valid": true,
  "has_start_observation": true,
  "has_end_observation": true,
  "continuous_path_complete": true,
  "kalshi_max_age_sec": 1.4,
  "brti_max_age_sec": 2.1,
  "coinbase_max_age_sec": 1.1,
  "max_source_gap_sec": 4.0,
  "rollover_lag_sec": 4.9,
  "parity_fail_count": 0,
  "brti_attempts": 1000,
  "brti_429_count": 10
}
```

## Output

For every contract:
- classification;
- Operational Health result;
- Evidence Integrity result;
- certification eligibility;
- quarantine flag;
- machine-readable reasons and warnings;
- untouched original input.

The summary contains counts by classification and explicitly records the dual-gate rule.

## Next wiring step

V1 is the deterministic core. It should next receive a **read-only adapter** that reconstructs these fields from the current BTC project sources:

1. production/root market observations;
2. BRTI shared-feed health;
3. Coinbase warnings;
4. rollover probe records;
5. Early / Final / combined / scalp collector observations;
6. deployment/config identity and storage health;
7. accepted prospective cutoffs.

The adapter must never guess a missing measurement. Missing facts become `UNKNOWN`.

Only after the adapter is verified against known incident windows should the reconciler be used to decide which historical contracts are eligible for evaluation.
