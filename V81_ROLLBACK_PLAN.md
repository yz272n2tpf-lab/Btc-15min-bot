# V8.1 Scalp Integration Rollback Plan

This plan is for signal-only integration only. It must never enable automated order placement.

## Before integration
- Record the exact source commit SHA of the currently working production bot/app.
- Record Railway service configuration and active start command.
- Preserve BRTI transport, Kalshi 15-minute alignment, Final Outcome, and Early Opportunity behavior.
- Keep the V8.1 immutable test branch untouched as evidence/reference.

## Integration order
1. Apply only lanes explicitly marked GRADUATE in `v81_lane_decision.json`.
2. Keep rejected/hold/tighten lanes disabled.
3. Run `v81_release_gate.py` before deployment.
4. Run the regression guard and app acceptance checklist.
5. Deploy to an isolated validation service before production.
6. Verify live timestamps, Kalshi prices, UP/DOWN side, entry zone, signal reason, and no-order behavior.

## Automatic rollback triggers
Rollback immediately if any of these occur:
- Kalshi contract timing or ticker alignment drifts.
- BRTI freshness/health degrades materially versus the frozen baseline.
- Final Outcome or Early Opportunity output changes unexpectedly.
- App shows the wrong UP/DOWN side, stale price, or wrong contract.
- Scalp signals emit from a lane not marked graduated.
- Any order-placement code/path becomes reachable.
- Runtime errors, repeated restarts, or missing heartbeats appear.

## Rollback action
- Restore the recorded pre-integration commit and Railway start command.
- Verify production heartbeat and Kalshi/BRTI alignment.
- Keep failed integration changes isolated for diagnosis; do not patch production live.
