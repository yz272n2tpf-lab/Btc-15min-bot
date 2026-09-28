# BTC15 Recovered V11 App — Integration Contract V1

Status: OFF-PRODUCTION / SIGNAL ONLY / NO ORDERS
Branch purpose: preserve the exact historical V11/V12/V13 dashboard lineage and integrate current qualified outputs without redesigning the UI.
Do not merge or deploy during the protected prospective cohort.

## Visual source of truth
- Railway service: combined-dashboard-shadow-v11
- Historical source branch: scalp-move-shadow-v1-20260912
- Host: btc15_combined_dashboard_shadow_v8.py
- UI: BTC15_DASHBOARD_COMBINED_SCALP_UI_V12.py
- Presentation successor: BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py
- Existing render fixes remain part of the lineage.
- Preserve layout, live BTC/BRTI chart, card placement, typography hierarchy, mountain/sacred-geometry treatment, and responsive iPad/iPhone behavior. No redesign.

## Authority separation
Authoritative action state alone may create or change:
- FINAL CALL qualification/side
- qualified EARLY action state
- qualified SCALP/REVERSAL lifecycle
- entry/position/protect/exit lifecycle
- actionable profit-protection instructions

Informational read-only state may decorate the UI only when AVAILABLE, fresh, same-ticker, signal_only=true, orders=false:
- continuous UP/DOWN probability
- live Kalshi bid/ask
- BRTI/target/gaps
- numeric flip risk
- 5M_CAUTION / 3M_GUARD informational phase
- informational market context

Informational values MUST NOT manufacture FINAL, EARLY, SCALP, PROTECT or EXIT authority.

## Current informational source
Schema: BTC15_INFORMATION_V1
Authority: INFORMATIONAL_READ_ONLY
Freshness/identity validation remains mandatory. On WAIT, expiry, rollover, owner restart, clock regression, offline/online transition, or hidden-page invalidation, informational values fail closed rather than persisting stale values.

## UI mappings
FINAL OUTCOME:
- Large continuous probability uses informational probability_up/probability_down.
- Direction display is symmetric: show preferred side directly (e.g. 92% DOWN, not 8% UP).
- FINAL CALL label/qualified action comes only from authoritative final_status/final_side/final_confidence/final_call_source.
- A high descriptive probability is never a FINAL CALL by itself.

EARLY OPPORTUNITY:
- Qualification/action comes only from authoritative EARLY state.
- Kalshi ask may be informational when fresh and ticker-matched.
- Preserve target buy <=50%; ideal 25-35%; good 36-50%; above 50 is caution/no-chase presentation.
- Entry classification never upgrades qualification.

CONTRACT TIMER:
- Use canonical same-contract seconds_left.
- Contract identity must match before action/informational composition.

SCALP / REVERSAL + PROFIT PROTECTION:
- Preserve the existing in-card serial lifecycle and completed-opportunity context.
- Qualified scalp/reversal, entry, PROTECT and EXIT come only from authoritative lifecycle.
- Preserve no-position tracking semantics when entry is too expensive.
- Profit protection remains with the scalp/ladder lifecycle, not a detached footer.
- Expected move window may display only when supplied by a qualified source.

LIVE BTC/BRTI CHART:
- Preserve existing chart placement and render fixes.
- Use BRTI/current qualified price history and exact Kalshi target.
- Never substitute a moving average or unrelated price source.

FLIP RISK:
- Informational numeric display from flip_risk_pct is permitted only while BTC15_INFORMATION_V1 is AVAILABLE/fresh/same-ticker.
- Numeric flip risk alone never creates EXIT/PROTECT authority.

5M / 3M:
- Informational protection_phase/five_minute_caution/three_minute_guard may illuminate caution/guard UI.
- Actual position-management action remains authoritative lifecycle only.

SIGNAL STRENGTH / EVIDENCE / MOMENTUM / MARKET CONTEXT:
- Populate only from explicitly mapped, validated sources.
- Until mapped, render unavailable rather than static/demo values.

## Fail-closed requirements
- No stale values surviving rollover/reconnect/backgrounding.
- No cross-ticker composition.
- No static/demo trading numbers in live mode.
- No UI-derived qualification.
- No orders.
- No strategy/model/threshold/ladder tuning in this branch.
- No changes to protected prospective cohort evidence.

## Acceptance gates before any deployment consideration
1. Exact visual-regression review against recovered V11 app on iPad.
2. Full-feature responsive iPhone review; no feature removal.
3. Authority-adversarial tests: high informational probability cannot manufacture FINAL.
4. Rollover/reconnect/stale/clock-regression fail-closed tests.
5. UP/DOWN parity tests.
6. Authoritative scalp/protection lifecycle tests including too-expensive/no-position path.
7. Current production regression/authority suite remains green.
8. Wednesday prospective cohort and independent forensic certification remain separate gates.
