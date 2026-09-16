# BTC15 Pullback Entry Forward V1 — Prospective Development Freeze

**SHADOW ONLY · SIGNAL ONLY · DEVELOPMENT COMPARISON · NO ORDERS · NO AUTO-PROMOTION**

## Purpose
Test the dashboard idea **“Wait for pullback”** without assuming that simply waiting improves entry price.

The study asks whether an unchanged serial scalp opportunity later offers a real executable ASK at a lower absolute price while enough executable movement remains to preserve scalp utility.

## Frozen comparison lanes
Targets are fixed before the future sample:
- ASK <=50c within 30 seconds
- ASK <=50c within 60 seconds
- ASK <=40c within 30 seconds
- ASK <=40c within 60 seconds
- ASK <=35c within 30 seconds
- ASK <=35c within 60 seconds

The unchanged immediate candidate is reported separately as the reference lane.

## Execution semantics
For each frozen pullback lane:
- Entry occurs only at the **first then-current executable ASK** at or below the lane target within its wait window.
- If the candidate ASK already meets the target, the lane qualifies immediately at t=0.
- If no executable ASK reaches the target within the window, the lane does not enter that opportunity.
- Favorable movement before the actual pullback entry is discarded.
- Movement after entry is measured only from subsequent executable BID observations.
- +5c / +10c / +20c are rebased to the actual pullback ASK.
- The existing +5c arm / 4c giveback protection lifecycle is also rebased to the actual pullback entry.
- Fee-adjusted protected-exit economics use the existing conservative 1-lot and 10-lot taker/taker accounting.

## Serial-opportunity discipline
The set of opportunities being compared is the unchanged immediate serial lifecycle. This study changes entry timing/price only for diagnostic comparison; it does not generate a new alternate serial opportunity sequence.

## Required reporting
Each lane reports:
- qualifying signals and contracts;
- signal/contract retention vs immediate;
- true future-contract coverage;
- immediate qualification vs later actual pullback;
- actual entry delay;
- actual entry ASK and improvement vs candidate ASK;
- <=50c and 25-35c entry rates;
- time remaining at actual entry;
- scoreable +5c / +10c / +20c rates after actual entry;
- protected-exit rate;
- 1-lot and 10-lot taker/taker net protected-exit economics;
- opportunity-index breakdown.

## Prospective denominator
Only fully observed contracts whose first passive observation occurs at/after the later frozen cutoff may enter the future sample. Quiet fully observed contracts remain in the true contract denominator.

## Evidence readiness
Development review-size marker requires both:
- >=100 fully observed future contracts; and
- >=100 unchanged immediate serial opportunities.

Readiness is sample size only. It is not a performance PASS/FAIL gate.

## Selection discipline
- This first future sample cannot select a pullback lane.
- It cannot tune target prices or wait windows from the same sample.
- It cannot auto-promote a lane.
- Any later manually selected pullback rule must be frozen and evaluated on a **new fresh prospective certification window**.

## Safety
- No production logic changes.
- No signal suppression/rescue.
- No automatic orders.
- Existing Coverage Rescue, Economics Forward, Regime Forward, Candidate->Verify, Flip Risk, Watch->Exit, Density, FINAL, and EARLY streams remain independent.
