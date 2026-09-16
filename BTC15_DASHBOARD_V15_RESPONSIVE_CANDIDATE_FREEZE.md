# BTC15 Dashboard V15 Responsive Candidate Freeze

**SHADOW PRESENTATION CANDIDATE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS**

V15 is intentionally built on top of the exact V14 generated dashboard. It is not a production deployment and may not be merged/deployed as production without separate explicit approval.

## Allowed V15 changes

- Responsive placement of the existing FINAL, EARLY, CONTRACT TIMER and SCALP cards.
- One-column phone layout.
- Two-column tablet/desktop layout.
- Stable card width/min-width behavior.
- No whole-card transition animation.
- Runtime fail-closed DOM guard before the responsive wrapper is installed.

## Frozen semantic order

1. FINAL OUTCOME
2. EARLY OPPORTUNITY
3. CONTRACT TIME LEFT
4. SCALP OPPORTUNITY

V15 adds no second timer and no numeric Flip Risk card.

## Runtime DOM guard

The responsive wrapper may install only when all four expected card anchors exist and share the same parent. If they do not, the V14 DOM/layout remains unchanged and the page records a guarded-noop status.

## Inherited authorities that V15 may not change

- V14 BTC numeric anti-blink behavior.
- V14/V4 fixed FINAL reason/action-subtext height behavior.
- V13 plain-language presentation.
- V12 no-position / expensive-entry tracking semantics.
- Protected MAIN contract and timer authority.
- EARLY qualification.
- FINAL qualification / LOCK authority.
- SCALP qualification and serial lifecycle.
- +5c protection arm and 4c giveback EXIT lifecycle.
- Kalshi price/data-source authority.
- Numeric Flip Risk remains hidden.
- Signal only / manual execution / no orders.

## Network invariant

V15 introduces no `fetch`, XHR, WebSocket, EventSource, timer poller, API endpoint, token, or request client. The count of inherited network primitives in generated V15 HTML must exactly equal V14.

## DOM invariant

The four existing card anchors and single canonical timer must remain exactly once in generated HTML. V15 may create one runtime layout wrapper but may not create duplicate signal cards.

## Status

Research/app candidate only. No Railway deployment. No production logic changed.
