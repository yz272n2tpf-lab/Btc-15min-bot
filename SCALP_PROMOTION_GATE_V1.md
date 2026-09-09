# Scalp / Reversal Promotion Gate V1

Research-only validation policy. No orders.

## Objective
Promote a scalp candidate only when BTC/BRTI evidence consistently appears before Kalshi reprices and produces a usable executable expansion.

## Scorecard
For each version and side (UP/DOWN), record:
- candidate count and unique contract count
- entry ask distribution: median, p25, p75
- +5c executable hit rate
- +10c executable hit rate
- median seconds to +5c and +10c
- median and p90 adverse excursion
- median maximum executable gain
- Kalshi +5c reprice delay
- pre-reprice lead: trigger must occur before Kalshi +5c reprice
- false signal rate: no +5c executable gain within 90s
- late-signal share (<120s left)
- side balance: UP and DOWN evaluated separately

## Promotion gates
Do not connect a research version to the live Scalp/Reversal ladder until all are true on forward, out-of-sample data:
1. At least 50 qualified candidates across at least 20 distinct 15-minute contracts.
2. At least 15 qualified candidates on each side (UP and DOWN). If one side has fewer, that side remains shadow-only.
3. +10c executable hit rate >= 70% overall and >= 65% on each promoted side.
4. +5c executable hit rate >= 80% overall.
5. Median adverse excursion <= 3c; p90 adverse excursion <= 10c.
6. Median entry ask <= 30c. No fixed target entry price; this is a quality statistic, not an entry requirement.
7. At least 70% of +5c winners show positive measured lead before Kalshi's +5c repricing, with trigger timestamp recorded first.
8. No signals with <120 seconds remaining and no near-dead <=2c contract entries in the promoted rule set.
9. Results must span multiple market regimes/contracts; no promotion from one unusually directional window.
10. Production remains signal-only. No order placement code.

## Comparison rule
Compare V2 BROAD, V3 QUALIFIED, and V4 QUALIFIED on the same forward period. Prefer the simplest version that passes the gates. Do not select a version from headline max gain alone.

## Failure / iteration rule
If V4 misses the gates, change one logical family at a time (timing, persistence, BRTI agreement, Kalshi-lag, or price-zone guard), run a new shadow version, and preserve prior versions as baselines.
