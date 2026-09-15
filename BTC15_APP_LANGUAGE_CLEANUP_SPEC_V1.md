# BTC15 APP LANGUAGE CLEANUP SPEC V1

STATUS: PRESENTATION-ONLY SPEC — DO NOT DEPLOY UNTIL LOGIC IS FROZEN

Purpose: define the final user-facing wording for the BTC 15-minute signal-only dashboard after behavior is accepted. This spec changes no qualification, scoring, timing, pricing, Kalshi integration, scalp lifecycle, protection, FINAL logic, EARLY logic, or order behavior.

## Core language rules

- Use **UP / DOWN**, never “long / short.”
- Lead with the action the user needs now: **WAIT / BUY / HOLD / WATCH / PROTECT / EXIT / LOCK**.
- Keep backend/debug wording out of the final app.
- Never imply the user owns a position unless the app actually told them an acceptable manual entry was available.
- Keep EARLY, SCALP, and FINAL visually and verbally separate.
- Kalshi price is shown as entry guidance; it is not silently turned into a hidden qualification gate.
- No numeric Flip Risk percentage until separately calibrated and validated.
- Signal only. Manual execution. No orders.

## Entry Guidance

### Ideal entry

Label: **IDEAL ENTRY**

Condition for presentation: 25–35¢ on the signaled side.

Suggested copy:
- `IDEAL ENTRY · 31¢`
- `BUY RANGE · 25–35¢`

### Good entry

Label: **GOOD ENTRY**

Condition for presentation: 36–50¢ on the signaled side.

Suggested copy:
- `GOOD ENTRY · 44¢`
- `ENTRY STILL OK · 44¢`

### Expensive / no manual entry assumed

Label: **DON'T CHASE**

Suggested copy:
- `MOVE VALID · PRICE TOO HIGH`
- `TRACKING ONLY · DON'T CHASE`
- `WAIT FOR A BETTER PRICE`

Never show `PROTECT PROFITS` or `EXIT NOW` as a user instruction on a path where the dashboard never presented an acceptable manual entry.

## EARLY Opportunity card

Card title: **EARLY OPPORTUNITY**

PASS:
- `WAITING FOR AN EARLY EDGE`

Qualified:
- `EARLY UP OPPORTUNITY`
- `EARLY DOWN OPPORTUNITY`

Supporting rows:
- `Kalshi Entry`
- `Model Edge`
- `Time Left`
- `Entry Quality`

Avoid final-outcome language on this card. EARLY is an opportunity path, not the FINAL lock.

## SCALP Opportunity card

Card title: **SCALP OPPORTUNITY**

Opportunity numbering:
- `UP #1`
- `DOWN #1`
- `UP #2`
- etc.

The number means first, second, third scalp opportunity **inside the current 15-minute contract**. It resets with the next contract.

PASS / scanning:
- `WATCHING FOR SCALP`

Qualified and acceptable entry:
- `UP #1 · ENTRY AVAILABLE`
- `DOWN #1 · ENTRY AVAILABLE`

Active after acceptable manual entry guidance:
- `HOLD · MOVE STILL BUILDING`

Protection armed:
- `PROTECT PROFITS`

Validated giveback exit:
- `EXIT NOW · PROTECT PROFITS`

Expensive qualified path with no assumed position:
- `TRACKING ONLY · DON'T CHASE`

Completed protected scalp:
- `#1 COMPLETED · PROTECTED EXIT`
- `SCANNING FOR #2`

Ended before protection armed:
- `#1 ENDED · NO PROTECTED EXIT`
- `SCANNING FOR #2`

Do not expose `ENDED_UNARMED` as final user-facing wording. That remains backend lifecycle terminology.

Supporting rows:
- `Entry Price`
- `Current Sell Price`
- `Profit Now`
- `Best Profit`
- `Profit Given Back`
- `Time Left`
- `Profit Protection`

Underlying frozen behavior remains +5¢ protection arm and 4¢ giveback EXIT unless separately changed by validated research.

## FINAL Outcome card

Card title: **FINAL OUTCOME**

Before qualification:
- `FINAL CALL NOT READY`
- `WATCHING FOR CONFIRMATION`

Qualified but below explicit lock threshold:
- `LEAN UP`
- `LEAN DOWN`

Locked:
- `LOCK · UP`
- `LOCK · DOWN`

Primary values:
- `UP 93%`
- `DOWN 94%`

Supporting rows:
- `Confidence`
- `Kalshi Price`
- `Time Left`
- `Entry Quality`
- `Reason`

Reason text should be short, natural, and capped visually so the card does not grow/shrink as wording changes.

Examples:
- `Momentum and price distance agree.`
- `Direction is strong, but entry is expensive.`
- `Still too close to the start price.`
- `Waiting for cross-source confirmation.`

Do not present a high-confidence FINAL as a cheap-entry recommendation when Kalshi has already moved above 50¢.

## Lock wording

Use **LOCK** only when the validated FINAL lock condition is met.

Examples:
- `LOCK · UP · 93%`
- `LOCK · DOWN · 95%`

If confidence is high but the frozen lock gate is not complete:
- `HIGH CONFIDENCE · NOT LOCKED YET`

## Market Context

Use plain directional language:
- `BULLISH MOMENTUM`
- `BEARISH MOMENTUM`
- `MIXED / SIDEWAYS`
- `REVERSAL RISK RISING`

Do not use a numeric reversal/flip percentage until that number is independently calibrated.

## Flip Risk area

Until numeric calibration exists:

Title: **FLIP RISK**

Allowed values:
- `LOW`
- `MODERATE`
- `HIGH`
- `NOT CALIBRATED`

Do not display fabricated percentages such as `12%` merely for visual completeness.

## Exit / protection area

When a real accepted scalp path is active:
- `HOLD`
- `WATCH CLOSELY`
- `PROTECT PROFITS`
- `EXIT NOW`

When no manual entry was assumed:
- `TRACKING ONLY`
- `NO POSITION ASSUMED`

## Timer / contract status

Use one visible canonical timer only.

Labels:
- `CONTRACT TIME LEFT`
- `NEXT CONTRACT SYNCING` only during brief rollover fail-closed state

Never show a second scalp-specific countdown.

At rollover, old opportunity numbering/context may remain attached to the old contract until the new contract is established, but it must never remain actionable for the new contract.

## Feed / sync waits

Translate technical waits:
- `WAIT · FEED STALE` -> `WAIT · DATA NOT FRESH`
- `WAIT · INVALID ENVELOPE` -> `WAIT · CHECKING DATA`
- `WAIT · CONTRACT SYNC` -> `WAIT · SYNCING CONTRACT`
- `WAIT · SCALP ALIGNMENT` -> `WAIT · SYNCING SCALP`
- `WAIT · SCALP SOURCE STALE` -> `WAIT · SCALP DATA NOT FRESH`
- `WAIT · SCALP INTEGRATION` -> `WAIT · SCALP NOT READY`

## Visual hierarchy

Top row priority:
1. FINAL OUTCOME
2. EARLY OPPORTUNITY
3. CONTRACT TIME LEFT / SCALP status

Actions must visually dominate explanations.

Preferred action emphasis:
- BUY / IDEAL ENTRY
- WAIT
- HOLD
- WATCH
- PROTECT
- EXIT
- LOCK

Reasoning and debug detail stay secondary.

## Mobile behavior

- Same app/data on iPhone and iPad; layout adapts to screen size.
- No card height jumping when reasoning text changes.
- No blinking BTC price/color changes unless the value itself meaningfully changes state.
- Important action text must remain readable without zooming.
- Avoid wrapping action labels into confusing multi-line fragments.

## Frozen cleanup sequence

1. Logic works correctly.
2. Freeze behavior.
3. Apply this wording cleanup.
4. Tighten colors, spacing, labels, hierarchy, and responsive layout.
5. Run final live-use visual validation.

## Guardrails

- Presentation only.
- No signal threshold changes.
- No new price suppression rule.
- No changes to +5¢ arm / 4¢ giveback protection.
- No changes to serial scalp lifecycle.
- No changes to EARLY/FINAL ownership.
- No changes to Kalshi clock or fixed-start alignment.
- No numeric flip-risk percentage without validation.
- No auto trading or order placement.
