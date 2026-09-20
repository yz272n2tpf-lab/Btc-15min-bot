# BTC15 Ladder Development Candidate — 2026-09-20

STATUS: FROZEN DEVELOPMENT CANDIDATE FOR CLEAN FORWARD VALIDATION.
SIGNAL ONLY. MANUAL EXECUTION. NO ORDERS.
Production main is untouched.

## 1. Movement detector
UNCHANGED.

- Detect the developing BTC/BRTI move first.
- Kalshi cents do not create, strengthen, weaken, or reject the movement setup.
- Preserve full 15-minute scanning, UP/DOWN reversals, and serial opportunities.
- Preserve ENDED_UNARMED lifecycle behavior.
- Do not add btc30>=20, normalized-momentum gates, strict 15s BRTI/BTC parity,
  or 1-4 second micro-confirmation. Those studies did not pass.

## 2. Value-first actionable entry guidance
Once the movement setup qualifies:

- If executable ASK <=50c: actionable value entry at the actual ASK.
- If ASK >50c: keep the movement signal visible as WATCH / WAIT FOR VALUE.
- Watch for a maximum of 30 seconds for the first actual ASK <=50c.
- If no <=50c ASK arrives in that 30-second value window, do not issue an
  actionable entry for that candidate. This is an execution/value decision,
  not a detector rejection.
- Actual ASK is entry cost; future executable BID scores the path.

V2 evidence snapshot:
- code SHA 7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f
- source SHA 8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a
- 352 full contracts / 563 serial opportunities
- chosen lane V1_LE50_30S: 321 entries / 236 contracts
- avg ASK 32.01c; median 34c
- +5c 82.87%; +10c 66.36%; +20c 42.06%
- protected exit observed 63.24%

Why 30 seconds:
- extending to 60s added only 12 entries; avg ASK 45.25c, +10c 16.67%,
  +20c 8.33%, zero protected exits.
- V2_PRICE_DISCIPLINED added four entries beyond the 30s lane; avg ASK 49.25c,
  +10c 25%, +20c 0%, zero protected exits.
- V2_BALANCED added 95 expensive entries; avg ASK 68.17c, +10c 64.21%,
  +20c 30.53%, protected-exit rate 46.32%, protected-exit one-lot
  taker/taker average net -1.98c.

## 3. Entry-price display tiers
TELEMETRY / USER GUIDANCE ONLY. Not detector gates.

On the frozen 30s value lane:
- UNDER 15c: 40 signals, avg 8.25c; +10c 27.5%; +20c 7.5%.
  Label as very-cheap / higher-variance value, not higher-confidence.
- 15c to under 25c: 44 signals, avg 19.5c; +10c 59.09%; +20c 38.64%.
- 25c to 35c: 97 signals, avg 30.72c; +10c 68.04%; +20c 48.45%.
  Keep IDEAL VALUE label.
- over 35c to 50c: 140 signals, avg 43.63c; +10c 78.57%; +20c 48.57%.
  Keep ACCEPTABLE / GOOD label.
- >50c: WATCH / WAIT FOR VALUE for up to 30s; do not call it a bad move solely
  because of price.

## 4. Protection / exit
KEEP CURRENT CONTROL UNCHANGED:

- arm protection at +5c executable gain;
- protected EXIT at first observed 4c giveback from running executable peak.

Value-first protection study:
- 609 value-first entries total; development 373 / holdout 236.
- development avg entry 29.22c; +10c 64.34%; +20c 38.61%.
- holdout avg entry 30.14c; +10c 64.83%; +20c 41.95%.
- CONTROL +5/4 average realized: dev +9.07c; holdout +8.85c.
- no 2c/3c/5c/6c giveback or stepped 4/3/2 version met the predeclared
  development shortlist criteria strongly enough to replace control.

Therefore protection is NOT retuned today.

## 5. What clean forward validation must judge
The post-final-infrastructure clean window is untouched by these development
decisions. Judge this exact frozen candidate on:
- actionable contract/opportunity coverage;
- average/median actual ASK;
- <=35c and <=50c entry shares;
- +5/+10/+20 executable BID follow-through;
- adverse excursion;
- protected-exit behavior and realized capture;
- timing / seconds left;
- stability across enough new full contracts.

No mid-window retuning.
No automatic promotion.
NO ORDERS.
