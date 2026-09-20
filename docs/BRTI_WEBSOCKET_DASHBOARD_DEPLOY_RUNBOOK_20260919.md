# BRTI WEBSOCKET DASHBOARD CANARY DEPLOY RUNBOOK — 2026-09-19

## Source
Branch: brti-websocket-dashboard-canary-20260919
Entrypoint: python -u btc15_dashboard_ws_canary_runner_v1.py

## Required variables
- BTC15_USE_SHARED_BRTI=1
- BTC15_BRTI_TRANSPORT=websocket_gateway
- BTC15_BRTI_GATEWAY_URL=<qualified gateway URL>
- BTC15_ISOLATED_CANARY_LOCAL_DATA=1
- KALSHI_KEY_ID / KALSHI_PRIVATE_KEY_B64 copied from protected production
- PYTHONUNBUFFERED=1
- PORT supplied by Railway

Do not copy production /data into the canary. Do not change strategy/model/thresholds.

## Launch
The runner executes the preflight. Preflight executes all static gates and a live PRIMARY_OK <=5s gateway read. Any failure stops startup before the dashboard launches.

## Observe
Require dashboard_state.json HTTP 200, zero direct cfbenchmarks BRTI polling, zero BRTI 429s, fresh BRTI <=5s, matching contract/target, preserved +/-$11 WAIT and FINAL-60 semantics, V8.1 manual-only safety, one active continuation and one rollover.

## Rollback / stop
Canary failure does not modify production. Stop/remove only the canary service. Keep production on protected main until scorecard is fully passed. NO ORDERS throughout.
