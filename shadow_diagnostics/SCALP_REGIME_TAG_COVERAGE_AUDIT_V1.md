# BTC15 Regime Tag Coverage / Feature Audit V1

**Mode:** CAUSAL FEATURE DIAGNOSTIC / DESCRIPTIVE ONLY / NO ORDERS / NO AUTO-PROMOTION

## Question

Why did Market-Regime Ledger V1 assign almost all serial opportunities to `CHOP_LOW_CONVICTION` or `OTHER`, with little/no primary `TREND_ALIGNED`, `KALSHI_LAG`, `ACCELERATION_BURST`, or `REVERSAL_HAZARD`?

## Causal firewall

The audit record uses an explicit allow-list containing only identifiers and candidate-time features:

- structure / BTC-BRTI agreement flags
- candidate-time against-side / dual-reversal flags
- BTC 5s/15s normalized momentum
- acceleration
- Kalshi 15s ask movement
- BTC/BRTI 5s/15s side-aligned movements
- BRTI primary-health flag

The audit record does **not** contain:

- +5/+10/+20 labels
- MFE/MAE
- protected exit gain
- settlement/result
- executable future path gain
- current future bid/ask rows
- private `_candidate` or `_paths` objects

## Reports

For all serial opportunities and for validation/holdout separately:

- feature availability and missingness
- numeric min / P10 / P25 / median / P75 / P90 / max / mean
- boolean true/false rates
- independent condition pass rates
- sequential TREND, KALSHI_LAG and ACCELERATION funnels
- multi-reason blocker counts
- candidate-time reversal-evidence rate
- overlapping and primary tag counts

## Interpretation rule

This audit may identify:

- a schema/alias problem
- an unavailable feature
- a semantic mismatch
- a condition that almost never occurs
- a threshold that is far outside the actual feature scale

It may **not** use outcome performance to choose a replacement threshold or label.

If a Regime V2 is built, its definitions must be based on causal feature semantics/distributions and frozen before a new prospective test. V1 validation/holdout outcomes cannot become a tuning set for V2.

## Safety

- no signal suppression
- no signal rescue
- no threshold selection
- no automatic promotion
- no production writes
- no orders
- Coverage Rescue V1 and Economics Forward V1 remain frozen and independent
