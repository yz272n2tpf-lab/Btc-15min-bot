# BTC15 Scalp Opportunity Density Forward V1 — Prospective Cutoff

**Frozen cutoff:** `2026-09-16T11:56:59Z` / `2026-09-16 07:56:59 America/New_York`

This cutoff was stamped only after the Opportunity Density V1 code, denominator/economics guardrail tests, and methodology freeze passed the shadow diagnostics CI suite.

Rules:
- only fully observed contracts whose first passive observation is at/after this cutoff may enter the forward density denominator;
- pre-cutoff and already-underway contracts are excluded;
- quiet fully observed contracts remain in the denominator with zero opportunities;
- the existing serial scalp lifecycle is unchanged;
- <=50c and 25-35c coverage are descriptive entry-economics measures, not signal filters;
- +5/+10/+20 movement metrics remain context only;
- readiness at 100 fully observed future contracts is sample-size only, not a performance PASS or promotion gate;
- no production writes and no orders.
