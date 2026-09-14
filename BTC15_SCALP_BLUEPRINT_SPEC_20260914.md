# BTC 15-Minute SCALP Blueprint — User-Confirmed Spec

**Date locked as build/validation target:** 2026-09-14

**Scope:** SCALP behavior only. This document is the target specification for research, shadow validation, UI integration, and eventual freeze. It does **not** promote unvalidated thresholds into production.

## Non-negotiable behavior

- **SIGNAL ONLY / MANUAL EXECUTION / NO ORDERS.** The bot never places trades.
- Scan the **entire 15-minute contract**, continuously, in both UP and DOWN directions.
- A scalp can appear **anywhere in the contract** if there is still realistically enough time to enter and exit.
- Do **not** impose an artificial per-contract scalp count. A contract may have 0, 1, 2, 3, 4, 8, or more qualified scalp opportunities.
- After one scalp is fully managed and exited, **reset immediately and search for the next qualified scalp** in the same contract.
- Reversals are valid. The next scalp may be the same direction or the opposite direction.

## What triggers a scalp

- A scalp is triggered by the **market setup / movement evidence**, not by Kalshi reaching a preset cents zone.
- Trigger evidence should come from the BTC/BRTI move and momentum/reversal context, with Kalshi behavior used as executable market confirmation/telemetry.
- Kalshi entry price is **not currently a trigger gate** and should not suppress a valid scalp solely because the contract is low-priced or high-priced.
- Price examples such as 5c→15c, 7c→17c, 25c→37c, 32c→42c, or 58c→82c must remain eligible for study if the movement setup qualifies.

## Meaningful move target

- The intended scalp class is a **meaningful move**, approximately **10 cents or more** of executable contract movement.
- Track 10c, 15c, 20c, 30c, 40c, 50c+ outcomes so the system can distinguish small noise from meaningful scalp moves.
- A low-priced entry must **not** be dismissed because the absolute contract price is small. A 7c→17c move can be highly valuable and must remain visible if it qualifies.
- Relative return / payout can be displayed as information, but it must **not currently suppress** a scalp.

## High-price / priced-out research

- Very high entries (for example high-70s into 80s) may become practically priced out.
- **No hard high-price cutoff is locked yet.** It must be tested against real tape first.
- Until that research passes, high-price bands are **telemetry only**, not a trigger or suppression rule.

## Live scalp management

Once a scalp is surfaced, the app should clearly show:

- Direction: UP or DOWN
- Entry / executable price context
- Current executable value / profit
- Best profit / running peak
- Giveback from peak
- Time left in the current 15-minute contract
- Clear plain-language action state such as **BUY / HOLD / CAUTION / PROTECT PROFITS / PREPARE TO EXIT / EXIT NOW** (final wording still to be refined)

The current validated management concept tracks running executable peak and protects gains after arming. Any revised protection numbers must be validated before freeze.

## Failed scalp requirement

- A scalp that never reaches the profit-protection arm must **not remain ACTIVE indefinitely while deteriorating**.
- A failed-pre-arm WATCH/CUT/EXIT rule must be researched and validated separately before becoming actionable.
- Do not invent or promote a loss-cut threshold from a small sample.

## Timer / contract integrity

- The SCALP card must use the same canonical contract/time authority as the main dashboard.
- The SCALP timer must visibly match the current 15-minute contract timer.
- Contract mismatch or stale data must fail closed rather than display an actionable scalp.

## Freeze rule

Do **not** call the SCALP ladder complete or frozen until validation demonstrates the intended full loop:

**scan → qualify → enter guidance → manage → protect/exit → reset → next scalp**, repeatedly throughout the 15-minute contract, with no artificial scalp-count cap.

EARLY opportunity and FINAL outcome remain separate signal tracks and are not changed by this SCALP blueprint.
