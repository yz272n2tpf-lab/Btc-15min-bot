# BTC15 Rollover Production Integration Map V1

Status: DESIGN / REGRESSION ONLY. No production behavior change authorized.

## Proven shadow evidence
Corrected pre-discovery shadow commit: 0912a864.
Four consecutive verified live boundaries passed:
- exact future ticker staged before open;
- staged ticker held across delayed OPEN visibility;
- exact ticker verified before state advanced;
- activated=false, published=false, orders=false throughout verification.

Observed OPEN visibility delays on the four corrected passes:
26.05s, 26.81s, 41.58s, 26.21s after official open.

## Actual production launch chain
Railway production service: Btc-15min-bot
Source: main
Start: BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py
That wrapper delegates through BTC15_DASHBOARD_INLINE_SCALP_V1.py and BTC15_INSTALL_LIVE_DASHBOARD_V13.py.
The installer materializes BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py from a compressed payload before execution.
Pinned installer SHA during mapping: e1f1390f1fbf6d6649f7dfc319f5b085a9676afd.

## Integration boundary
Pre-discovery must be inserted at the core contract-discovery/selection layer, NOT the dashboard renderer, inline SCALP overlay, EARLY, FINAL, BRTI, target logic, or order-book interpretation.

Required state:
- current active ticker remains authoritative until its official close/boundary;
- next staged ticker is metadata only before open;
- staged ticker cannot publish or become active early;
- at/after official open, exact staged ticker is eligible for handoff to existing quote plumbing;
- mismatch/missing metadata/stale source => fail closed;
- transient OPEN/HTTP failure must retain staged ticker, never silently advance;
- no polling-cadence, signal threshold, settlement, BRTI, quote-provenance, or order behavior change.

## Regression gates before any promotion
1. Exact 15-minute ticker/open/close alignment.
2. No early activation/publication.
3. Existing websocket book provenance unchanged.
4. Target and BRTI readiness/parity unchanged.
5. EARLY protected Tier-1 unchanged.
6. FINAL protected rule unchanged.
7. SCALP unchanged.
8. Dashboard semantics unchanged except earlier valid rollover readiness.
9. Explicit signal_only=true / orders=false.
10. Fail closed under ticker mismatch and temporary API failure.

Next step: expose/decode the generated full-validation wrapper in the isolated branch or inspect its materialized runtime, then locate its core launch target. Do not patch compressed payload blindly.
