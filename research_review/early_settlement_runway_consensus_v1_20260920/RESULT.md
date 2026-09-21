# EARLY_SETTLEMENT_RUNWAY_CONSENSUS_V1 — development result

**Decision: REJECT / NO STABLE CANDIDATE for this exact hypothesis.**

Preregistration commit: `7f88e71cd8d2edd79a25f6808ebba62d40c6ee81`

Development source: `union_optimizer_processed_snapshot_cache.csv` (199 historical contracts; already-examined development evidence only).

No clean post-fix validation data was accessed.

## Result

- Calls: **16 / 199**
- Coverage: **8.04%**
- Correct: **12 / 16**
- Official settlement accuracy: **75.00%**
- First chronological half: **6 / 8 = 75.00%**
- Second chronological half: **6 / 8 = 75.00%**
- UP: **11 / 13**
- DOWN: **1 / 3**
- Average / median ASK: **44.69c / 47c**
- Ideal 25–35c: **1 / 16**
- Every entry <=50c: yes
- Average / median minutes remaining: **9.375 / 10.0**

## Frozen advancement gate

- total calls >=15: PASS
- overall settlement accuracy >=93%: **FAIL**
- first-half accuracy >=90%: **FAIL**
- second-half accuracy >=90%: **FAIL**
- >=5 calls in each half: PASS
- contract coverage >=10%: **FAIL**
- every entry <=50c: PASS
- average ASK <=40c: **FAIL**
- average minutes remaining >=7.0: PASS

Because the frozen rule failed, no threshold changes or subset search were performed afterward.

## Interpretation

The combined model/current-target-side/runway/momentum consensus did not solve the EARLY settlement problem. It was early enough in time but too expensive on average, too sparse, and materially below the required final-settlement accuracy.

This exact hypothesis is closed.

SIGNAL ONLY / NO ORDERS.
