# BTC15 Watch -> Exit Warning Forward V1 — Prospective Freeze

**SHADOW ONLY · SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS · NO AUTO-PROMOTION**

## Purpose
Measure whether an earlier app-facing **Watch / Protect Profits** warning can provide useful lead time before the already-frozen protected Exit.

This study does **not** change the scalp detector, entry rule, serial opportunity lifecycle, or protected Exit.

## Frozen lifecycle
- Protection arm: executable gain reaches **+5c**.
- Watch comparison lanes, fixed before the future sample:
  - **WATCH_1C**: first post-arm giveback >=1c from the running peak.
  - **WATCH_2C**: first post-arm giveback >=2c.
  - **WATCH_3C**: first post-arm giveback >=3c.
- Protected Exit remains exactly **4c giveback** from the running peak after the +5c arm.
- A Watch event never moves the peak, resets the lifecycle, or forces an Exit.
- If price recovers to a new high after Watch, that is recorded explicitly as recovery / false-alarm evidence.
- If Watch occurs and the frozen 4c Exit never occurs, the path is reported as `warning_without_exit`; no realized exit is fabricated.

## Metrics
For each fixed Watch lane, report prospectively:
- armed-signal and armed-contract counts;
- Watch rate among armed signals;
- true future-contract Watch coverage;
- frozen Exit rate among armed signals;
- fraction of frozen Exits preceded by Watch;
- average/median Watch-to-Exit lead seconds;
- percentage of paired Watch/Exit paths with >=5s, >=10s, >=15s lead;
- warning-without-exit rate;
- recovery-to-new-high-after-Watch rate;
- executable gain at Watch and at frozen Exit;
- entry economics and <=50c entry rate;
- conservative 1-lot and 10-lot taker/taker net economics for paths with observed Watch then frozen Exit;
- opportunity-index breakdown.

## Prospective denominator
Only contracts proven fully observed by the existing passive-contract universe logic and whose first observation occurs at/after the later frozen cutoff may enter the forward sample.

Mid-contract or pre-cutoff contracts are excluded.

## Evidence readiness
A review-size marker requires both:
- >= **100 fully observed future contracts**; and
- >= **50 armed signals**.

This is a sample-size marker only. It is **not** a performance PASS/FAIL gate.

## Selection discipline
This first future window is a comparison/development window.

- It cannot select a production Watch giveback.
- It cannot tune the 1c/2c/3c lanes from the same sample.
- It cannot alter the frozen 4c Exit.
- It cannot auto-promote any lane.
- If manual review later chooses a Watch rule, that rule must be frozen and tested on a **new future certification window**.

## Safety
- No production imports or writes.
- No dashboard behavior changes.
- No signal suppression or rescue.
- No automatic orders.
- Existing Coverage Rescue, Economics Forward, Regime Forward, Candidate->Verify, FINAL/EARLY, and Flip Risk collectors remain independent.
