# V8.1 30-45c Integration Handoff

## Purpose
Persistent source of truth for the graduated 30-45c scalp integration. Read this before any future scalp/dashboard integration work so paths, services, source branches, safety boundaries, visual-layout rules, and next steps are not rediscovered from scratch.

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

## Live architecture — backend completed 2026-09-12
The locked V8.1 research collector prints candidates/results to stdout and does not persist a dedicated dashboard CSV. Therefore the production architecture uses a separate read-only HTTP feed instead of inventing a file path or modifying the frozen research collector.

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

## Production dashboard and visual lock
- Production Railway service: `Btc-15min-bot`
- Service ID: `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`
- Production branch: `main`
- Start command: `python -u BTC15_DASHBOARD_RENDER_FIX_V1.py`
- Production domain: `btc-15min-bot-production.up.railway.app`

### Visual integration correction — 2026-09-12
A temporary V8.1 card was initially injected with fixed positioning. User visual review correctly identified that it floated over the app and violated the already-locked dashboard aesthetics. That approach is rejected.

Production now enforces a UI lock:
- no floating V8.1 overlay
- no fixed-position V8.1 card
- no fourth standalone ladder/card added to the locked dashboard
- existing three-ladder visual structure is authoritative
- future graduated-lane data must be mapped into the existing ladder presentation rather than changing the layout
- backend V8.1 feed remains live and untouched

Current production render patch explicitly removes any persisted V8.1 injected script/style and hides any leftover `#v81ScalpCard`. Its self-test requires no V8.1 overlay and preservation of the existing dashboard layout.

### Existing dashboard aesthetics are frozen
Do not change without explicit user approval:
- card locations / overall hierarchy
- three-ladder structure
- scroll behavior
- desktop/iPad/iPhone layout behavior
- fonts, sizes, spacing, colors, or card geometry merely to accommodate a new backend module

Integration means supplying the existing visual system with new validated data, not creating a new UI system.

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
- V8.1 live backend feed: DEPLOYED / SUCCESS
- Signal-only / no-orders boundary: LOCKED
- Floating overlay approach: REJECTED / REMOVED
- Production dashboard layout: RESTORED / UI-LOCKED
- Next integration target: map V8.1 30-45c outputs into the existing locked scalp/reversal ladder structure, with no aesthetic changes

## Future integration template
For every new module/lane:
1. Freeze and record the evidence/decision.
2. Record exact source branch/file/service ownership.
3. Define a typed/fail-closed payload boundary.
4. Preserve signal-only/no-orders explicitly.
5. Identify the EXISTING visual destination before writing UI code.
6. Do not add a new card/overlay if an existing locked component owns that function.
7. Build regression/release guards.
8. Validate on an isolated service/source before promotion.
9. Verify desktop/iPad/iPhone behavior without changing frozen aesthetics.
10. Record exact deployment/commit IDs and runtime pass markers.
11. Promote only after validation passes.
12. Perform one user-facing visual confirmation.
13. Lock the completed handoff before beginning the next module.

## Anti-loop rule
Before asking the user to search for any filename, path, service, branch, runtime artifact, or UI location:
1. Read this handoff first.
2. Inspect GitHub/Railway metadata and logs through connected tools.
3. Reuse the known live dashboard/state architecture above.
4. Ask the user for a terminal command only when a genuinely new runtime-only detail cannot be retrieved any other way.
5. When a manual step is unavoidable, consolidate it into one short command/action whenever possible.
