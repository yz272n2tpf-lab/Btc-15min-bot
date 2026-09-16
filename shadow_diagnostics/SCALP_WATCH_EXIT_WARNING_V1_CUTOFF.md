# BTC15 Watch -> Exit Warning Forward V1 — Prospective Cutoff

**Frozen cutoff:** `2026-09-16T11:48:06Z` / `2026-09-16 07:48:06 America/New_York`

This cutoff was stamped only after the Watch -> Exit V1 code, guardrail tests, and methodology freeze passed the shadow diagnostics CI suite.

Rules:
- only fully observed contracts whose first passive observation is at/after this cutoff may enter the forward sample;
- contracts already underway at the cutoff are excluded;
- fixed +5c arm, Watch 1c/2c/3c giveback comparison lanes, and frozen 4c Exit remain unchanged;
- this is a development/comparison future window, not a production-policy selection window;
- any later selected Watch rule requires a new fresh certification window;
- no production writes and no orders.
