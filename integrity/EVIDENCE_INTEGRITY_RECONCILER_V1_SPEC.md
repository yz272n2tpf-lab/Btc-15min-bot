# BTC15 Evidence Integrity Reconciler V1

## Purpose

Deterministically classify every BTC 15-minute contract's **evidence quality** without modifying source data, strategy code, frozen controls, or production.

This tool implements the permanent project rule:

> **Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence.**

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
  "kalshi_sample_count": 169,
  "kalshi_has_start_observation": true,
  "kalshi_has_end_observation": true,
  "kalshi_max_observation_gap_sec": 5.0,
  "kalshi_coverage_complete": true,
  "brti_sample_count": 169,
  "brti_has_start_observation": true,
  "brti_has_end_observation": true,
  "brti_max_observation_gap_sec": 5.0,
  "brti_coverage_complete": true,
  "coinbase_sample_count": 169,
  "coinbase_has_start_observation": true,
  "coinbase_has_end_observation": true,
  "coinbase_max_observation_gap_sec": 5.0,
  "coinbase_coverage_complete": true,
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

## Verification hardening contract

- Both CLIs canonicalize the complete output set and all protected inputs before
  writing. They refuse input/output aliases, output/output aliases, existing
  output files (including hard links), and output symlinks. Files are created
  exclusively; there is no overwrite option. Use new derived-output filenames
  or a new bundle directory for each run.
- All age, gap, clock and rollover measurements must be finite and non-negative.
  Invalid explicit observations are recorded in `invalid_measurements`; a later
  healthy observation cannot erase them. Invalid policy thresholds are rejected.
- Each enabled feed requires its own coverage boolean, unique-timestamp sample
  count (at least two), start and end observations, and maximum observation gap.
  Adapter coverage also enforces contract clock continuity. The defaults require
  first coverage within 15 seconds, end coverage at 60 seconds left or later,
  and no observation gap above 10 seconds. No feed measurements means UNKNOWN;
  one sample or incomplete coverage means failure. Disabling an unused feed
  explicitly in the policy exempts its coverage requirement.
- Explicit parity failure dominates cumulative counts, including zero. Parity
  events outside the continuous-path sample set are still aggregated.
- BRTI counters are ordered by timestamp and checked at every adjacent pair.
  `brti_counter_metadata` preserves reset locations, sample counts and invalid
  measurements. A reset produces no normal delta and blocks certification.
- `brti_feed_clean`, `direct_brti_ready` and `coinbase_timeout` retain tri-state
  status. Absent diagnostics remain null; they do not assert health or replace
  required measured feed coverage. Explicit trouble for an enabled feed blocks
  certification even when measured ages are fresh.
- Certification uses the worst applicable inferred or recorded rollover lag,
  including exact-ticker and combined-first-seen records. Repeated summaries
  cannot lower it. Invalid recorded lag remains disqualifying.

Run all tests with `python -m unittest discover -s integrity -p 'test_*.py' -v`.
Run independent synthetic adversarial probes with
`python -m integrity.adversarial_hardening_v1`.
Neither command contacts Railway or uses real source evidence.

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
