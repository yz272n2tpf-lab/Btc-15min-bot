# BTC15 Protected FINAL Forward Scorecard Freeze V1

**Frozen before live confirmation outcomes are reviewed.**  
**Mode:** READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

## Purpose

Confirm the already-protected FINAL module in the current integrated system without retuning it.

The scorecard must answer four separate questions:

1. **Accuracy** — Was the first protected FINAL LOCK side correct against official Kalshi settlement?
2. **FINAL-only coverage** — On what percentage of observed 15-minute contracts did protected FINAL produce a LOCK?
3. **Entry economics** — What was the actual Kalshi ask for the locked side at the first LOCK?
4. **Timing** — How many minutes remained at the first LOCK?

No single metric may substitute for the other three.

## Historical anchor

Source files:

- `fresh_oos_market_manifest.csv`
- `fresh_oos_locked_final_calls.csv`

Known prior fresh-OOS directional anchor:

- 250 observed contracts
- 133 protected FINAL calls
- 99.2% qualified accuracy
- 53.2% FINAL-only coverage
- ~5.04 minutes average remaining
- 5.0 minutes median remaining

The new scorecard adds the actual Kalshi preferred ask distribution from the same frozen call rows. This is evaluation only; it does not add a price gate to protected FINAL.

## Live forward cutoff

`2026-09-15T16:45:00Z`

Nothing observed before this cutoff counts toward the new live confirmation sample.

The cutoff is aligned to a complete 15-minute contract boundary so the service does not count a partial startup contract.

## Live scoring rule

For each contract after the cutoff:

- count the contract once in the observed universe;
- record only the **first protected FINAL LOCK**;
- preserve the protected side and confidence exactly;
- record canonical seconds/minutes remaining;
- record live Kalshi bid/ask for the protected side;
- later resolve the call against **official Kalshi settlement truth**;
- never rewrite a call after the fact.

## Price bands — evaluation only

- `<25c`
- `25–35c` — preferred/ideal zone
- `36–50c` — acceptable zone
- `51–70c`
- `71–85c`
- `>85c`

A correct 94c FINAL call remains a correct directional prediction but is explicitly an expensive/non-preferred entry. It must not be counted as a <=50c entry.

**No Kalshi price is used to qualify or suppress protected FINAL.**

## Timing bands

- `>=6m`
- `5–6m`
- `3–5m`
- `<3m`

Timing is descriptive confirmation only. Protected FINAL thresholds remain unchanged.

## Initial live smoke sample

The scorecard may label the live confirmation sample `LIVE_SMOKE_SAMPLE_READY` only after both:

- at least **30 complete observed contracts**, and
- at least **12 officially settled protected FINAL LOCK calls**.

This is a live integration/behavior smoke threshold, not a new model-selection holdout and not enough by itself to retune FINAL.

## Guardrails

- Protected FINAL rules remain unchanged.
- No threshold search from the live confirmation sample.
- No auto-promotion.
- No new price filter.
- No stop-loss.
- No numeric flip-risk percentage until separately calibrated.
- FINAL-only coverage is not UNION actionable coverage.
- EARLY and SCALP remain independent opportunity authorities.
- Official Kalshi settlement is the truth label for FINAL accuracy.
- Signal only. Manual execution only. No orders.

## Anti-drift interpretation

The finished system goal is not “99% FINAL therefore done.” A protected FINAL can be extremely accurate while arriving after Kalshi has already repriced to 90c+.

Therefore the scorecard must keep these statements separate:

- **directionally correct**;
- **high-confidence protected FINAL**;
- **economically attractive entry at the time of the call**;
- **early enough to be useful**.

The system may rely on separately validated EARLY and SCALP paths to provide economic opportunity in contracts where protected FINAL is intentionally selective or expensive.
