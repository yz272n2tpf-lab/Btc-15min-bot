# BTC15 SCALP Serial Lifecycle Checkpoint — 2026-09-15

SHADOW / RESEARCH ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS

## Frozen strategy anchors preserved

- Full 15-minute scalp scan.
- Frozen qualification remains `seconds_left >= 120` and side-aligned `btc30 >= 15`.
- Kalshi entry price remains telemetry only; no price trigger or suppression filter is applied.
- Protection remains unchanged: +5c executable gain arms protection; 4c giveback from running executable peak triggers protected EXIT.
- A completed protected EXIT may reset scanning and allow the next later qualified scalp.
- No artificial scalp-count cap.
- No stop-loss or early loss-cut rule selected.
- EARLY and FINAL protected-main logic is unchanged.
- Main dashboard remains canonical contract/timer authority.
- No order placement or automatic trading behavior exists in this work.

## BTC30 tightening decision

Development nominee `btc30 >= 20` was rejected by fresh holdout.

- Development baseline: n=34, +10c rate=0.765.
- Development nominee: n=31, +10c rate=0.774, winner retention=0.923.
- Holdout baseline: n=23, +10c rate=0.652.
- Holdout nominee: n=17, +10c rate=0.647, winner retention=0.733, selected share retained=0.739.
- Holdout support: FALSE.

Therefore the frozen `btc30 >= 15` qualification remains intact. No alternate threshold is selected from the same holdout.

## Failed-prearm lifecycle decision

A frozen-qualified candidate that receives collector RESULT before ever arming +5c may enter:

`ENDED_UNARMED`

This is an informational lifecycle terminal only. It is not a sell signal, stop-loss, actionable EXIT, order action, or trade instruction. After ENDED_UNARMED, serial scanning may resume for the next later frozen-qualified candidate.

A candidate that DID arm +5c but never reached the frozen 4c giveback EXIT is different. It remains a protected/blocking winner state and MUST NOT be reclassified as ENDED_UNARMED merely because collector RESULT exists.

Latest live lifecycle evidence before this checkpoint:

- baseline completed serial opportunities: 54
- projected serial opportunities with ENDED_UNARMED lifecycle: 58
- additional serial opportunities: 4
- ENDED_UNARMED terminals observed: 9
- armed/no-validated-exit protected states observed: 17
- armed/no-exit states preserved blocking: TRUE
- armed/no-exit states reclassified as ENDED_UNARMED: 0
- post-unarmed later completed handoffs: 4
- post-unarmed later +10c handoffs: 1
- true post-exit missed meaningful +10c candidates: 0
- lifecycle review ready: TRUE

## Failed-prearm reset tournament

The fixed descriptive adverse-move × elapsed-time grid found no measured reason to introduce an actionable stop-loss. Early release rules did not recover more completed later opportunities than the non-actionable ENDED_UNARMED lifecycle, and the recovered handoffs had the same weak +10c yield. No reset threshold was selected.

## Live protection evidence

Latest consolidated protection audit at this checkpoint:

- protected EXIT records: 32
- first observed frozen 4c giveback crossing correctness: 1.000

Protection thresholds remain unchanged.

## Current forward review

Latest consolidated forward snapshot before this checkpoint:

- completed serial opportunities: 55
- +10c meaningful-move rate: 0.727
- multi-opportunity behavior already observed up to four serial opportunities in one contract in the forward run

The +10c rate is a SCALP meaningful-move metric, not FINAL UP/DOWN accuracy.

## V5 / V10 shadow integration

### Combined scalp source

`btc15_combined_state_bridge_v5.py`

- Uses the tested serial state engine.
- Uses V4-style incremental event cache, freshness gating, main-contract authority, and fail-closed composition.
- Exposes ENDED_UNARMED only as lifecycle metadata.
- Explicitly sets `scalp_lifecycle_metadata_only = true`.
- Explicitly sets `scalp_ended_unarmed_is_actionable_exit = false`.
- Explicitly sets `scalp_armed_no_exit_reset_allowed = false`.
- Keeps state actionability limited to PASS / ACTIVE / PROTECT / EXIT.
- 65-test Railway startup gate passed on live V5 deployment.

### Shadow dashboard

`BTC15_DASHBOARD_COMBINED_SCALP_UI_V10.py` + `btc15_combined_dashboard_shadow_v6.py`

- Accepts V5 only if lifecycle metadata is explicitly metadata-only, ENDED_UNARMED is non-actionable, and armed/no-exit reset is disabled.
- Displays current scalp opportunity number.
- Displays prior ENDED_UNARMED only as plain-language lifecycle context: reset only / non-actionable.
- Preserves the single visible contract timer.
- Does not change EARLY, FINAL, Kalshi quote handling, protection thresholds, or order behavior.
- Dashboard server safety tests passed.
- V10 self-test passed.
- Live V5 preflight passed with contract match TRUE, EARLY preserved TRUE, FINAL preserved TRUE, canonical clock present, lifecycle metadata TRUE, serial safety TRUE, scalp guarded TRUE, fresh TRUE, aligned TRUE, and NO ORDERS.

## Remaining conservative freeze blockers

The consolidated live review gate currently has only two hard blockers:

1. Fresh local backend timer evidence must accumulate at least 20 valid samples.
2. Visual timer acceptance must be explicitly confirmed; it is never inferred by code.

At the latest sample before this checkpoint:

- timer valid: 11 / 14 total polls
- contract-match rate across valid samples: 1.000
- canonical-clock rate across valid samples: 1.000
- within-5s rate across valid samples: 0.909 (review note, not a frozen hard blocker)
- visual accepted: FALSE / pending

The system remains NOT READY TO FREEZE until the frozen review gate clears. Auto-freeze is not allowed.
