# BTC15 Pullback Entry Forward V1 — Prospective Cutoff

**Frozen cutoff:** `2026-09-16T12:05:59Z` / `2026-09-16 08:05:59 America/New_York`

This cutoff was stamped only after the Pullback Entry V1 implementation, execution-causality tests, denominator tests, and methodology freeze passed the shadow diagnostics CI suite.

Rules:
- only fully observed contracts first seen at/after this cutoff may enter the future denominator;
- pre-cutoff and already-underway contracts are excluded;
- pullback lanes remain fixed at executable ASK <=50c / <=40c / <=35c within 30s or 60s;
- entry is the first then-current executable ASK meeting the lane target;
- all favorable movement before actual entry is discarded;
- +5/+10/+20 and the +5c arm / 4c giveback protected exit restart from the actual pullback entry;
- this is a development/comparison sample only and cannot select or promote a lane;
- any later selected rule requires a new fresh prospective certification window;
- no production writes and no orders.
