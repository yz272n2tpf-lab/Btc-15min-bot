# BTC15 finish-line research preregistration — 2026-09-21

Status: one hypothesis per lane, fixed before this pass's outcome scoring. Research only. SIGNAL ONLY / NO ORDERS. No production, FINAL, infrastructure, BRTI, service or dashboard changes.

## Authority and data boundary
Protected EARLY reference is unchanged: preferred ASK <=45c, fair >=75%, edge >=8pp, 2–10 minutes remaining, absolute target gap >=$25, first qualifying row per contract. Source: CURRENT_PROJECT_STATE_KALSHI_BTC15.md at d31922b4c72d5bc7efa590eb1b3c4f86da71fc0d. EARLY excursion semantics come from BTC15_EARLY_EXCURSION_FORWARD_FREEZE_20260915.md.
SCALP lifecycle authority: BTC15_SCALP_SERIAL_LIFECYCLE_CHECKPOINT_20260915.md and BTC15_SCALP_RESEARCH_DECISION_LOG_20260915.md at the same source revision. Newer diagnostic context: BTC15_EARLY_SCALP_DIAGNOSTIC_CHECKPOINT_20260920.md at 38a14fc8085090f2965bf93cf831646a1b5aa6c2.

Allowed development inputs, exact SHA256:
- kalshi_scalp_shadow_snapshots_v1.csv: d7c2dd36a5e0be197f5304fff0117f6fe340924e2436c60daf70806d84b00c4b; 12,273,752 bytes; September 3–5; 156 contracts.
- kalshi_early_conf_shadow_v1_2.csv: b49b55215a0ae1704cdea1f9aaf1f5db2edcab72eaf3576d68fbae3aa77a43a2; September 3–5; 101 contracts; protected-reference comparator only.
- subminute_official_truth_cache.csv: 50915c34044658c0a9871c04a57290bb3e7987ef8414aa51cc48ef79f927fab7; secondary settlement context only; missing truth never drops an excursion.
- scalp_move_shadow_v1_events.csv: 47148d03418810fb96985d8f5db9e5f062d963b42fac8cfd062599118d43c437; 42,518,872 bytes; September 13–14; 91 observed contracts, 242 CANDIDATE, 40,877 PATH, 240 RESULT, 27,601 SNAPSHOT records. This is a separate older development cohort, NOT the unrecovered 352/563 archive with source hash 8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a.

Only these exact files may be read for scoring. Fail on hash mismatch or timestamps at/after 2026-09-20T19:05:17.147189Z. No clean raw backup, endpoint, performance log, or validation result will be opened. Entire allowed cohorts are development, including previously used old holdouts; chronological thirds are descriptive stability blocks, never new independent validation.

## EARLY: BREAKOUT_RETEST_RECLAIM_V1
One causal sequence hypothesis. Evaluate both BTC directions using signed BTC price:
1. During 6–11 minutes remaining, start an episode when price exceeds the highest signed price observed in the preceding 30 seconds AND side-aligned recorded BTC15 >=$8. Require at least 25 seconds of prior within-contract history and no gap exceeding 10 seconds. Starting an episode does not depend on Kalshi price.
2. Save that prior high as the breakout level; save the running impulse peak and contemporaneous side ASK. Watch for at most 30 seconds from episode start.
3. A subsequent observation strictly below the running impulse peak, but not below the breakout level, marks a held pullback. A price below the breakout level, a data gap >10 seconds, or expiry invalidates the episode.
4. After a held pullback, the first observation strictly exceeding the saved running impulse peak completes the pattern. Evaluate actual current ASK then. It must be >0 and <=50c and no more than 2c above the start-of-episode ASK, with valid 0<=BID<=ASK<=1. Still require 6–11 minutes remaining. One first qualifying entry per contract; no later better entry selected using its outcome.
5. If both sides complete on the same observation, choose larger side-aligned BTC15, UP only as deterministic exact tie-break.

The $8 and 30-second/+2c scales are anchored in existing research constants; no sweep. New information is ordered breakout / held pullback / reclaim geometry, not higher fair confidence, target-gap gating, a renamed momentum conjunction, or a settlement classifier. Price cannot manufacture the directional setup.

Coverage universe: all contracts observed before or at 11 minutes left and through 6 minutes left; incomplete contracts reported separately. Causal scans do not use future eligibility. Report calls for incomplete contracts separately. Primary excursion horizon is 120 seconds, with all remaining recorded contract path reported separately. ASK at entry; later BID for +5/+10/+15/+20, time to first hit, MFE and MAE; initial spread included in MAE. Do not interpolate a missed BID or a settlement payout. Primary complete paths must extend through 120 seconds with no >10-second observation gap; unresolved paths counted, not called failures or winners. Report one-observation delayed-entry sensitivity under identical frozen qualifying rules, not another candidate.

Development advancement screen (not an established production gate): >=20 complete calls; >=40% eligible-contract coverage; >=90% +5c and >=80% +10c within 120s; >=5 complete calls each UP and DOWN; mean and median ASK <=40c; every ASK <=50c; mean minutes left >=7; each chronological third >=5 complete calls and >=70% +10c. No secondary settlement-accuracy gate. Report all gates even if sample or quality fails. Observed excursions do not establish profitable manual execution.

## SCALP: TARGET_SUPPORTED_QUALITY_TIER_V1
Preserve the source movement candidates, side-aligned BTC30 >=15 and seconds_left >=120 qualification; no additional BTC30/parity/normalized-momentum gate. Join by (contract,candidate_id) and verify uniqueness.
1. Reconstruct the price-neutral serial movement opportunity schedule from original candidates and their PATH/RESULT records. +5c executable gain arms, first >=4c peak giveback exits. Only completed never-armed RESULT permits ENDED_UNARMED reset. Armed/no-exit stays blocking. Missing path evidence never permits reset. Process later candidates strictly after the terminal timestamp; no artificial opportunity cap.
2. Attach a candidate-time context tier: sign(side)*(BTC-target)>0 is TARGET_SUPPORTED; otherwise ordinary WATCH context. No future features and no Kalshi cent bucket in this tier.
3. The existing value control is first actual ASK <=50c at setup or within 30 seconds, on each serial movement opportunity. Candidate uses exactly the same value rule, but offers the TARGET_SUPPORTED quality tier as the only proposed actionable subset. All underlying moves and the serial movement schedule remain visible and unchanged. No reopening or rescheduling skipped opportunities.
4. Recompute excursion/protection against actual value-entry ASK; never include pre-entry bids. The original movement schedule and value-entry management are reported separately. If delayed-entry management is still blocking when the next scheduled movement arrives, do not overlap actionable entries. This compatibility check applies identically to control and candidate. No fabricated exit for open positions.
5. Gap=0 is not target-supported; absent BTC/target is unknown, not supported. This is a quality-tier research hypothesis, not permission to change live eligibility.

Paired comparison uses complete contracts first observed with >=780 seconds remaining, whose close is no later than the source capture end. Report all observed and excluded contracts and IDs. All comparisons share the same lifecycle and cohort; the older incomplete historical scorer is not overwritten.
Development advancement screen: >=30 complete control value entries, >=15 represented control contracts, candidate retains >=80% control opportunity IDs and >=90% control +10c winner IDs, candidate complete entry count >=80% control, +10c lift >=5 percentage points, no chronological third with lower +10c rate than control, >=5 candidate entries per third. Report absolute contract coverage and all price/timing/adverse/protection metrics. Exact-target context differs from rejected BTC30/parity gates; retention can still disqualify it. No retune after results.

## Closeout
Return one frozen eligible candidate or NO STABLE CANDIDATE per lane. A failed screen ends this pass; no alternative candidate or threshold search. A successful development screen is still unvalidated. Keep clean collection boundary and provisional validation reservation unchanged; full prior development-membership union remains unavailable, so do not certify clean-holdout eligibility.
