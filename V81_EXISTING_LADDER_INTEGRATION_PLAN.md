# V8.1 Existing-Ladder Integration Plan

## Goal
Integrate the graduated 30-45c V8.1 scalp lane into the already-approved three-ladder dashboard layout without adding any new floating, fixed, overlay, fourth-card, or aesthetic structure.

## Visual lock
The current three-ladder layout is authoritative. Preserve card positions, hierarchy, typography, spacing, colors, and responsive behavior unless the user explicitly approves a later aesthetics pass.

## Data ownership
- V8.1 owns only the graduated 30-45c scalp opportunity signal.
- V8.1 does not own or modify Final Outcome.
- V8.1 does not own or modify Early Opportunity.
- V8.1 does not place orders.
- Manual execution only.

## Feed
Use the existing read-only Railway feed:
- service: `v81-30-45-live-feed-v2`
- endpoint: `https://v81-30-45-live-feed-v2-production.up.railway.app/state`
- expected version: `V8.1_GRADUATED_30_45`
- band: `30-45c`
- allowed routes: `CORE`, `SURGE`

## Fail-closed boundary
Accept only payloads where all are true:
- `version == V8.1_GRADUATED_30_45`
- `entry_band == 30-45c`
- `graduated == true`
- `manual_execution_only == true`
- `order_action == null`
- `owns_final_outcome == false`
- `owns_early_opportunity == false`

Otherwise do not render actionable scalp content.

## Existing-ladder behavior
Map the V8.1 payload into the existing scalp/reversal ladder destination only.

When inactive:
- keep existing visual shell unchanged
- show the existing WAIT / no-opportunity state in that ladder's normal content area
- do not create a new card

When active:
- side: UP or DOWN
- entry: V8.1 entry price
- current bid: V8.1 current bid
- route: CORE or SURGE
- time left: V8.1 seconds_left
- targets: +5c / +10c / +20c
- status progression: WATCH -> ACTIONABLE -> ACTIONABLE_EXPANSION -> PROTECT

## Production safety checks before promotion
1. No `position:fixed` or overlay injection for V8.1.
2. No new fourth card.
3. Existing three ladder/card DOM remains present.
4. Final Outcome text/state remains unchanged by V8.1.
5. Early Opportunity text/state remains unchanged by V8.1.
6. Read-only dashboard remains true.
7. Orders remain disabled.
8. Malformed/wrong-band payload fails closed.
9. Mobile and tablet layout continue to scroll normally.
10. One user-facing screenshot confirms the V8.1 content appears inside the intended existing ladder area.

## Anti-loop implementation rule
Before asking for any Codespaces command, use this plan plus `V81_INTEGRATION_HANDOFF.md`, GitHub, and Railway first. Only ask the user for a runtime-only detail that cannot be obtained any other way, and consolidate it into one short command.