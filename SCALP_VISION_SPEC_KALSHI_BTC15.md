# BTC / KalSHI 15-Minute Bot — SCALP VISION SPEC

## Core definition
A scalp is NOT a tiny 1–2 cent model edge.

A scalp is a meaningful, short-lived move in Kalshi contract price that can be captured before the contract later resumes its broader path or settles the other way.

Examples:
- A side trades around 8c, then jumps to ~22c within 15–30 seconds.
- A side trades around 20–35c, then runs to ~60–80c over the next 30 seconds to 3 minutes.
- The scalp can be profitable even if that side ultimately LOSES the 15-minute contract.

The scalp engine therefore predicts a SHORT-HORIZON PRICE MOVE, not the final settlement outcome.

## What the scalp engine must answer
For every 15-minute contract:
- Is there a meaningful short-term mispricing / rebound / momentum burst?
- Which side has the temporary opportunity?
- What is the current executable Kalshi ask?
- What price move is realistically available?
- How quickly is the move expected?
- When should the trader exit?
- What is reversal / failure risk?

## Required outputs
- SCALP SIDE: UP / DOWN / NONE
- ENTRY PRICE
- EXPECTED PRICE WINDOW / TARGET EXIT
- EXPECTED MOVE SIZE in cents
- EXPECTED TIME TO MOVE
- CURRENT BID / ASK
- HOLD / EXIT
- STOP / INVALIDATION LEVEL
- REVERSAL RISK
- SCALP CONFIDENCE

## Economic requirement
Do not call a scalp merely because there is a 1–2c theoretical edge.

Research should prioritize meaningful executable moves, for example:
- +8c
- +10c
- +15c
- +20c
- +30c or more

The optimizer should report which move-size targets are realistically repeatable with acceptable win rate.

## Entry-price context
Scalps can originate from:
- deep-value prices such as 5–15c
- value prices such as 15–35c
- mid-range prices such as 35–50c
- higher prices when momentum still creates a large executable move

The scalp engine is not restricted to the Tier-1 <=45c directional-entry rule.

## Independence from FINAL
A scalp does NOT need to agree with the eventual FINAL winner.

Example:
- FINAL may ultimately be DOWN.
- UP may still move from 10c to 30c temporarily.
- That UP move is a valid scalp if the bot detects it early and exits correctly.

Therefore:
- FINAL logic must not block a valid scalp.
- Scalp logic must not contaminate FINAL authority.

## Historical research objective
Use existing historical Kalshi price data to identify:
- first executable ask at candidate entry
- future executable bid on the SAME side
- maximum favorable excursion (MFE)
- maximum adverse excursion (MAE)
- time to +8c / +10c / +15c / +20c / +30c
- whether stop-loss occurred before profit target
- whether the move occurred even when the scalp side lost settlement

Rank scalp rules by:
1. win rate
2. average executable profit opportunity
3. median executable profit opportunity
4. time to target
5. actionable coverage
6. drawdown / stop behavior

## Important data-resolution rule
Historical Kalshi candles currently available are 1-minute resolution.

Use them to discover broad scalp patterns and eliminate bad ideas quickly.

Do NOT pretend 1-minute history can prove a 15–20 second scalp.

Sub-minute behavior must later be verified live using faster snapshots/logging.

## Live-resolution requirement
For scalp validation, the live bot should eventually sample faster than the current 30-second general loop when needed.

Desired live scalp observation cadence should be researched at:
- 5 seconds
- 10 seconds
- 15 seconds

Do not increase cadence until data/API stability is confirmed.

## Scalp success metrics
Every scalp test must report:
- number of qualified scalp signals
- win rate
- actionable contract coverage
- average entry ask
- average executable exit bid
- average cents captured
- median cents captured
- average time to exit
- percentage hitting +8c / +10c / +15c / +20c / +30c
- stop-loss rate
- percentage of profitable scalps where scalp side later lost FINAL settlement

That last metric proves whether the scalp engine is adding opportunity beyond directional prediction.

## Anti-drift rule
A scalp module is NOT successful because it finds many tiny edges.

It is successful only if it finds meaningful, executable, short-duration price moves that create worthwhile profit opportunities.

Do not redefine scalp around settlement accuracy.
Do not redefine scalp around 1–2c edges.
Do not force scalp to agree with FINAL.
Do not weaken locked FINAL or Tier-1 ENTRY.

## Development workflow
1. Preserve existing data / model / historical replay foundation.
2. Build scalp research from existing cached Kalshi price history.
3. Batch-test many meaningful move targets offline.
4. Use chronological validation + untouched holdout.
5. Select only strong candidates.
6. Use a short live smoke test with faster snapshots for sub-minute confirmation.
7. Integrate scalp as a separate module beside FINAL and ENTRY.
8. Update UNION ACTIONABLE COVERAGE after scalp is validated.

## Finished-product intent
The bot should seek a worthwhile opportunity in almost every 15-minute contract.

If FINAL direction is uncertain, scalp/reversal may still provide the trade.

True PASS should mean:
"There was no validated directional, scalp, reversal, or other positive-expectation opportunity worth taking."
