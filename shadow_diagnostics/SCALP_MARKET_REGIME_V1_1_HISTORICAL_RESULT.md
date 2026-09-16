# BTC15 Market-Regime Ledger V1.1 — Corrected Historical Result Freeze

**Mode:** DESCRIPTIVE SEMANTIC REPAIR / SHADOW ONLY / NO THRESHOLD SELECTION / NO ORDERS  
**Source SHA-256:** `8a61c833ff850bd97f7c31cd157606df3edea4f493bb14598086e090ca7a2ddb`  
**Source rows:** `311376`  
**Source bytes:** `197800559`

V1.1 corrects only numeric boolean interpretation (`1.0/0.0`). All regime thresholds, features, tag priority, serial lifecycle, chronological split and economics accounting are unchanged from V1. V1 remains preserved as the bug-discovery result.

The holdout had already been observed before this representation bug was found. Therefore all V1.1 holdout results below are descriptive only and cannot select or promote a regime-aware signal rule.

## Overall totals — unchanged by the semantic repair

### Validation
- Signals: 93
- +10 touch rate: 70.97%
- Protected exits: 52 / 93 = 55.91%
- 10-lot taker/taker average net: +4.75c per contract
- 10-lot taker/taker median net: +3.20c
- 10-lot taker/taker positive-net rate: 61.54%

### Holdout
- Signals: 96
- +10 touch rate: 57.29%
- Protected exits: 55 / 96 = 57.29%
- 10-lot taker/taker average net: +0.67c per contract
- 10-lot taker/taker median net: -0.70c
- 10-lot taker/taker positive-net rate: 38.18%

## Corrected primary regime distribution

### Validation (93 signals)
- `KALSHI_LAG`: 35
- `OTHER`: 54
- `ACCELERATION_BURST`: 3
- `TREND_ALIGNED`: 1

### Holdout (96 signals)
- `KALSHI_LAG`: 38
- `OTHER`: 54
- `ACCELERATION_BURST`: 2
- `TREND_ALIGNED`: 2

`REVERSAL_HAZARD` and `CHOP_LOW_CONVICTION` did not appear as primary labels in these two windows after the semantic repair; this is diagnostic evidence only and is investigated separately by the causal blocker audit.

## KALSHI_LAG — corrected descriptive performance

### Validation
- Signals: 35
- +10 touch rate: 74.29%
- Protected-exit rate: 62.86%
- Average entry ask: 52.39c
- <=50c entry rate: 48.57%
- 10-lot taker/taker average net: +3.36c
- 10-lot taker/taker median net: +1.35c
- 10-lot taker/taker positive-net rate: 63.64%

### Holdout
- Signals: 38
- +10 touch rate: 68.42%
- Protected-exit rate: 55.26%
- Average entry ask: 42.22c
- <=50c entry rate: 68.42%
- 10-lot taker/taker average net: +2.07c
- 10-lot taker/taker median net: -0.30c
- 10-lot taker/taker positive-net rate: 42.86%

### Validation -> holdout shift
- +10: -5.86 percentage points
- Protected-exit rate: -7.59 points
- 10-lot average net: -1.29c

The average remained positive, but the holdout median and positive-net rate did not meet the separate forward economics break-even standard. This is not promotion evidence.

## OTHER — corrected descriptive shift

### Validation
- Signals: 54
- +10: 66.67%
- 10-lot average net: +4.14c
- median net: +3.50c
- positive-net rate: 55.56%

### Holdout
- Signals: 54
- +10: 48.15%
- 10-lot average net: +0.39c
- median net: -1.90c
- positive-net rate: 38.71%

Validation -> holdout +10 fell 18.52 points and average net fell about 3.75c.

## Small-sample tags

`ACCELERATION_BURST` and primary `TREND_ALIGNED` have only a handful of signals in validation/holdout. Their percentages are descriptive only and must not be used as evidence of a stable edge.

## Guardrails

- Numeric boolean parsing repair only.
- No threshold changes.
- No feature changes.
- No holdout-selected rule.
- No signal suppression/rescue from these results.
- No automatic promotion.
- Coverage Rescue V1 and Economics Forward V1 remain independent and frozen.
- Any regime-aware trading rule requires a separately frozen prospective cutoff and new future contracts.
