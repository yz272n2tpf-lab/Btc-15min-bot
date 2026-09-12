# V8.1 30-45c Integration Handoff

## Purpose
Persistent source of truth for the graduated 30-45c scalp integration. Read this before any future scalp/dashboard integration work so paths, services, source branches, safety boundaries, and next steps are not rediscovered from scratch.

## Frozen research decision
- Graduated lane: 30-45c only
- Allowed routes: CORE, SURGE
- 15-30c: hold for more sample
- 7-15c: rejected by V8.1 design
- 3-7c: insufficient sample / shadow only
- Signal-only, manual execution only, no automatic orders
- Do not retune the graduated 30-45c qualification logic during integration

## Forward evidence used for graduation
- Valid uninterrupted V8.1 run on `v81-final-isolated-test`
- 30-45c: n=10, +5c 100%, +10c 100%, +20c 70%, avg max gain +27.7c, avg adverse -2.0c
- 15-30c: n=2, promising but insufficient sample

## Proven integration components
- v81_30_45_integration_adapter.py
- v81_30_45_app_payload.py
- test_v81_30_45_integration_adapter.py
- v81_30_45_app_integration_gate.py
- v81_30_45_release_guard.py
- v81_30_45_live_hook.py
- BTC15_V81_30_45_DASHBOARD_CANDIDATE_V1.py

## Live architecture — completed 2026-09-12
The locked V8.1 research collector prints candidates/results to stdout and does not persist a dedicated dashboard CSV. Therefore the final production architecture uses a separate read-only HTTP feed instead of inventing a file path or modifying the frozen research collector.

### Graduated scalp feed
- Railway service: `v81-30-45-live-feed-v2`
- Service ID: `afd8f1f0-65f6-46f0-a79b-ef582f35293f`
- Source branch: `v81-30-45-live-feed-immutable-20260912`
- Start command: `python -u v81_30_45_live_feed.py`
- Public domain: `v81-30-45-live-feed-v2-production.up.railway.app`
- Endpoints: `/health`, `/state`
- Production deployment validated SUCCESS
- Runtime markers: `V81 FEED HTTP | port 8080` and `V81 LIVE FEED START | 30-45 ONLY | CORE/SURGE | SIGNAL ONLY | NO ORDERS`

### Feed payload boundary
Must remain:
- version: V8.1_GRADUATED_30_45
- entry_band: 30-45c
- graduated: true
- manual_execution_only: true
- order_action: null
- owns_final_outcome: false
- owns_early_opportunity: false

Feed only publishes a live candidate when:
- entry ask is 30-45c inclusive
- side is UP or DOWN
- route is CORE or SURGE
- frozen freshness/structure gates pass
- two confirmations occur inside 4 seconds

### Dashboard production integration
- Production Railway service: `Btc-15min-bot`
- Service ID: `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`
- Production branch: `main`
- Start command: `python -u BTC15_DASHBOARD_RENDER_FIX_V1.py`
- Production domain: `btc-15min-bot-production.up.railway.app`
- Integration source branch used for validation: `v81-dashboard-live-card-20260912`
- Integration commit promoted to main: `6111ef585348d968c2d5c2c72aa529b1662c73df`
- Production deployment after promotion: `e9554283-3736-4f25-b18e-36241fd39edd` — SUCCESS

The live dashboard patch adds a separate `Scalp Opportunity · V8.1` card. It polls the graduated feed every second and fails closed if any payload invariant is missing. It does not replace or own Final Outcome or Early Opportunity.

### Validation service
- Railway service: `v81-dashboard-live-card-validation`
- Service ID: `80e36da7-15aa-447e-9b08-fad61d193d11`
- Validation deployment: `5aeb6837-8e96-497c-839d-82f5257bf914` — SUCCESS
- Required pass markers observed:
  - `BTC15 FULL VALIDATION + DASHBOARD SELF-TEST: PASS`
  - `Read-only dashboard: YES`
  - `Orders enabled by dashboard: NO`
  - `V81 DASHBOARD CARD SELFTEST PASS | 30-45 ONLY | MANUAL ONLY | NO ORDERS`

## Live dashboard wiring discovered in Codespaces
Repository working directory: `/workspaces/Btc-15min-bot`
State builder: `BTC15_DASHBOARD_STATE.py`
Generated state file: `dashboard_state.json`
Dashboard installer: `BTC15_INSTALL_LIVE_DASHBOARD_V13.py`
Production HTML patcher/start entry: `BTC15_DASHBOARD_RENDER_FIX_V1.py`

### Existing state namespaces
- timer
- market
- early
- rescue_v2
- parity
- position_protection
- safety

The final V8.1 integration is deliberately UI/feed isolated rather than rewriting these namespaces.

## Safety invariants
Existing dashboard safety must remain:
- read_only: true
- orders_enabled: false
- trading_logic_changed: false

Graduated scalp integration must remain:
- manual execution only
- signal-only
- no order action
- no ownership/change of Final Outcome
- no ownership/change of Early Opportunity
- fail closed on wrong lane, wrong route, expired signal, or malformed payload

## Railway packaging lesson
Earlier isolated validation services repeatedly received stale/wrong source snapshots. Do not interpret source-packaging failures as a trading-logic failure and do not reopen the frozen 30-45c lane because of deployment plumbing. The successful feed was built from an immutable branch containing the inherited V8 dependencies.

## Current status
- 30-45c qualification logic: FROZEN / GRADUATED
- Live feed: DEPLOYED / SUCCESS
- Dashboard candidate self-test: PASS
- Production dashboard promotion: DEPLOYED / SUCCESS
- Remaining final confirmation: visual check on the user-facing app that the V8.1 card renders as WAIT or a valid live signal and that the existing Final/Early cards remain visually intact.

## Future integration template
For every new module/lane:
1. Freeze and record the evidence/decision.
2. Record exact source branch/file/service ownership.
3. Define a typed/fail-closed payload boundary.
4. Preserve signal-only/no-orders explicitly.
5. Build regression/release guards.
6. Validate on an isolated service/source before promotion.
7. Record exact deployment/commit IDs and runtime pass markers here (or in the module handoff).
8. Promote only after validation passes.
9. Perform one user-facing visual confirmation.
10. Lock the completed handoff before beginning the next module.

## Anti-loop rule
Before asking the user to search for any filename, path, service, branch, or runtime artifact:
1. Read this handoff first.
2. Inspect GitHub/Railway metadata and logs through connected tools.
3. Ask the user for a terminal command only when a genuinely new runtime-only detail cannot be retrieved any other way.
4. When a manual step is unavoidable, consolidate it into one short command/action whenever possible.
