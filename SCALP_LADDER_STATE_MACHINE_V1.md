# Scalp / Reversal Ladder State Machine V1

Research/design spec only. Signal-only. No order placement.

## Purpose
Translate a validated pre-Kalshi scalp trigger into simple live ladder states without changing the underlying detection model.

## States
1. WAIT
   - No qualified setup.
   - Dashboard shows no scalp call.

2. FORMING
   - BTC/BRTI impulse is developing but promotion threshold has not fully confirmed.
   - Use only for warning/attention, not entry guidance.

3. ENTRY
   - Qualified trigger confirmed before Kalshi repricing.
   - Show side (UP/DOWN), current executable ask, trigger timestamp, lead status, and confidence tier.
   - No fixed cent target; use actual executable ask at trigger.

4. HOLD
   - Position-side Kalshi bid has improved after entry and impulse remains intact.
   - Track unrealized executable gain from entry ask to current bid.

5. PROTECT
   - Gain has expanded enough that reversal risk matters.
   - Triggered by weakening BTC/BRTI persistence, loss of acceleration, opposite-side impulse, or giveback from local max.
   - Dashboard should say protect profit / tighten exit.

6. EXIT
   - Reversal evidence or predefined giveback threshold says the temporary expansion is ending.
   - Show current executable bid and cents gained/lost from entry.

7. REVERSAL WATCH
   - After EXIT or a failed ENTRY, opposite-side qualified evidence begins forming.
   - Must pass its own independent trigger; never auto-flip solely because the prior side failed.

8. CLOSED
   - Contract expired or opportunity horizon ended.

## Core measurements stored per signal
- contract ticker
- side
- trigger timestamp
- seconds left
- entry ask
- entry bid
- BTC and BRTI values
- 5s/15s BTC side-adjusted move
- 5s BRTI side-adjusted move
- Kalshi ask movement over 5s/15s
- time to +5c and +10c executable gain
- max executable gain
- max adverse excursion
- local max bid and giveback from max
- exit timestamp and exit bid
- total executable cents captured
- whether opposite-side reversal subsequently qualified

## Entry principles
- Signal is triggered by BTC/BRTI evidence before Kalshi reprices.
- Kalshi price is the opportunity being exploited, not the source of the prediction.
- No minimum fixed entry price and no target of 45c. Cheap entries such as 7c, 10c, 18c, 25c are valid if evidence qualifies.
- Research versions may use temporary maximum-price guards; those are filters, not the definition of a scalp.

## Exit principles
- A scalp does not need to be the eventual 15-minute settlement winner.
- Optimize capture of the temporary Kalshi expansion.
- Prefer exiting on evidence deterioration/giveback rather than waiting for contract resolution.
- Exit logic must be validated separately from entry logic.

## Promotion dependency
Do not connect these states to the production Scalp/Reversal dashboard until a research trigger passes SCALP_PROMOTION_GATE_V1.md on forward data.
