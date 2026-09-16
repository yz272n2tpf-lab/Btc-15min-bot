# CURRENT STATE — September 16, 2026, R2 engineering milestone

This Work thread is the sole engineering/control authority. No instructions imported from other chats.

## CONTROL

No Railway service was changed, stopped, restarted or deleted in this milestone. All frozen source files are unchanged. Read-only checks confirmed:

| Service / role | Active deployment | State |
| --- | --- | --- |
| scalp-economics-forward-v1 | 0cf8e2e8-ef60-4b09-86cf-93b2aff44f6e | SUCCESS; logs advancing |
| scalp-economics-exit-review-v1 / Candidate Verify V1 | 19c72496-8ea1-4a4b-8e09-564e1074dbef | SUCCESS; logs advancing |
| scalp-entry-profit-review-v1 / Watch V1 | 71f6718d-1901-4196-b629-2e514ea5a327 | SUCCESS; logs advancing |
| v81-30-45-live-feed-v2 / replacement feed | ae6976a2-fb93-449a-a05d-f45dc32bd478 | SUCCESS |
| v81-30-45-live-feed / legacy deletion target | 130646d2-e445-492a-8588-e49fdf7f313b | FAILED; still present |

This is not a claim that every project service is healthy. Existing unrelated service faults were not changed.

Latest inspected CONTROL evidence, not V2 results:

- Economics, 21:28:29Z: 33 full contracts, 72 signals, 48 protected exits. SCALP-2: 20 signals, 15 protected exits, conditional taker/taker net averages +1.9533c at one lot and +2.72c per contract at ten lots. Frozen sample gate is false; missing/unprotected outcomes are excluded, and average profitability alone does not establish a winner.
- Candidate Verify, 21:29:17Z: 33 full contracts, 69 immediate signals; sample_ready false.
- Watch, 21:30:00Z: 30 full contracts, 61 signals, 50 armed, 43 first warnings at 1c, 41 Watch exits. Mean lead 8.589s; median 0s; 24.39% of warned exits had >=5s lead. Warning-without-exit rate 4.65%; new-high recovery proxy 2.33%. These are distinct measures, not an interchangeable false-warning rate.

These services have different frozen cutoffs and samples; their totals are not pooled for V2 comparison.

## NEW SHADOW

R2 is built on the isolated `scalp-nextgen-shadow-v2` branch, not deployed. Single-service design, 24 policies across four families. Added a pure replay core; separated causal decisions from outcomes; repaired missing immediate-pullback scoring fields; eliminated duplicate-event confirmations; replaced the redundant velocity rule; added matched-opportunity comparisons and all requested V1 control policies; added per-opportunity audit, source freshness, error recovery, code pinning and fresh-window activation guards.

The earlier pullback problem was incomplete scoring/accounting for immediate entries, not a reproduced exception. The full CSV integration test now verifies that those entries contribute correctly.

Changed files: V2 core, V2 service, V2 tests, V2 freeze/spec/current-state documents, and `railway.json` on this isolated branch. No V1 helper, collector, production, or existing CI workflow file changed.

Validation: 27 synthetic regression tests pass with Python 3.12 and exact repository dependencies (numpy 2.5.2, pandas 3.0.5, requests 2.32.5, scikit-learn 1.9.0, cryptography 50.0.0). Real local HTTP handler checks cover liveness/readiness/state/audit. Twelve extra differential cases matched the separate frozen Watch V1 implementation. Railway JSON validates against its official schema. No CI or Railway build success is claimed.

Synthetic illustration only: the declining-quote fixture triggered R2 Watch at 12s versus V1 at 20s, an 8s lead improvement with identical exit time and gain. No live V2 performance is available. These tests cannot establish economic improvement or production eligibility.

Reproduce: install `requirements.txt`, then run `python shadow_diagnostics/test_scalp_nextgen_shadow_v2.py`.

## BLOCKED

Railway is still at 50 services. The sole approved legacy deletion remains pending because the connected deletion route is unavailable/usage-limited. No V2 service exists and its prospective window is NOT ACTIVATED. The superseded 19:50Z cutoff must not be reused for this changed code.

## NEXT STEP

After the user deletes only the failed legacy feed, verify the freed slot and healthy replacement; create the single combined V2 service from the saved branch; pin its fingerprint, choose and record a fresh cutoff after deployment acceptance, configure read-only export references, then verify logs, `/ready`, `/state`, `/audit`, and unchanged frozen control deployment IDs. Start development comparison only. Any eventual candidate requires a separately frozen future certification window before production consideration.
