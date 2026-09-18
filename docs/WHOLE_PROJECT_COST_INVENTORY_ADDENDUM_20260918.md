# WHOLE PROJECT COST INVENTORY ADDENDUM — 2026-09-18

Captured 1h engineering averages (not invoice):
- Btc-15min-bot: ~4.57 GB RAM, ~0.474 vCPU. This is a separate major cost center and must be investigated during plumbing/infrastructure repair before production freeze.
- combined-dashboard-shadow-v14: ~0.024 GB RAM.
- authoritative-scoreboard-v1: ~0.024 GB.
- early-excursion-forward-v1: ~0.046 GB.
- early-final-handoff-v1: ~0.050 GB.
- early-forward-scorecard-v1: ~0.036 GB.
- combined-forward-scorecard-v1: ~0.033 GB.
- final-forward-scorecard-v1: ~0.052 GB.
- brti-shared-feed-v1: ~0.032 GB.

Conclusion: Early/Final/BRTI scoreboard plumbing is already lightweight. The principal RAM/CPU cost centers are the scalp full-tape research cluster plus the main Btc-15min-bot service. Do not optimize the lightweight plumbing first.

Action order after scalp canary:
1. Prove bounded-state pattern.
2. Apply to high-cost scalp consumers.
3. Audit Btc-15min-bot 4.57 GB footprint as part of original Work plumbing/infrastructure remediation; preserve live signal semantics.
4. Leave already-light Early/Final/BRTI services alone unless correctness audit requires change.
