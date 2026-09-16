# BTC15 Dashboard V15 Responsive Candidate Freeze

**SHADOW PRESENTATION CANDIDATE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS**

V15 is intentionally built on top of the exact V14 generated dashboard. It is not a production deployment and may not be merged/deployed as production without separate explicit approval.

## Allowed V15 changes

- Responsive placement of the existing FINAL, EARLY, CONTRACT TIMER and SCALP cards through CSS/classes on existing V14 containers.
- One-column phone layout.
- Two-column tablet/desktop layout.
- Stable card width/min-width behavior.
- No whole-card transition animation.
- Runtime fail-closed DOM guard before responsive classes are installed.

## Measured V14 DOM authority

The generated V14 DOM was captured before adapting V15:
- FINAL is child 0 of `div.left-stack`.
- EARLY is child 1 of `div.left-stack`.
- CONTRACT TIMER is child 0 of `div.right-stack`.
- SCALP is child 1 of `div.right-stack`.
- `div.left-stack` and `div.right-stack` share `section.primary-grid` as their parent.
- There is exactly one `#timerRemaining` node.

V15 must match this measured hierarchy; the audit is not weakened to fit V15.

## Frozen semantic order

1. FINAL OUTCOME
2. EARLY OPPORTUNITY
3. CONTRACT TIME LEFT
4. SCALP OPPORTUNITY

V15 adds no second timer and no numeric Flip Risk card.

## Runtime DOM guard

Responsive classes may install only when:
- FINAL and EARLY share a `.left-stack` parent;
- TIMER and SCALP share a `.right-stack` parent;
- both stacks share one `.primary-grid` parent.

If any relationship drifts, the V14 DOM/layout remains unchanged and the page records a guarded-noop status.

V15 does **not** create, move, append, clone, or recreate the four signal-card DOM nodes. It only adds classes/data metadata to the existing `primary-grid`, `left-stack`, and `right-stack` containers after the guard passes.

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

The four existing card anchors and single canonical timer must remain exactly once in generated HTML. Existing signal-card nodes are never moved or recreated by V15.

Any other direct child already present in `.primary-grid` remains present and is forced full-width below the named V15 core grid areas rather than being deleted or overwritten.

## Status

Research/app candidate only. No Railway deployment. No production logic changed.
