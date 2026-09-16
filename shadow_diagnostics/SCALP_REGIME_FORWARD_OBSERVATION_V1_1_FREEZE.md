# BTC15 Prospective Regime Observation Ledger V1.1 — Freeze

**Prospective cutoff:** `2026-09-16T11:03:16Z`  
**Local equivalent:** `2026-09-16 07:03:16 EDT`  
**CI-gated code commit before cutoff:** `c715bed3acd7fbd320a64266fe21a855c64232c1`  
**Mode:** PROSPECTIVE / DESCRIPTIVE ONLY / SHADOW ONLY / NO ORDERS / NO SIGNAL SUPPRESSION / NO AUTO-PROMOTION

## Fixed tag definitions

This forward observer uses the already-corrected Regime V1.1 semantics and the existing V1 thresholds without alteration:

- `TREND_ALIGNED`: BTC5 normalized >=0.60 and BTC15 normalized >=0.50, plus the existing structure/agreement/no-reversal semantics.
- `KALSHI_LAG`: Trend-aligned plus `abs(ask_move15) <= 0.02`.
- `ACCELERATION_BURST`: BTC5 normalized >=0.75 and acceleration >0, plus the existing structure/agreement/no-reversal semantics.
- `REVERSAL_HAZARD`: existing against-side / dual-reversal evidence.
- `CHOP_LOW_CONVICTION`: existing BTC5/BTC15 normalized <0.45 plus broken agreement semantics.
- Numeric boolean semantics: finite nonzero numeric flags are true; numeric zero is false.

No threshold may be changed based on observations from this forward window.

## Prospective denominator

A contract enters the forward denominator only if:

1. its first passive tape observation is at or after `2026-09-16T11:03:16Z`, and
2. it is later proven fully observed from >=840 seconds left through <=60 seconds left.

A contract already in progress at the cutoff is excluded. Quiet fully observed contracts remain in the denominator even if they produce no serial scalp opportunity.

## What is reported

- true future fully observed contract denominator
- contracts with at least one serial scalp opportunity
- serial true-contract coverage
- primary and overlapping regime tag incidence against the true future denominator
- +5c / +10c / +20c movement telemetry
- protected-exit rate and captured economics
- entry price/timing
- scalp opportunity index (#1/#2/#3+)

A +10c touch remains movement telemetry and is not treated as a realized +10c exit.

## Evidence-readiness marker

The observer remains `COLLECTING` until both:

- >=100 fully observed future contracts, and
- >=50 observed protected exits.

Then it may become `READY_FOR_MANUAL_DESCRIPTIVE_REVIEW`.

This readiness marker is **not** a PASS/FAIL gate, a regime winner, or promotion authority. Any later regime-aware signal rule must be defined separately and tested on another fresh future cutoff.

## Safety

- no threshold selection
- no signal suppression or rescue
- no production writes
- no automatic promotion
- no orders
- Coverage Rescue V1 remains independently frozen
- Economics Forward V1 remains independently frozen
