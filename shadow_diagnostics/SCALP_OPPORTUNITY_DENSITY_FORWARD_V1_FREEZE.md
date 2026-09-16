# BTC15 Scalp Opportunity Density Forward V1 — Prospective Freeze

**SHADOW ONLY · SIGNAL ONLY · DESCRIPTIVE ONLY · NO ORDERS · NO AUTO-PROMOTION**

## Purpose
Measure how frequently the unchanged serial scalp lifecycle produces usable opportunities on a true prospective 15-minute contract denominator.

This study answers four separate questions without blending them:
1. **Any-opportunity coverage:** did a fully observed future contract produce at least one completed serial scalp opportunity?
2. **Opportunity density:** how many contracts produced 0 / 1 / 2 / 3 / 4+ completed opportunities?
3. **Actionable-price coverage:** did the contract produce at least one opportunity at <=50c?
4. **Ideal-price coverage:** did the contract produce at least one opportunity in the 25-35c target band?

## Denominator
The denominator is **all fully observed future contracts first seen at or after the later frozen cutoff** using the existing passive-contract universe logic.

A quiet fully observed contract remains in the denominator with opportunity count **zero**. It is never dropped merely because no candidate fired.

Mid-contract and pre-cutoff contracts are excluded.

## Signal lifecycle
- The existing serial scalp opportunity builder is reused unchanged.
- Existing baseline minimum seconds-left remains 120 seconds.
- Existing failed-prearm/protected-exit serial reset behavior is unchanged.
- Up to 4+ opportunities may be observed; the ledger does not impose a new cap.
- No signal is filtered, suppressed, rescued, repriced, or promoted by this ledger.

## Entry-economics bands
These are descriptive user-goal bands, not signal filters:
- **Ideal:** 25-35c inclusive.
- **Good / actionable:** 36-50c inclusive.
- **Affordable:** <=50c.

The ledger reports true-contract coverage for any opportunity, <=50c opportunity, and 25-35c opportunity separately so raw frequency cannot hide poor entry economics.

## Timing zones
Fixed seconds-left bands:
- 15-12m: 720-900 seconds left
- 12-9m: 540-<720
- 9-6m: 360-<540
- 6-3m: 180-<360
- 3-2m: 120-<180

Cumulative coverage is also reported by 12m, 9m, 6m, 3m, and 2m left.

## Movement context
+5c / +10c / +20c rates are reported descriptively overall, by timing zone, and by opportunity index. They are **not** density gates and cannot remove quiet or losing contracts from the denominator.

## Evidence readiness
A review-size marker requires >= **100 fully observed future contracts**.

This means only that the prospective density sample is large enough for manual review. It is **not** a performance PASS/FAIL threshold and cannot promote any production change.

## Safety
- No production logic changes.
- No dashboard behavior changes.
- No threshold selection.
- No signal filtering/suppression/rescue.
- No automatic promotion.
- No orders.
- Existing Coverage Rescue, Economics Forward, Regime Forward, Candidate->Verify, Flip Risk, Watch->Exit, FINAL, and EARLY collectors remain independent.
