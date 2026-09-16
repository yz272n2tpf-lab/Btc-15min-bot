# BTC15 Dashboard V15 Viewport Contract

**SHADOW PRESENTATION CANDIDATE ONLY | NO PRODUCTION DEPLOY | NO ORDERS**

This contract freezes responsive expectations for the V15 candidate after the measured V14 DOM hierarchy and V15 structural audits passed.

## Semantic order

The information hierarchy is always:
1. FINAL OUTCOME
2. EARLY OPPORTUNITY
3. CONTRACT TIMER
4. SCALP OPPORTUNITY

The browser may place cards side-by-side at larger widths, but DOM/source authority, one canonical timer, and the semantic priority above never change.

## Phone class — below 768 px

Core grid is one column:
- FINAL
- EARLY
- TIMER
- SCALP

Requirements:
- no horizontal card overflow;
- no card-node cloning/moving;
- one canonical `#timerRemaining`;
- raw number/timer ticks may update text but do not trigger whole-card animation;
- FINAL reason/action copy remains inside its existing bounded V14 slots.

## Tablet class — 768 through 1180 px

Core grid is two columns:
- FINAL spans both columns;
- EARLY left / TIMER right;
- SCALP spans both columns.

This keeps FINAL visually dominant while preserving the single canonical timer and gives the SCALP card enough width for the protected serial-management rows.

## Desktop / wide tablet — 1181 px and above

Core grid is two columns:
- FINAL left / EARLY right;
- TIMER left / SCALP right.

No signal behavior changes at a breakpoint. Responsive width changes presentation only.

## Existing V14 container authority

V15 may install only when the generated V14 DOM has:
- FINAL + EARLY inside `.left-stack`;
- TIMER + SCALP inside `.right-stack`;
- both stacks directly inside `.primary-grid`.

V15 makes the two stack wrappers layout-transparent with `display: contents` after the guard passes. It does not recreate or move card nodes.

## Other `.primary-grid` children

Any pre-existing direct child other than the guarded left/right stacks remains in the DOM and is forced to full width below the four named core areas. It is never deleted or overlaid by V15.

## App wording / action invariants

- 25–35c: IDEAL ENTRY.
- 36–50c: GOOD ENTRY.
- above 50c: TRACKING ONLY / DON'T CHASE / NO POSITION ASSUMED.
- below 25c: LOW PRICE / CHECK SIGNAL.
- Numeric Flip Risk remains hidden/not calibrated.
- Uncertified 1c/2c/3c Watch-warning research remains hidden.
- Existing frozen 4c giveback EXIT lifecycle remains backend authority.

## Visual stability

- semantic transitions may change emphasis;
- raw bid/ask/BTC/timer ticks do not change card geometry;
- reason text has reserved height;
- tabular numerics remain inherited from V14;
- card content rows do not appear/disappear solely because a transient value is missing.

## Safety

- signal only;
- manual execution only;
- no order controls/actions;
- no new poller/network request introduced by V15;
- no production deployment from this candidate without explicit approval.
