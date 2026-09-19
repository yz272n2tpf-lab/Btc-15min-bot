# BRTI WEBSOCKET FULL-BOT CANARY SCORECARD — 2026-09-19

This scorecard is intentionally strict. No production cutover from a partial pass.

## Required runtime evidence
- [ ] Exact canary branch/commit confirmed
- [ ] Main cutover static gate PASS
- [ ] Gateway client fail-closed gate PASS
- [ ] Kalshi authentication PASS
- [ ] Direct CF/BRTI HTTP polling from full bot = 0
- [ ] WebSocket BRTI source age <= 5.0s during normal operation
- [ ] No HTTP 429 from the canary BRTI path
- [ ] Sequence advances continuously
- [ ] No duplicate/out-of-order/bad BRTI accepted
- [ ] At least 4 complete KXBTC15M contract rollovers observed
- [ ] Contract ticker/open/close/target alignment preserved
- [ ] +/-$11 WAIT semantics preserved
- [ ] FINAL authority semantics preserved
- [ ] Stale/disconnected BRTI forces WAIT
- [ ] Restart/reconnect requires fresh new-epoch BRTI
- [ ] Logging/scoring remains isolated from production
- [ ] orders=false / signal-only throughout

## Decision
CUTOVER_APPROVED = false

Rule: any failed freshness, alignment, protected-semantic, logging-isolation, or signal-only gate keeps CUTOVER_APPROVED=false.

Rollback after any future production cutover: restore prior production branch/config immediately if BRTI freshness, Kalshi alignment, protected WAIT/FINAL semantics, logging/scoring, or signal-only behavior regresses.
