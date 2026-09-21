# BTC15 EARLY final settlement accuracy audit

**EARLY FINAL-ACCURACY AUDIT COMPLETE**
**20/51 = 39.22% final-settlement directional accuracy.**

Exact saved candidate: `BREAKOUT_RETEST_RECLAIM_V1`. Source research commit: `543e7d960f1b8aeb9f7c7de2645f46d5b1e181ab`.
Every one of the original 51 calls is retained in its original order. No rule, threshold or call was changed.

| Primary metric | Result |
|---|---:|
| Officially settled / original calls | 51 / 51 |
| Correct | 20 |
| Wrong | 31 |
| Unresolved | 0 |
| Final directional accuracy | 20/51 = 39.22% |
| UP directional accuracy | 12/26 = 46.15% |
| DOWN directional accuracy | 8/25 = 32.00% |
| Mean / median entry ASK, all 51 | 29.27254902c / 31c |
| Entry ASK range / at or below 50c | 2.1–47c / 51 of 51 |
| Mean / median minutes remaining, all 51 | 8.70202614 / 8.91950000 |
| Mean / median seconds remaining, all 51 | 522.12156863 / 535.17000000 |
| Original eligible-contract coverage | 51/147 = 34.69% |

## Descriptive groups

| Group | Calls | Correct / settled = accuracy | Wrong | Unresolved |
|---|---:|---:|---:|---:|
| Below 25c (remaining calls) | 20 | 2/20 = 10.00% | 18 | 0 |
| 25–35c | 11 | 5/11 = 45.45% | 6 | 0 |
| 36–40c | 8 | 6/8 = 75.00% | 2 | 0 |
| 41–50c | 12 | 7/12 = 58.33% | 5 | 0 |
| At least 8 minutes remaining | 35 | 13/35 = 37.14% | 22 | 0 |
| 6 to under 8 minutes remaining | 16 | 7/16 = 43.75% | 9 | 0 |

Price bounds are literal inclusive cent bounds, using unrounded recorded ASK. No calls fall in the gaps between these requested bands. The below-25c row accounts for the other 20 calls. Time bands use original recorded seconds. Groups are descriptive only; no subset was selected for a new rule.

## Truth, provenance and scope

Truth comes from 51 fresh HTTP GET responses from the official Kalshi market endpoint, one for each exact ticker. Each response is finalized, has a settlement timestamp and an explicit yes/no result. YES maps to UP and NO maps to DOWN for these BTC-up binary contracts. This uses the official contract outcome, including its greater-or-equal rule; no settlement was inferred from BTC prices, bids or a model.
All 23 matching old-cache results agree with the fresh official responses. The remaining 28 now have official results. All 51 timestamps, asks and recorded seconds match their historical source snapshot rows. Each official open-to-close interval is 900 seconds; recorded time remaining differs from official close minus call timestamp by less than 0.011 seconds due to source rounding.
The original 147 eligible-contract denominator is taken unchanged from the committed membership evidence. The original nine incomplete-window contracts are not newly excluded by this audit. The detector was not rerun. Neither excursion statistics nor settlement performance were used to select calls.
This is a historical development-cohort audit, not untouched forward validation. The untouched clean post-fix window was not accessed. Production, FINAL, SCALP, BRTI, Kalshi plumbing and thresholds were not modified. SIGNAL ONLY / NO ORDERS.

## Reproduce

Run `python3 audit_settlements.py` in this directory to reproduce the table and summary offline from frozen inputs and captured official responses. It fails closed on cohort, fingerprint, identity, settlement or timing mismatches. `python3 fetch_official_settlements.py` is an optional fresh official GET-only retrieval for the same 51 tickers; it is not needed to reproduce this captured audit.
The inputs directory retains the exact committed calls and original membership file, the source fingerprints read from GitHub at the stated commit, the prior cache and the 51 matched historical source rows. `retrieval_manifest.json` stores request URLs, fetch times, HTTP metadata and raw-response SHA-256 values. `artifact_fingerprints.json` fingerprints every saved audit artifact except itself.

## Every original call

| # | Contract ID | EARLY timestamp (UTC) | Side | ASK (c) | Remaining (m:ss) | Official result / side | Verdict |
|---:|---|---|---|---:|---:|---|---|
| 1 | KXBTC15M-26SEP030145-45 | 2026-09-03T05:34:55.101335Z | DOWN | 14 | 10:04.90 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030145-45) | WRONG |
| 2 | KXBTC15M-26SEP030230-30 | 2026-09-03T06:20:51.180596Z | DOWN | 24 | 9:08.82 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030230-30) | WRONG |
| 3 | KXBTC15M-26SEP030245-45 | 2026-09-03T06:35:46.594401Z | DOWN | 41 | 9:13.41 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030245-45) | WRONG |
| 4 | KXBTC15M-26SEP030545-45 | 2026-09-03T09:38:27.608974Z | DOWN | 47 | 6:32.39 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030545-45) | CORRECT |
| 5 | KXBTC15M-26SEP030615-15 | 2026-09-03T10:08:58.293593Z | DOWN | 20 | 6:01.71 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030615-15) | CORRECT |
| 6 | KXBTC15M-26SEP030715-15 | 2026-09-03T11:07:24.111563Z | DOWN | 29 | 7:35.89 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030715-15) | WRONG |
| 7 | KXBTC15M-26SEP030730-30 | 2026-09-03T11:20:54.546378Z | DOWN | 11 | 9:05.45 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030730-30) | WRONG |
| 8 | KXBTC15M-26SEP030800-00 | 2026-09-03T11:52:05.266282Z | UP | 41 | 7:54.73 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030800-00) | CORRECT |
| 9 | KXBTC15M-26SEP030900-00 | 2026-09-03T12:49:36.611366Z | DOWN | 26 | 10:23.39 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030900-00) | WRONG |
| 10 | KXBTC15M-26SEP030915-15 | 2026-09-03T13:08:27.704828Z | UP | 12 | 6:32.30 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030915-15) | WRONG |
| 11 | KXBTC15M-26SEP030945-45 | 2026-09-03T13:34:33.368018Z | DOWN | 22 | 10:26.63 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP030945-45) | WRONG |
| 12 | KXBTC15M-26SEP031000-00 | 2026-09-03T13:51:58.854484Z | DOWN | 41 | 8:01.15 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031000-00) | CORRECT |
| 13 | KXBTC15M-26SEP031015-15 | 2026-09-03T14:08:34.197901Z | DOWN | 37 | 6:25.80 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031015-15) | WRONG |
| 14 | KXBTC15M-26SEP031445-45 | 2026-09-03T18:34:17.996439Z | DOWN | 41 | 10:42.00 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031445-45) | WRONG |
| 15 | KXBTC15M-26SEP031515-15 | 2026-09-03T19:04:18.253961Z | UP | 44 | 10:41.75 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031515-15) | WRONG |
| 16 | KXBTC15M-26SEP031545-45 | 2026-09-03T19:38:38.764193Z | UP | 7.2 | 6:21.24 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031545-45) | WRONG |
| 17 | KXBTC15M-26SEP031600-00 | 2026-09-03T19:50:33.889840Z | UP | 35 | 9:26.11 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031600-00) | CORRECT |
| 18 | KXBTC15M-26SEP031615-15 | 2026-09-03T20:04:59.428818Z | UP | 28 | 10:00.57 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031615-15) | WRONG |
| 19 | KXBTC15M-26SEP031630-30 | 2026-09-03T20:20:19.760799Z | UP | 43 | 9:40.24 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031630-30) | CORRECT |
| 20 | KXBTC15M-26SEP031730-30 | 2026-09-03T21:20:00.797411Z | UP | 36 | 9:59.20 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031730-30) | CORRECT |
| 21 | KXBTC15M-26SEP031745-45 | 2026-09-03T21:38:56.367993Z | DOWN | 33 | 6:03.63 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031745-45) | CORRECT |
| 22 | KXBTC15M-26SEP031845-45 | 2026-09-03T22:36:14.965432Z | UP | 30 | 8:45.03 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031845-45) | CORRECT |
| 23 | KXBTC15M-26SEP031945-45 | 2026-09-03T23:37:03.354472Z | UP | 34 | 7:56.65 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP031945-45) | WRONG |
| 24 | KXBTC15M-26SEP032345-45 | 2026-09-04T03:36:06.641836Z | UP | 39 | 8:53.36 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP032345-45) | CORRECT |
| 25 | KXBTC15M-26SEP040100-00 | 2026-09-04T04:49:38.823245Z | DOWN | 44 | 10:21.18 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP040100-00) | WRONG |
| 26 | KXBTC15M-26SEP040130-30 | 2026-09-04T05:20:29.089844Z | DOWN | 19 | 9:30.91 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP040130-30) | WRONG |
| 27 | KXBTC15M-26SEP040845-45 | 2026-09-04T12:38:19.869591Z | UP | 2.1 | 6:40.13 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP040845-45) | WRONG |
| 28 | KXBTC15M-26SEP040900-00 | 2026-09-04T12:49:45.259126Z | UP | 20 | 10:14.74 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP040900-00) | WRONG |
| 29 | KXBTC15M-26SEP040945-45 | 2026-09-04T13:34:27.433557Z | DOWN | 46 | 10:32.57 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP040945-45) | WRONG |
| 30 | KXBTC15M-26SEP041000-00 | 2026-09-04T13:52:52.859744Z | DOWN | 23 | 7:07.14 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041000-00) | CORRECT |
| 31 | KXBTC15M-26SEP041015-15 | 2026-09-04T14:06:13.250469Z | DOWN | 21 | 8:46.75 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041015-15) | WRONG |
| 32 | KXBTC15M-26SEP041030-30 | 2026-09-04T14:21:23.972122Z | UP | 13 | 8:36.03 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041030-30) | WRONG |
| 33 | KXBTC15M-26SEP041045-45 | 2026-09-04T14:36:09.745959Z | DOWN | 34 | 8:50.25 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041045-45) | CORRECT |
| 34 | KXBTC15M-26SEP041100-00 | 2026-09-04T14:52:15.148739Z | UP | 24 | 7:44.85 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041100-00) | WRONG |
| 35 | KXBTC15M-26SEP041130-30 | 2026-09-04T15:20:06.103438Z | DOWN | 31 | 9:53.90 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041130-30) | WRONG |
| 36 | KXBTC15M-26SEP041145-45 | 2026-09-04T15:35:21.609963Z | UP | 39 | 9:38.39 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041145-45) | CORRECT |
| 37 | KXBTC15M-26SEP041200-00 | 2026-09-04T15:50:32.190674Z | UP | 19 | 9:27.81 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041200-00) | WRONG |
| 38 | KXBTC15M-26SEP041215-15 | 2026-09-04T16:05:28.117783Z | UP | 46 | 9:31.88 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041215-15) | CORRECT |
| 39 | KXBTC15M-26SEP041245-45 | 2026-09-04T16:37:09.219406Z | DOWN | 6.6 | 7:50.78 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041245-45) | WRONG |
| 40 | KXBTC15M-26SEP041300-00 | 2026-09-04T16:51:29.336389Z | UP | 35 | 8:30.66 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041300-00) | WRONG |
| 41 | KXBTC15M-26SEP041345-45 | 2026-09-04T17:38:05.588712Z | UP | 22 | 6:54.41 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041345-45) | WRONG |
| 42 | KXBTC15M-26SEP041430-30 | 2026-09-04T18:21:16.822704Z | DOWN | 16 | 8:43.18 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041430-30) | WRONG |
| 43 | KXBTC15M-26SEP041445-45 | 2026-09-04T18:35:27.045653Z | DOWN | 15 | 9:32.95 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041445-45) | WRONG |
| 44 | KXBTC15M-26SEP041630-30 | 2026-09-04T20:20:47.330944Z | DOWN | 37 | 9:12.67 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041630-30) | CORRECT |
| 45 | KXBTC15M-26SEP041645-45 | 2026-09-04T20:38:52.973670Z | DOWN | 38 | 6:07.03 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041645-45) | CORRECT |
| 46 | KXBTC15M-26SEP041845-45 | 2026-09-04T22:36:04.834405Z | UP | 39 | 8:55.17 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP041845-45) | WRONG |
| 47 | KXBTC15M-26SEP042215-15 | 2026-09-05T02:05:00.264108Z | UP | 36 | 9:59.74 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP042215-15) | CORRECT |
| 48 | KXBTC15M-26SEP050015-15 | 2026-09-05T04:04:53.202368Z | UP | 22 | 10:06.80 | [no / DOWN](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP050015-15) | WRONG |
| 49 | KXBTC15M-26SEP050130-30 | 2026-09-05T05:20:24.726944Z | UP | 42 | 9:35.27 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP050130-30) | CORRECT |
| 50 | KXBTC15M-26SEP050200-00 | 2026-09-05T05:51:20.897107Z | UP | 27 | 8:39.10 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP050200-00) | CORRECT |
| 51 | KXBTC15M-26SEP050245-45 | 2026-09-05T06:38:12.441633Z | UP | 41 | 6:47.56 | [yes / UP](https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC15M-26SEP050245-45) | CORRECT |

**EARLY FINAL-ACCURACY AUDIT COMPLETE**
**20/51 = 39.22%.**
