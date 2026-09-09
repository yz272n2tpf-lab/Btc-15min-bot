# Scalp V6 Hypothesis (research only)

Do not deploy until V5 has a forward sample. This is a pre-registered hypothesis based on V4 failures/wins so we avoid tuning after seeing the next result.

## What current V4 data suggests
- Very low asks around 1–3c often behave like dead-side noise rather than useful reversal/scalp opportunity.
- Several 14–23c candidates produced meaningful +10c expansions with relatively small adverse movement.
- Some 35–43c candidates failed or suffered materially larger adverse movement.
- Strong short-term impulse alone is not enough; persistence and broader structure matter.

## V6 candidate guardrails to test only if V5 is still too noisy
1. Keep V5 persistence + 30s structure checks.
2. Add a soft opportunity-zone preference, not a fixed entry requirement:
   - preferred: 7–30c
   - caution: 31–45c
   - reject <=2c
3. Require stronger asymmetry for expensive entries (>30c): higher 15s persistence and lower recent Kalshi ask movement.
4. Add a pre-trigger deterioration guard: reject when the proposed side has made a fresh 30s low while BTC/BRTI impulse is only briefly positive.
5. Keep >=120s time-left guard.
6. Score UP and DOWN separately; do not assume symmetric thresholds.

## Promotion logic
V6 should only be built/deployed if V5 fails the existing promotion gate on forward data. If V5 passes, prefer the simpler V5 model.
