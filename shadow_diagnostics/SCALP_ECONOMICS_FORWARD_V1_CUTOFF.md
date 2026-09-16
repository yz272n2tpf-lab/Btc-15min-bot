# BTC15 Scalp Economics Forward V1 — Prospective Cutoff

**Frozen cutoff UTC:** `2026-09-16T10:31:55+00:00`  
**Local equivalent:** `2026-09-16T06:31:55-04:00`  
**Mode:** SHADOW ONLY / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION

The accounting rules, sample-readiness gates, lane definitions, fee views and break-even evidence conditions were committed and tested before this timestamp.

Only fully observed contracts whose first passive observation is at or after this cutoff may enter the prospective economics denominator.

No contract already underway at the cutoff may be admitted later.

The forward test must not alter:

- baseline scalp detector
- serial lifecycle
- +5c arm / 4c giveback protection
- realized-exit definition
- fee model used for the frozen evidence gate
- sample thresholds
- break-even evidence conditions
- lane definitions (#1, #2, #3+)

Results are for manual review only and can never trigger automatic production promotion or orders.
