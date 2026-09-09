# Scalp / Reversal Ladder Payload Contract V1

Research/integration specification only. No order placement.

## Purpose
Define the exact data contract the validated scalp engine must emit before it is allowed to drive the dashboard ladder. This keeps detection logic, risk logic, and presentation decoupled.

## Required live payload
Each update should expose:
- contract_ticker
- timestamp_utc
- seconds_left
- side: UP | DOWN | NONE
- state: WAIT | FORMING | ENTRY | HOLD | PROTECT | EXIT | REVERSAL_WATCH | CLOSED
- confidence_0_100
- entry_ask
- live_bid
- live_ask
- peak_bid_since_entry
- unrealized_gain_cents
- giveback_from_peak_cents
- btc_price
- brti_price
- btc_move_5s
- btc_move_15s
- brti_move_5s
- brti_move_15s
- kalshi_ask_move_5s
- kalshi_ask_move_15s
- opposite_side_ask
- opposite_side_move_5s
- lead_quality: EARLY | MARGINAL | LATE | UNKNOWN
- lead_seconds_to_kalshi_reprice
- exit_risk_0_100
- reversal_risk_0_100
- reason_code
- message

## State behavior
WAIT: no qualified setup.
FORMING: qualified pre-Kalshi evidence building, but entry not yet confirmed.
ENTRY: first actionable signal; snapshot entry_ask and timestamp exactly once.
HOLD: signal remains aligned and price expansion is underway.
PROTECT: meaningful profit exists and giveback/reversal risk has increased.
EXIT: evidence says protect realized opportunity now; do not continue calling HOLD.
REVERSAL_WATCH: original move is fading and opposite-side setup may be forming.
CLOSED: event complete or contract no longer suitable for scalp action.

## Guardrails
- Entry price is observed, never forced to a fixed target cent value.
- Research ceiling can remain separate from UI language.
- No new ENTRY if seconds_left < 120 in the promoted rule set.
- No promoted ENTRY for near-dead <= 2c contracts.
- One entry snapshot per scalp event; repeated qualifying ticks must not create duplicate entries.
- EXIT must be sticky for a short confirmation window so the UI does not flicker back to HOLD.
- REVERSAL_WATCH must not automatically create an opposite-side ENTRY; it only arms the opposite-side detector.
- Dashboard is signal-only; no order fields, order ids, position sizing, or execution actions.

## Reason codes
Examples:
- BTC_BRTI_PREKALSHI_IMPULSE
- KALSHI_LAG_CONFIRMED
- MOMENTUM_PERSISTENCE
- PEAK_GIVEBACK
- BTC_BRTI_FLIP
- OPPOSITE_SIDE_REPRICE
- LATE_WINDOW_BLOCK
- DEAD_CONTRACT_BLOCK
- DATA_STALE_BLOCK

## Promotion rule
Only a version that passes SCALP_PROMOTION_GATE_V1.md may populate ENTRY/HOLD/PROTECT/EXIT states in production. Until then, shadow versions may emit identical payloads into logs for dry-run comparison only.
