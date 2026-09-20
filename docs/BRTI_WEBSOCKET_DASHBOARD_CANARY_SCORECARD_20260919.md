# BRTI WEBSOCKET DASHBOARD CANARY SCORECARD — 2026-09-19

No production cutover from a partial pass.

## Frozen baseline
- Source branch inherits qualified full-bot WebSocket canary.
- V13 dashboard HTML/presentation bundle remains unchanged.
- V8.1 inline scalp safety wrapper remains unchanged.
- Strategy/model/thresholds remain unchanged.
- Signal-only; manual execution only; NO ORDERS.

## Startup gates
- [ ] dashboard WebSocket static gate PASS
- [ ] main BRTI cutover static gate PASS
- [ ] gateway fail-closed gate PASS
- [ ] adapter compatibility gate PASS
- [ ] isolated data-path gate PASS

## Runtime gates
- [ ] BTC15_USE_SHARED_BRTI=1
- [ ] BTC15_BRTI_TRANSPORT=websocket_gateway
- [ ] qualified BTC15_BRTI_GATEWAY_URL configured
- [ ] startup direct BRTI diagnostic SKIPPED
- [ ] direct /cfbenchmarks/values BRTI polling from dashboard canary = 0
- [ ] BRTI HTTP 429 count = 0
- [ ] BRTI source true age <=5s in normal operation
- [ ] gateway PRIMARY_OK / connected / ready
- [ ] dashboard_state.json remains HTTP 200
- [ ] same KXBTC15M ticker/open/close/target as control
- [ ] +/-$11 WAIT semantics preserved
- [ ] FINAL-60 semantics preserved
- [ ] contract-mismatch WAIT preserved
- [ ] stale/disconnected BRTI fails closed
- [ ] V8.1 manual_execution_only / order_action null preserved
- [ ] canary logs/data isolated from production
- [ ] NO ORDERS throughout
- [ ] at least one active-contract continuation observed
- [ ] at least one clean contract rollover observed

## Production comparison baseline
Known old production path has repeated direct BRTI HTTP 429s and can become >60s stale while dashboard_state.json still returns 200. The canary must remove the transport failure without weakening any protected semantic.

## Decision
DASHBOARD_CUTOVER_APPROVED = false

Rule: any freshness, alignment, WAIT/FINAL, isolation, dashboard-health, or signal-only failure keeps DASHBOARD_CUTOVER_APPROVED=false.
