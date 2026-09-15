# BTC15 FINAL APP VISUAL QA CHECKLIST V1

STATUS: PRESENTATION / HUMAN QA ONLY — NO STRATEGY CHANGES — NO ORDERS

Purpose: one final visual/live-use acceptance pass after logic is frozen and the plain-language cleanup is applied.

## iPhone

- [ ] FINAL OUTCOME is immediately readable without zooming.
- [ ] EARLY OPPORTUNITY is clearly separate from FINAL.
- [ ] SCALP OPPORTUNITY is clearly separate from both EARLY and FINAL.
- [ ] Contract timer is visible and there is only one countdown.
- [ ] UP / DOWN direction is obvious at a glance.
- [ ] BUY / WAIT / HOLD / WATCH / PROTECT / EXIT / LOCK actions visually dominate explanation text.
- [ ] Kalshi entry price is readable without wrapping awkwardly.
- [ ] IDEAL ENTRY 25–35¢ is visually distinct.
- [ ] GOOD ENTRY 36–50¢ is visually distinct.
- [ ] >50¢ qualified paths clearly say DON'T CHASE / TRACKING ONLY when no manual position is assumed.
- [ ] No card jumps vertically when reasoning wording changes.
- [ ] No BTC price blinking/flickering between colors.
- [ ] No stale old-contract scalp remains actionable after rollover.
- [ ] #1 / #2 / #3 opportunity numbering is understandable and resets with the next contract.

## iPad

- [ ] Same data/logic as iPhone; only layout adapts.
- [ ] Top-row hierarchy remains FINAL / EARLY / TIMER-SCALP as designed.
- [ ] Shorter chart does not push key actions below the initial viewport unnecessarily.
- [ ] Text does not become excessively small because of wider layout.
- [ ] No unnecessary duplicated cards or timers.
- [ ] Reasoning text remains bounded and stable.
- [ ] Entry guidance and scalp management remain readable at normal viewing distance.

## Contract rollover

- [ ] Timer counts down normally with no freeze or backward jump.
- [ ] Brief fail-closed syncing state is acceptable.
- [ ] New contract appears after rollover.
- [ ] Old contract context does not control the new contract.
- [ ] Old scalp opportunity may remain visible only as completed old-contract context, never as new-contract action.
- [ ] EARLY state resets/updates correctly.
- [ ] FINAL state resets/updates correctly.
- [ ] Scalp numbering resets for the new contract.

## FINAL card

- [ ] WATCH / NOT READY wording is plain English.
- [ ] LEAN wording does not look like LOCK.
- [ ] LOCK only appears when the validated FINAL lock condition is actually met.
- [ ] Confidence percentage is visually prominent.
- [ ] Locked-side Kalshi price is shown separately from confidence.
- [ ] Correct-but-expensive locks do not look like cheap-entry recommendations.
- [ ] Reason text is short and natural.

## EARLY card

- [ ] Clearly says EARLY OPPORTUNITY, not FINAL.
- [ ] Direction is UP/DOWN.
- [ ] Entry quality is visible.
- [ ] Time left is visible.
- [ ] No FINAL lock wording appears on EARLY.

## SCALP card

- [ ] SCALP OPPORTUNITY title is plain English.
- [ ] Current opportunity number is visible.
- [ ] Entry price and current sell price are clearly different fields.
- [ ] PROFIT NOW and BEST PROFIT are understandable.
- [ ] PROFIT GIVEN BACK is understandable.
- [ ] PROTECT PROFITS appears only when a position could reasonably have been entered from dashboard guidance.
- [ ] EXIT NOW appears only for a real protected path, not model-only tracking.
- [ ] Expensive qualified path says TRACKING ONLY / DON'T CHASE.
- [ ] Completed opportunity context remains understandable while scanning for the next opportunity.

## Entry guidance

- [ ] 25–35¢ = IDEAL ENTRY.
- [ ] 36–50¢ = GOOD ENTRY.
- [ ] >50¢ = WAIT / DON'T CHASE unless separately justified by a future validated rule.
- [ ] No hidden price rule contradicts the displayed guidance.
- [ ] User can tell the difference between model validity and attractive manual entry price.

## Flip risk / reversal wording

- [ ] No fabricated numeric Flip Risk percentage.
- [ ] If numeric risk is not yet calibrated, app says NOT CALIBRATED or uses explicitly defined qualitative wording only.
- [ ] Reversal-risk wording does not override FINAL ownership.

## Feed / sync messages

- [ ] WAIT · DATA NOT FRESH is understandable.
- [ ] WAIT · SYNCING CONTRACT is understandable.
- [ ] WAIT · SCALP DATA NOT FRESH is understandable.
- [ ] Technical backend terms are hidden from normal user view.
- [ ] Temporary feed issue fails closed rather than showing stale action.

## Stability

- [ ] No layout shaking.
- [ ] No card height pulsing.
- [ ] No price-color flicker.
- [ ] No duplicate timer.
- [ ] No duplicate scalp card.
- [ ] No stale action across contract rollover.
- [ ] No console/debug text visible in normal dashboard.

## Safety footer

- [ ] SIGNAL ONLY visible.
- [ ] MANUAL EXECUTION visible.
- [ ] NO ORDERS / no order controls.

## Acceptance

Human visual acceptance requires all critical items above to pass on both iPhone and iPad during at least one real contract rollover.

Passing this checklist authorizes presentation acceptance only. It does not automatically authorize production strategy changes or order placement.
