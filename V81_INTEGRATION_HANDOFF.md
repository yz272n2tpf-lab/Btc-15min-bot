# V8.1 30-45c Integration Handoff

## Purpose
This file is the persistent source of truth for the graduated 30-45c scalp integration so future work does not rediscover runtime/dashboard wiring from scratch.

## Frozen research decision
- Graduated lane: 30-45c only
- Allowed routes: CORE, SURGE
- 15-30c: hold for more sample
- 7-15c: rejected by V8.1 design
- 3-7c: insufficient sample / shadow only
- Signal-only, manual execution only, no automatic orders
- Do not retune the graduated 30-45c qualification logic during integration

## Proven integration components
- v81_30_45_integration_adapter.py
- v81_30_45_app_payload.py
- test_v81_30_45_integration_adapter.py
- v81_30_45_app_integration_gate.py
- v81_30_45_release_guard.py
- v81_30_45_live_hook.py
- BTC15_V81_30_45_DASHBOARD_CANDIDATE_V1.py

## Live dashboard wiring discovered in Codespaces
Repository working directory: /workspaces/Btc-15min-bot
State builder: BTC15_DASHBOARD_STATE.py
Generated state file: dashboard_state.json
Dashboard installer: BTC15_INSTALL_LIVE_DASHBOARD_V13.py

### Current state namespaces
- timer
- market
- early
- rescue_v2
- parity
- position_protection
- safety

### Required new namespace
Add scalp_v81 as a sibling namespace in the state object, immediately before safety. Do not overwrite or repurpose any existing namespace.

## Safety invariants from live builder
The existing safety object must remain:
- read_only: true
- orders_enabled: false
- trading_logic_changed: false

The scalp_v81 payload must also remain:
- version: V8.1_GRADUATED_30_45
- entry_band: 30-45c
- graduated: true
- manual_execution_only: true
- order_action: null
- owns_final_outcome: false
- owns_early_opportunity: false

## Dashboard-state builder structure discovered
- FILES mapping near lines 23-28
- pulled CSV rows around lines 132-135
- latest snapshot selection around lines 137-140
- state object starts around line 145
- early namespace around lines 165-171
- position_protection around lines 191-200
- safety around lines 201-205
- JSON write around line 208

## Runtime/source caveat
The locked V8.1 collector was not present in the local main checkout during integration discovery. Do not rediscover filenames repeatedly. Resolve the exact V8.1 source artifact from the known immutable/research branch or Railway service metadata first, then wire that source into BTC15_DASHBOARD_STATE.py once.

## Railway validation caveat
Railway isolated validation services repeatedly built stale/wrong source snapshots despite correct branch/start-command config. Treat that as deployment plumbing, not a ladder-logic failure. Do not reopen or retune the 30-45c lane because of Railway packaging issues.

## Next integration step
1. Resolve the exact live V8.1 scalp source artifact once.
2. Add it to the FILES mapping in BTC15_DASHBOARD_STATE.py.
3. Parse latest graduated 30-45c event.
4. Build scalp_v81 sibling namespace.
5. Preserve all existing namespaces and safety invariants.
6. Generate dashboard_state.json and verify scalp_v81 appears while Final Outcome/Early Opportunity remain unchanged.
7. Only after that, wire the UI card renderer and visually validate on the app.

## Anti-loop rule
Before asking the user to search for any filename/path/service again, read this handoff first and inspect GitHub/Railway metadata. Ask the user for a terminal command only if a genuinely new runtime-only detail is unavailable through connected tools.
