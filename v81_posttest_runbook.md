# V8.1 Post-Test Runbook

Purpose: finish the scalp-ladder decision quickly after the immutable forward test without touching production until evidence passes.

## Order of operations
1. Export immutable Railway V8.1 runtime log.
2. Run `v81_runtime_integrity_check.py`.
3. If integrity FAILS: do not score/graduate; fix runtime and rerun test.
4. Run `v81_posttest_scorer.py`.
5. Fill `v81_lane_decision_template.json` with evidence-backed decisions.
6. Run the regression guard before any integration.
7. Integrate only graduated lanes on an isolated branch.
8. Validate app output against the integration manifest.
9. Verify unchanged: Final Outcome, Early Opportunity, BRTI, Kalshi 15m timing/alignment, signal-only/no orders.
10. Only then prepare a production-candidate merge/deploy.

## Lane policy
- 3-7c: graduate cautiously only on sufficient sample, useful +10c expansion, and tight adverse movement.
- 7-15c: remains disabled/rejected in V8.1 unless a future separate experiment reopens it.
- 15-30c: graduate only if forward evidence meets the scorer thresholds and adverse movement is controlled.
- 30-45c: preserve CORE/SURGE behavior unless forward evidence materially contradicts prior validation.

## Stop conditions
Do not integrate if any of these occur: wrong runtime banner, missing heartbeats, traceback, BRTI degradation, order-placement code, contract-timing drift, or evidence below the lane threshold.

## Production rule
Signal-only/manual execution remains non-negotiable. No automatic trade placement is introduced by this workflow.
