# BTC15 Market-Regime Ledger V1

**Mode:** RESEARCH ONLY / DESCRIPTIVE ONLY / NO ORDERS / NO AUTO-PROMOTION

## Purpose

Describe how the existing serial scalp ladder behaves across market states that are observable before entry. This ledger is intended to explain regime dependence; it does not choose a filter or modify any signal.

## Causal regime tags

Tags may overlap. Primary attribution uses the fixed priority listed below.

### TREND_ALIGNED
- structure intact
- BTC/BRTI agreement at 5s and 15s
- no against-side or dual-reversal evidence
- BTC 5s normalized momentum >= 0.60
- BTC 15s normalized momentum >= 0.50

### KALSHI_LAG
- all TREND_ALIGNED conditions
- absolute Kalshi ask repricing over 15s <= 2c

### ACCELERATION_BURST
- structure intact
- BTC/BRTI agree at 5s
- no reversal evidence
- BTC 5s normalized momentum >= 0.75
- acceleration > 0

### REVERSAL_HAZARD
- BTC against-side OR BRTI against-side OR dual-reversal evidence

### CHOP_LOW_CONVICTION
- not reversal hazard
- not trend aligned
- BTC 5s normalized momentum < 0.45
- BTC 15s normalized momentum < 0.45
- 5s or 15s BTC/BRTI agreement is broken

### OTHER
Fallback when no predeclared regime applies.

## Primary priority

1. REVERSAL_HAZARD
2. KALSHI_LAG
3. ACCELERATION_BURST
4. TREND_ALIGNED
5. CHOP_LOW_CONVICTION
6. OTHER

## Reported diagnostics

For development, validation and holdout separately:
- signal and contract counts
- +5/+10/+20 movement rates
- protected-exit rate
- gross captured protected gain
- capture efficiency
- entry ask / <=50c share
- timing
- 1-lot taker/taker net economics
- 10-lot taker/taker net economics
- scalp-index breakdown
- validation -> holdout changes by primary regime

## Integrity

- outcomes never define regime tags
- tags are assigned before outcome/economics are inspected
- no threshold selection
- no signal suppression or rescue
- no ranking or automatic promotion
- no production writes
- no orders

Any future regime-aware trading rule must be frozen separately and tested on a fresh prospective window. V1 diagnostic holdout results cannot be used as if they were untouched evidence for a derived rule.
