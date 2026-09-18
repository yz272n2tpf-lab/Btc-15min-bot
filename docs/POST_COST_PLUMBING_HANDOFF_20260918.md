# POST-COST HANDOFF — ORIGINAL PLUMBING / INFRASTRUCTURE

This is queued immediately after cost-remediation completion. Cost work does NOT replace these repairs.

## Correctness gates to return to
1. BRTI freshness / 429 handling / source parity.
2. Provider timeout and connection-reset resilience.
3. Kalshi contract identity, fixed start price, and 15-minute rollover alignment.
4. Observation latency: forward scorecards must receive contracts early enough to count; "process healthy" is not sufficient.
5. EARLY -> FINAL handoff continuity.
6. Scalp evidence delivery and entry-price synchronization.
7. Logging/scoring continuity across restart/deploy boundaries.
8. Health semantics must include data freshness/correctness, not merely HTTP process liveness.
9. End-to-end untouched-contract certification before ladder retuning.

## Cost finding relevant to plumbing
Early/Final/BRTI/scoreboard services are already small (~0.02-0.05 GB RAM each in sampled hour), so correctness—not cost—is their priority.
Main Btc-15min-bot is a separate large cost center (~4.40 GB 24h avg RAM, ~0.485 vCPU) and must be investigated during this plumbing phase without changing signal semantics.

## Exit gate before ladders
Trace untouched 15-minute contracts:
market data -> BTC/BRTI -> Kalshi -> correct contract/start -> EARLY -> FINAL -> scalp -> entry -> Watch/Exit -> evidence/logging -> scorecard.
Require fresh sources, correct timestamps/contract IDs, no late exclusion, no missing intervals, no evidence reset contamination, NO ORDERS.

Only after this integrity gate passes do ladder performance changes resume.
