# Scalp Exit / Reversal Research V1

Research-only. Signal-only. NO ORDERS.

## Purpose
Entry detection and exit timing are separate problems. This layer defines what must be measured after a qualified scalp entry so the live ladder can protect gains and detect reversals before a temporary Kalshi expansion gives back too much.

## States
ENTRY -> HOLD -> PROTECT -> EXIT -> REVERSAL WATCH -> CLOSED

## Measurements after entry
At 1-second resolution, record:
- entry ask and contemporaneous executable bid
- best executable bid since entry
- max gain from entry
- drawdown from best executable bid
- BTC 5s / 15s directional change
- BRTI 5s / 15s directional change
- Kalshi ask and bid 5s / 15s change
- spread width and spread expansion
- seconds since entry
- seconds left in contract
- opposite-side ask expansion

## Research labels
PROTECT_CANDIDATE when:
- executable gain >= +10c, and
- drawdown from peak >= 3c, or BTC/BRTI momentum materially weakens.

EXIT_CANDIDATE when any of the following occur after a profitable expansion:
- drawdown from peak >= 5c,
- BTC 5s and BRTI 5s both flip against the scalp side,
- opposite-side ask expands >= 5c from its post-entry low,
- spread widens sharply while bid stops advancing,
- contract is under 120s and edge is deteriorating.

REVERSAL_WATCH when:
- original scalp side has lost short-term BTC/BRTI agreement,
- opposite side has fresh positive 5s/15s impulse,
- Kalshi has not yet fully repriced the opposite side.

## Outcome scoring
For every candidate exit rule, calculate:
- cents of peak gain captured
- percentage of peak gain captured
- seconds before/after true local peak
- avoidable giveback after exit
- premature-exit penalty if price continued >= +5c after exit
- reversal confirmation rate

## Promotion requirement
Do not promote an exit/reversal rule because it protects a single winner. It must be evaluated across the same forward contracts as the entry model, separately for UP and DOWN. Prefer the simplest rule that preserves the largest share of peak gain while keeping premature exits controlled.

## Non-negotiables
- No fixed profit target as the only exit rule.
- No automatic trade execution.
- A scalp can be valid even if the 15-minute contract ultimately settles the other way.
- Exit logic must not alter or contaminate entry validation data.
