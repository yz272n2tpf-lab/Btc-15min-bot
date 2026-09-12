# V8.1 App Signal Contract

This contract defines how a graduated scalp lane is allowed to appear in the app. It does not enable trading or place orders.

## Non-negotiable protections
- Signal-only. No order placement, no auto-buy, no auto-sell.
- Final Outcome and Early Opportunity remain separate signals.
- Kalshi UP/DOWN prices shown are live market prices, not inferred placeholders.
- Contract timer remains aligned to the active 15-minute Kalshi contract.
- BRTI/BTC source health must be available before a scalp signal can be marked actionable.

## Required scalp payload
Each scalp signal must expose:
- side: UP or DOWN
- lane: 3-7c, 15-30c, or 30-45c (7-15c remains rejected unless a future test explicitly changes that)
- entry_ask
- current_bid
- route: CORE, SURGE, or SUB30_STRONG
- confidence/evidence label
- seconds_left
- expected expansion target(s): +5c / +10c / +20c where supported
- adverse-risk field
- status: WATCH, ACTIONABLE, PROTECT, EXIT/WATCH
- timestamp and active contract ticker

## UI behavior
- Entry <= 50c may be shown as favorable-entry territory; 25-35c remains ideal-entry territory.
- Do not present a scalp as a final-outcome lock.
- Do not allow scalp text changes to move/reflow the Final Outcome card.
- If BRTI or timing integrity fails, scalp status becomes WATCH/PASS rather than actionable.
- A lane disabled by the post-test decision manifest must never surface as actionable.

## Exit/profit guidance
The app may display signal-only prompts such as Protect Profit, Watch, or Exit Warning based on deterioration. It must never submit the exit itself.
