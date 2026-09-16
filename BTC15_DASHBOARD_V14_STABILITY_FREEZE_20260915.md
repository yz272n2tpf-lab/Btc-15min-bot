# BTC15 Dashboard V14 Stability Freeze — 2026-09-15

**Presentation only · signal only · manual execution · no orders**

V14 is a shadow-only presentation candidate built on the accepted V13 candidate.
It must not alter protected EARLY, FINAL, SCALP qualification/lifecycle, Kalshi
pricing, canonical timer authority, data-source authority, or order behavior.

## User-observed issues V14 is allowed to address

1. Live BTC numeric price visibly blinking / alternating white-yellow during normal updates.
2. FINAL OUTCOME card moving vertically when its reason/explanation text changes length.
3. Timer and changing numeric values causing width jitter.
4. Other top-row cards changing height because short/long state copy wraps differently.

## Frozen visual acceptance requirements

- Live BTC numeric value uses stable typography/color during ordinary price updates.
  Direction/market state may be communicated elsewhere, but the numeric glyphs must not
  flash between ordinary update colors.
- Timer and price/probability values use tabular numerals and reserve enough inline width
  to prevent digit-width jitter.
- FINAL and EARLY explanation/reason regions reserve stable minimum height on iPhone and
  iPad breakpoints so normal copy changes do not move neighboring cards.
- Top-row cards use stable minimum heights and stretch consistently within their row.
- SCALP V13 reason stability remains preserved.
- The existing single visible main CONTRACT TIMER remains the only visible contract timer.
- No duplicate timer is introduced.
- No card may hide protected signal state or change a signal solely to stabilize layout.
- No numeric Flip Risk may be introduced.

## Fail-closed implementation rules

- V14 patches generated V13 HTML only after exact DOM anchors are inventoried.
- Every targeted selector/anchor must be unique or otherwise explicitly scoped.
- If a required anchor is absent or ambiguous, the build fails instead of applying broad
  global CSS/JS that could affect unrelated elements.
- V13/V12 services stay unchanged. V14 uses a separate shadow service and URL.

## Safety invariants

V14 must preserve before/after values for:
- SCALP lifecycle constants and safety markers;
- protected EARLY/FINAL integration markers;
- canonical timer markers;
- signal-only/manual-execution/no-orders markers;
- absence of user-facing numeric Flip Risk.

## Human acceptance

Passing automated tests authorizes only a V14 visual-review candidate. Final acceptance
requires iPhone and iPad human visual review through at least one real contract rollover.
It does not authorize strategy or production changes.
