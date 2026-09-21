# BTC15 EARLY Settlement Runway Consensus V1 — preregistration

**Status:** FROZEN BEFORE SCORING  
**Mode:** READ-ONLY RESEARCH | SIGNAL ONLY | NO ORDERS

## Primary job

Predict the official final UP/DOWN settlement side of the same 15-minute Kalshi contract early enough to preserve favorable entry economics.

Primary success metric: **official settlement directional accuracy**.

Entry ASK, minutes remaining and coverage are co-primary usability constraints. Short-horizon +5/+10/+15/+20 excursions are not the success label for this study.

## Development source

Use only the already-examined historical development cache:

`union_optimizer_processed_snapshot_cache.csv`

This cache is development evidence only. No part of it will be called a new untouched holdout.

Do not access the post-fix clean validation window.

## Candidate: EARLY_SETTLEMENT_RUNWAY_CONSENSUS_V1

Evaluate snapshots in chronological order for each contract. Emit at most one EARLY call: the first row satisfying every rule below.

1. Remaining time is between **7.0 and 11.0 minutes**, inclusive.
2. Called side is the model's `preferred_side`.
3. The model preferred side must equal the side currently ahead of the fixed target:
   `preferred_side_num == current_side`.
4. Actual preferred-side Kalshi ASK is **<= 0.50**.
5. Model preferred fair is **>= 0.80**.
6. Model edge versus ASK is **>= 0.20**.
7. Volatility-normalized target runway:
   `dist_over_range5 >= 0.30`.
8. Recent target-side support must agree on all three short horizons:
   `support1 > 0`, `support2 > 0`, and `support3 > 0`.
9. Missing/non-finite required values fail closed.

No persistence wait, breakout/retest sequence, or post-entry excursion is required.

## Why this is a genuinely different hypothesis

Previous failed approaches centered on:
- one-minute fair-confidence classification;
- generic sub-minute ML;
- persistence/meta-model confirmation;
- PRE-WATCH/handoff threshold relaxation;
- breakout/retest/reclaim excursion behavior.

This hypothesis instead asks whether **settlement-side consensus plus normalized distance from the exact target relative to recent range** identifies rare early contracts where the final side is already structurally advantaged while Kalshi still offers <=50c.

## Frozen scoring

For the first qualifying row per contract report:
- contract
- timestamp
- side
- ASK
- fair
- edge
- minutes remaining
- target distance
- dist_over_range5
- official final side
- correct/wrong

Chronologically divide unique contracts into equal first/second development halves for stability reporting only.

Report:
- total calls and coverage
- correct / settled and accuracy
- first-half accuracy and call count
- second-half accuracy and call count
- UP/DOWN accuracy
- average/median ASK
- 25–35c share and <=50c share
- average/median minutes remaining

## Frozen advancement gate

Candidate advances to fresh validation only if ALL are true:
- total calls >= 15
- overall settlement accuracy >= 93%
- first-half accuracy >= 90%
- second-half accuracy >= 90%
- at least 5 calls in each half
- contract coverage >= 10%
- every entry <=50c
- average ASK <=40c
- average minutes remaining >=7.0

If the candidate fails, record NO STABLE CANDIDATE for this exact hypothesis. Do not search thresholds after seeing results.

## Guardrails

- Do not modify protected EARLY.
- Do not modify FINAL.
- Do not modify SCALP.
- Do not modify production, BRTI or Kalshi plumbing.
- Do not inspect the clean post-fix validation window.
- No auto-promotion.
- SIGNAL ONLY / NO ORDERS.
