# V2 read-only review

Captured: 2026-09-16T22:30:13.718240+00:00

Status: **WAITING_FOR_FULL_CONTRACT**. Winner selected: **No**. No promotion.

Eligible full contracts: **0**; serial signals: **0**.
Remaining to overall review floor: 100 contracts / 100 signals. Per-lane sufficiency is not established.

All price/economics values below are cents per contract. Net deltas use the both-protected-exit subset.

| Family / experiment | Control | Matched entries | Both exits / contracts | Control-only entries | Entry improvement ¢ | 1-lot net Δ ¢ | 10-lot net Δ ¢ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp2_economics_v2 / AFFORDABLE_LE50 | CONTROL_V1_SCALP2 | 0 | 0 / 0 | 0 | — | — | — |
| scalp2_economics_v2 / EARLY_AFFORDABLE | CONTROL_V1_SCALP2 | 0 | 0 / 0 | 0 | — | — | — |
| scalp2_economics_v2 / STRONG_AFFORDABLE | CONTROL_V1_SCALP2 | 0 | 0 / 0 | 0 | — | — | — |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | V1_IMMEDIATE | 0 | 0 / 0 | 0 | — | — | — |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | V1_FIXED_5S | 0 | 0 / 0 | 0 | — | — | — |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | V1_FIXED_10S | 0 | 0 / 0 | 0 | — | — | — |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | V1_FIXED_15S | 0 | 0 / 0 | 0 | — | — | — |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | V1_FIXED_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_IMMEDIATE_CONTROL | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE50_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE50_60S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE40_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE40_60S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE35_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_BALANCED | V1_LE35_60S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_IMMEDIATE_CONTROL | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE50_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE50_60S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE40_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE40_60S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE35_30S | 0 | 0 / 0 | 0 | — | — | — |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | V1_LE35_60S | 0 | 0 / 0 | 0 | — | — | — |

| Watch experiment | Control | Paired exits / contracts | Lead improvement seconds | ≥5s earlier / later | Unresolved warnings, V2 / V1 |
| --- | --- | ---: | ---: | ---: | ---: |
| V2_CONFIRMED_HALF_C | V1_1C | 0 / 0 | — | 0 / 0 | 0 / 0 |
| V2_CONFIRMED_HALF_C | V1_2C | 0 / 0 | — | 0 / 0 | 0 / 0 |
| V2_CONFIRMED_HALF_C | V1_3C | 0 / 0 | — | 0 / 0 | 0 / 0 |
| V2_FALLING_TREND | V1_1C | 0 / 0 | — | 0 / 0 | 0 / 0 |
| V2_FALLING_TREND | V1_2C | 0 / 0 | — | 0 / 0 | 0 / 0 |
| V2_FALLING_TREND | V1_3C | 0 / 0 | — | 0 / 0 | 0 / 0 |

## Interpretation limits

- Same-window independent replays anchored to V1 serial opportunities, not executable portfolio P&L.
- Matched protected-exit averages exclude unresolved/unprotected outcomes; omissions and unique contracts are shown separately.
- Source audit does not include full raw paths or individual contract first-seen timestamps; causal replay and cutoff eligibility cannot be independently re-proved from these endpoints.
- No winner ranking, statistical significance claim, confidence bound, promotion or certification decision is made.
- A zero conditional delta for a SCALP-2 filter means retained trades use the same economics; omitted trades and coverage still matter.

Detailed omissions, protected-exit availability and new-high recovery proxy counts/rates are in review.json. Raw API responses are preserved in bundle.json.

## CURRENT STATE

- CONTROL: Read-only comparison; no collector writes.
- NEW SHADOW: Existing V2 snapshot inspected; this tool is offline and undeployed.
- BLOCKED: Further evidence is required before any prospective certification consideration.
- NEXT STEP: Review a later coherent snapshot without changing the frozen experiment.
