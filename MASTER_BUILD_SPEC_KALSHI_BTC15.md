# BTC / Kalshi 15-Minute Bot — MASTER BUILD SPEC

## Non-negotiable finished-product goal
Build a SIGNAL-ONLY trading-analysis system for EVERY Kalshi BTC 15-minute contract.
The user manually executes trades. The bot must never place orders.

The bot is NOT a cherry-pick-only system.
It must evaluate every 15-minute contract and try to identify the best positive-expectation opportunity available in that specific market condition.

True PASS should be the exception: reserved for genuinely untradeable / nail-biter contracts where no validated edge exists.

## Four permanent success requirements
Every change must be judged against ALL FOUR at the same time:

1. ACCURACY
2. ACTIONABLE COVERAGE
3. ENTRY PRICE / ECONOMIC VALUE
4. TIMING / EARLINESS

A build is NOT "better" if it improves one while materially damaging another.

## FINAL outcome requirements
- Target qualified FINAL accuracy: 93–95%+ if sustainably supported by evidence.
- Higher is preferred when coverage remains useful.
- Do NOT manufacture accuracy by PASSing most contracts.
- FINAL must account for:
  - exact Kalshi strike/target
  - time remaining
  - target distance
  - reversal/flip risk
  - market regime / recent range
- Current validated high-confidence FINAL tier may remain selective, but it is only ONE opportunity path.

## Early entry requirements
- Goal: identify the likely winning side BEFORE Kalshi fully prices it in.
- Preferred Kalshi ask: <=50c.
- Especially attractive range: ~20–40c.
- Entry accuracy must remain high enough to be useful.
- Entry timing must be early enough to create meaningful return potential.
- Cheap price alone is NEVER sufficient; it must represent actual model edge.

## Near-every-contract actionable coverage
The finished bot should seek something useful from almost every 15-minute contract.

Possible opportunity paths include:
- Tier-1 early directional value entry
- Secondary directional entry
- Pullback / re-entry
- Momentum scalp
- Reversal scalp
- Later high-confidence FINAL position
- Exit / profit-protection opportunity

A FINAL PASS does NOT mean there was nothing to trade intraperiod.
Scalp/reversal logic must evaluate contracts even when final direction is genuinely uncertain.

## Always-visible information on every contract
Even when no trade qualifies, show:
- current directional bias
- confidence / fair probability
- exact Kalshi target
- BTC distance from target
- time remaining
- live Kalshi UP/DOWN prices
- flip / reversal risk
- reason a trade is or is not qualified

## Scalp / reversal requirements
- Separate from FINAL authority.
- Detect intraperiod directional swings and reversal setups.
- Look for useful trades even in contracts that may ultimately be FINAL PASS.
- Must be validated separately so scalp logic cannot contaminate FINAL accuracy.

## Exit-guidance requirements
For actionable entries, eventually show:
- ENTRY PRICE
- CURRENT KALSHI PRICE
- unrealized profit / loss
- HOLD / EXIT
- TARGET EXIT
- REVERSAL / FLIP RISK

## Coverage is a first-class metric
Every test/optimizer must report:
- qualified FINAL coverage
- Tier-1 entry coverage
- secondary-entry coverage
- scalp/reversal coverage
- UNION ACTIONABLE COVERAGE:
  percentage of contracts with at least one validated opportunity

The finished system should push union actionable coverage toward "almost every contract" without forcing low-quality trades.

## Validation integrity
Never claim success from a tiny sample.

Use:
- official Kalshi settlement truth whenever evaluating final correctness
- actual Kalshi historical/live prices for entry economics
- chronological splits
- untouched holdout sets
- first qualifying signal per contract when scoring entry timing
- separate development/validation/holdout data
- live confirmation before declaring an offline winner production-ready

Never tune against the untouched holdout.

## Development-speed rule
MAXIMUM useful work per iteration without lowering standards.

Default process:
1. Cheap preflight first.
2. Batch/replay many legitimate candidates offline.
3. Automatically score accuracy + coverage + entry price + timing.
4. Select candidates on validation only.
5. Evaluate winner on untouched holdout.
6. Run only a 20–30 minute live smoke test when live verification is necessary.
7. Use 60–90 minute behavior tests only when the smoke test cannot answer the question.
8. Use 4–8 hour / overnight tests ONLY for confirmation after the build is stable.

Do NOT spend an hour live-testing a question that can be answered offline in minutes.

## Change-control rule
- Protect proven modules.
- Prefer one production behavior change per deployed version.
- Multiple ideas may be tested simultaneously OFFLINE in tournaments.
- Only deploy the best validated candidate(s).
- Do not rebuild stable foundations unnecessarily.

## Anti-drift rule
Before calling ANY version an improvement or milestone, explicitly answer:

1. Did accuracy improve or remain protected?
2. Did actionable coverage improve or remain protected?
3. Did entry economics improve or remain protected?
4. Did timing improve or remain protected?
5. Did any previously validated module regress?
6. Does this move us toward useful opportunity in almost every contract?

If the answer to #6 is NO, the version may be a useful TIER or MODULE, but it is NOT the finished bot.

## Current architecture principle
High-confidence validated tiers are anchors, not the whole system.
Do NOT weaken strong tiers merely to increase activity.
Fill coverage gaps with additional independently validated opportunity paths.

## Final acceptance standard
The core trading logic is not finished until:
- FINAL accuracy meets the agreed evidence-backed target,
- early-entry economics are attractive,
- timing is useful,
- union actionable coverage is high across real market conditions,
- scalp/reversal and exit guidance are validated,
- the combined system passes live confirmation,
- and all logic remains signal-only with manual user execution.
