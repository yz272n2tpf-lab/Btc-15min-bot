# BTC15 Directional Position Manager V1 — Shadow Contract Freeze

Status: SHADOW / READ ONLY / NO ORDERS
Frozen: 2026-09-21

Purpose: presentation and position-state composition only. It does not qualify or retune EARLY, FINAL, or SCALP.

State precedence:
1. protected SCALP EXIT -> EXIT
2. protected SCALP PROTECT -> PROTECT PROFITS
3. already-open directional position -> HOLD
4. protected EARLY QUALIFIED -> BUY
5. protected FINAL QUALIFIED/LOCK -> BUY
6. protected SCALP ACTIVE -> BUY
7. otherwise -> WAIT

Dashboard contract V1 exposes:
- contract and seconds remaining
- Kalshi target, UP/DOWN bid/ask
- protected EARLY fields
- protected FINAL fields
- SCALP fields
- position action/view
- safety: signal_only=true, manual_execution_only=true, orders_enabled=false

Non-goals:
- no new confidence thresholds
- no new stop/profit thresholds
- no order placement
- no mutation of production state
- no replacement of protected module authority

Promotion gate: do not merge into production until live validation streams are reviewed and an integration-specific shadow test proves state parity.
