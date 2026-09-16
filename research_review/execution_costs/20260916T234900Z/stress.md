# Extra execution-cost sensitivity

Status: **DESCRIPTIVE_SENSITIVITY_ONLY**. No winner selected.

Captured UTC: 2026-09-16T23:49:00.181854+00:00
Full contracts: 5; serial opportunities: 8.

One-lot taker/taker model. Values are conditional mean cents per contract on fee-scored protected exits only.
Column headings are EXTRA round-trip cost: 0, 1, 2, or 5 cents at EACH side (entry plus exit).

| Family / lane | Entries | Scored exits / contracts | No exit / missing fee net | +0c | +2c | +4c | +10c |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp2_economics_v2 / CONTROL_V1_SCALP2 | 2 | 2 / 2 | 0 / 0 | 8.500 | 6.500 | 4.500 | -1.500 |
| scalp2_economics_v2 / AFFORDABLE_LE50 | 0 | 0 / 0 | 0 / 0 | — | — | — | — |
| scalp2_economics_v2 / EARLY_AFFORDABLE | 0 | 0 / 0 | 0 / 0 | — | — | — | — |
| scalp2_economics_v2 / STRONG_AFFORDABLE | 0 | 0 / 0 | 0 / 0 | — | — | — | — |
| candidate_verify_v2 / V1_IMMEDIATE | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| candidate_verify_v2 / V1_FIXED_5S | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| candidate_verify_v2 / V1_FIXED_10S | 8 | 4 / 2 | 4 / 0 | -1.250 | -3.250 | -5.250 | -11.250 |
| candidate_verify_v2 / V1_FIXED_15S | 8 | 4 / 2 | 4 / 0 | -1.250 | -3.250 | -5.250 | -11.250 |
| candidate_verify_v2 / V1_FIXED_30S | 8 | 1 / 1 | 7 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |
| candidate_verify_v2 / V2_DYNAMIC_CAUSAL | 2 | 1 / 1 | 1 / 0 | 16.000 | 14.000 | 12.000 | 6.000 |
| watch_exit_v2 / V1_1C | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| watch_exit_v2 / V1_2C | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| watch_exit_v2 / V1_3C | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| watch_exit_v2 / V2_CONFIRMED_HALF_C | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| watch_exit_v2 / V2_FALLING_TREND | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| selective_pullback_v2 / V1_IMMEDIATE_CONTROL | 8 | 4 / 2 | 4 / 0 | 1.250 | -0.750 | -2.750 | -8.750 |
| selective_pullback_v2 / V1_LE50_30S | 2 | 1 / 1 | 1 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |
| selective_pullback_v2 / V1_LE50_60S | 3 | 1 / 1 | 2 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |
| selective_pullback_v2 / V1_LE40_30S | 2 | 1 / 1 | 1 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |
| selective_pullback_v2 / V1_LE40_60S | 2 | 1 / 1 | 1 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |
| selective_pullback_v2 / V1_LE35_30S | 1 | 0 / 0 | 1 / 0 | — | — | — | — |
| selective_pullback_v2 / V1_LE35_60S | 1 | 0 / 0 | 1 / 0 | — | — | — | — |
| selective_pullback_v2 / V2_BALANCED | 3 | 2 / 2 | 1 / 0 | 3.500 | 1.500 | -0.500 | -6.500 |
| selective_pullback_v2 / V2_PRICE_DISCIPLINED | 2 | 1 / 1 | 1 / 0 | -9.000 | -11.000 | -13.000 | -19.000 |

Ten-lot per-contract values, positive/zero/negative exit counts, omissions and all 28 paired comparisons are in stress.json.

## Limits

- Conditional on observed protected exits with finite fee-net values; missing outcomes are not zero profit.
- Not realized profit, total portfolio P&L, a win rate, an executable backtest, or a manual-fill guarantee.
- A fixed extra cost does not model reaction delay, market depth, spread changes, path-dependent exits, or repriced fees.
- Equal costs cancel in a paired net delta; these scenarios cannot establish comparative policy superiority.
- Watch warnings do not change frozen exits here; no economics benefit is credited for earlier warnings.
- Repeated opportunities within a contract and copied opportunities across lanes are not independent evidence; never sum lanes.
- The review floor and descriptive stress grid do not permit same-sample selection or promotion; later certification remains separate.

## CURRENT STATE

- CONTROL: Frozen source evidence is read only; no collector changes.
- NEW SHADOW: Offline sensitivity arithmetic only; not deployed or used by live signals.
- BLOCKED: Fill/latency performance and policy superiority are not established.
- NEXT STEP: Repeat on later coherent evidence without adjusting the frozen experiment.
