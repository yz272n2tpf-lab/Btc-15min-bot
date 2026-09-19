# BTC15 MAIN RUNTIME ARTIFACT CANARY — FROZEN ACCEPTANCE CONTRACT
Date: 2026-09-18
Scope: cost/speed optimization only. No strategy change.

## Protected semantics
- Existing Kalshi authentication/read-only market access.
- Exact active KXBTC15M contract selection, open/close, target/start alignment.
- Existing BRTI freshness/authority and +/-$11 wait-zone behavior.
- Existing EARLY, FINAL, scalp/reversal, ladder, flip-risk and manual execution semantics.
- Signal only. NO ORDERS.

## Models that may be serialized, not changed
A. General 15m RF:
- features: return_3, body_strength, trend_5_20, sma_distance, acceleration, momentum_3
- RandomForestClassifier(n_estimators=1200,max_depth=8,random_state=42,class_weight=balanced)
- fitting chronology/data boundary must be frozen and hashed.
B. Target-aware fair model:
- exact existing 20-feature order from V4.6
- RF(n_estimators=900,max_depth=9,min_samples_leaf=12,class_weight=balanced,random_state=42,n_jobs=-1)
- exact 50% training / next 20% sigmoid calibration chronology.
- LogisticRegression(solver=lbfgs,C=1.0,max_iter=1000,random_state=42)
- validation/holdout remains excluded from fitting.

## Live runtime optimization
- Load certified fitted artifacts + metadata/hashes.
- Compute current causal features exactly as protected code.
- Do NOT download/retrain 60-day model history in live critical path.
- Do NOT rebuild historical fair snapshots/retrain fair RF+sigmoid in live critical path.
- Preserve only current history window actually required to compute live features.

## Canary acceptance: ALL required
At identical captured input boundaries:
1. exact general RF class prediction.
2. predict_proba absolute difference <=1e-12.
3. exact fair preferred side; fair up/down/flip/stay abs diff <=1e-12.
4. exact EARLY status/side/ask/fair/edge/reason.
5. exact FINAL ready/status/side/confidence/source/reason.
6. exact active Kalshi ticker/open/close/target and seconds/minutes-left interpretation.
7. exact BRTI ready/side/gap/freshness decision.
8. exact ladder/flip-risk/scalp authority boundaries.
9. NO ORDERS / manual execution only.
10. state publication freshness no worse than protected runtime.
11. source->compute->published-state latency no worse; target materially faster startup/recovery.
12. materially lower RAM/CPU; no new public internal egress.

Any semantic/freshness/latency mismatch = FAIL CLOSED. Protected main remains unchanged.
