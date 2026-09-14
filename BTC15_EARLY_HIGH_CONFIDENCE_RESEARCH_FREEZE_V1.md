# BTC15 EARLY High-Confidence Research Freeze V1

**Status:** FROZEN BEFORE HISTORICAL SCORING  
**Mode:** READ-ONLY RESEARCH | SIGNAL ONLY | NO ORDERS

## Goal

Test whether a **stricter label inside the already-protected Tier-1 EARLY opportunity** can raise directional reliability toward the user's 93–95% target without destroying the economic entry and timing that make Tier-1 useful.

This research does **not** weaken, replace, or retune protected Tier-1.

Protected Tier-1 remains:

- ask <=45c
- fair >=75%
- edge >=8pp
- 2–10 minutes remaining
- absolute exact Kalshi target gap >=$25
- first qualifying row per contract

Protected historical reference: 20/22 = 90.9% report-half accuracy, 22% coverage, 31.9c average ask, 34c median ask, 6.09 minutes remaining on average.

## Important data-status rule

The existing 199-contract replay cache has already been examined in multiple EARLY studies. Therefore **no portion of this cache will be described as a new untouched holdout for this phase.**

Historical scoring is development/research evidence only. Any selected higher-confidence candidate must be frozen and then earn a fresh forward confirmation before it can become an actionable/high-confidence label.

## Frozen candidate families

Every candidate is a subset/confirmation of protected Tier-1. No candidate may create an EARLY action that protected Tier-1 itself would reject.

### Same-row stricter subsets

1. `FAIR80`: Tier-1 + preferred fair >=80%
2. `FAIR85`: Tier-1 + preferred fair >=85%
3. `EDGE10`: Tier-1 + edge >=10pp
4. `GAP35`: Tier-1 + abs target gap >=$35
5. `CURRENT_SIDE`: Tier-1 + preferred side = current target side
6. `FAIR80_CURRENT`: Tier-1 + fair >=80% + preferred side=current side
7. `FAIR80_EDGE10`: Tier-1 + fair >=80% + edge >=10pp
8. `FAIR80_GAP35`: Tier-1 + fair >=80% + gap >=$35
9. `FAIR80_CURRENT_EDGE10`: Tier-1 + fair >=80% + current-side agreement + edge >=10pp
10. `FAIR85_CURRENT`: Tier-1 + fair >=85% + current-side agreement

### Confirmation subsets

11. `PERSIST_30_90`: after the first protected Tier-1 row, use the first later snapshot 30–90 seconds afterward only if it still satisfies every protected Tier-1 gate, remains on the same preferred side, and ask is still <=45c. The confirmation row is the scored/action row.

12. `STRENGTHEN_30_90`: same as `PERSIST_30_90`, plus confirmation fair must be >= initial fair and confirmation edge must be >= initial edge. The confirmation row is the scored/action row.

No other thresholds or combinations may be added after results are seen in V1.

## Frozen historical research acceptance gate

A candidate is eligible to become a **forward-test candidate only** if all are true on the existing historical cache:

- combined calls >=15
- chronological first-half calls >=6
- chronological second-half calls >=6
- combined directional accuracy >=93%
- first-half accuracy >=90%
- second-half accuracy >=90%
- average ask <=45c
- median ask <=45c
- average time remaining >=5.0 minutes

If multiple candidates pass, rank by:

1. most combined calls
2. higher combined accuracy
3. lower average ask
4. more average time remaining

The protected Tier-1 baseline is always reported but is not eligible to be 'selected' as the new stricter layer.

If no candidate passes, **scratch the higher-confidence sub-tier rather than moving the thresholds after seeing results.** Protected Tier-1 remains unchanged.

## Fresh-forward requirement

Historical passing is not promotion.

Before any higher-confidence label is used live:

1. freeze the exact selected candidate,
2. collect at least 20 new unique qualifying contracts with no rule changes,
3. report accuracy, calls/coverage, average/median ask, average/median time, UP/DOWN balance, and relation to protected Tier-1.

Decision convention:

- 19/20 or better (>=95%) with preserved <=45c economics: may earn provisional higher-confidence status.
- 18/20 (90%): insufficient resolution; continue unchanged to 30 unique qualifiers. At 30, require at least 28/30 = 93.3%.
- 17/20 or worse: scratch the higher-confidence candidate.

These are research decision gates, not guarantees of future performance.

## Guardrails

- Protected Tier-1 remains actionable exactly as already validated.
- This high-confidence study cannot reduce Tier-1 coverage; it may only add a confidence label to a subset.
- No candidate may allow ask >45c.
- Do not tune using the historical result after this freeze.
- No new FINAL rule.
- No change to generalized SCALP.
- No auto-trading / no orders.
