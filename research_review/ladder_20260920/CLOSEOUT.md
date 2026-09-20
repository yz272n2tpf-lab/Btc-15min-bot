# BTC15 scalp ladder focused research closeout — 2026-09-20

**Recommendation: BLOCKED. Recover the exact historical evidence bundle before judging or advancing this candidate.** The reported aggregates were recovered from two archived jobs with the requested source hash. The raw tape and coherent full audit were not recovered, so an independent historical replay, false-start feature join, and holdout membership audit cannot be completed. No improvement or production promotion is established.

SIGNAL ONLY / MANUAL EXECUTION / NO ORDERS.

## Review identity and scope

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Review branch: `scalp-ladder-evidence-review-20260920`, based exactly on `e86075aa058d0e6f90c6f97e818748a2c7351457`.
- The closeout commit is the commit containing this file; obtain the full SHA with `git rev-parse HEAD`. The final handoff supplies that SHA.
- Historical strategy anchors read at `a832caed20a7a7535c1069275f7c2688f864b023`: `BTC15_SCALP_SERIAL_LIFECYCLE_CHECKPOINT_20260915.md` and `BTC15_SCALP_RESEARCH_DECISION_LOG_20260915.md`.
- Inspected newer development history through `e86075a`, raw-audit branch through `8b8c319a56119ed812478f03cb80d1fe3a08d799`, and review-tool history through `8124831`. None was rerun as a threshold search.
- Only the six files under `research_review/ladder_20260920/` listed below were added. Runtime code, frozen controls, collectors, production, main, FINAL/EARLY, BRTI, quote ingestion, and dashboard files were not edited. No Railway action or deployment was performed. No clean-window performance endpoint or log was read.

## What exists, and what the candidate document does not prove

The candidate commit adds **one specification document**, not a new implementation. Its chosen `V1_LE50_30S` lane already exists in `shadow_diagnostics/scalp_pullback_entry_forward_v1.py`, called unchanged by `scalp_nextgen_v2_core.pullback_records`.

That lane takes the first recorded ASK ≤50¢ at time zero or within an inclusive 30-second window, and measures subsequent recorded BID against actual entry ASK. No value entry is returned after a failed window. This is an offline entry replay; the document's visible WATCH / WAIT FOR VALUE behavior and a complete candidate-specific serial state machine are not implemented by this lane.

Movement qualification remains side-neutral with respect to price, supports UP/DOWN, and requires `seconds_left >= 120` and side-aligned BTC30 ≥15. Full-time collection does not remove that qualification. The ≥120-second check is at original movement qualification; delayed entry is not independently requalified by the legacy lane. Price bands remain descriptive. No BTC30 tightening, normalized-momentum, strict parity, or micro-confirmation study was repeated.

The matching historical opportunity builder is `scalp_opportunity_quality_frontier_v1.build_serial_opportunities`. It uses completed control opportunity IDs, allows later serial opportunities after protected exits, and stops after a candidate with no protected exit. **It does not implement the established ENDED_UNARMED reset.** Its counts therefore cannot be presented as a validation of the complete later lifecycle. The isolated tests reproduce this limitation; no frozen code was altered to hide it. Armed/no-exit candidates remain blocking.

The first observed ≥4¢ giveback after +5¢ arming is preserved. Observed gaps can yield more than 4¢ actual giveback. ENDED_UNARMED remains informational, never a sell instruction. There is no selected never-armed exit policy.

## Exact source and recovered evidence

| Item | Fingerprint / provenance |
|---|---|
| Required raw source SHA256 | `8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a` — reported in archived state, raw bytes unavailable |
| Replay dependency SHA256 | `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f` — independently recomputed from this checkout; exact match |
| Exact-hash aggregate run 1 | [35532923925](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/35532923925), commit `16749a3a0ee1f21576cc57404ba8a9f827657754`, output 19:37:49Z |
| Exact-hash aggregate run 2 | [35532972710](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/35532972710), commit `66b332b9972f6e9de93c85b92e1b4b36bc7e2991`, output 19:38:43Z |
| Later same-count source | Run `35533295727`, 19:44:46Z: `f175bea5ca8160ed40b1b551196aaf29a935b7f4c3766c80bbe01ce11ea2fc68`; rejected as an exact-source substitute despite identical aggregate counts |
| Committed evidence-excerpt SHA256 | `681c8aabcb2a476cee92ac7ae44715513d01f7a7a388f9dc28cc666f879a855b` |

Both exact-hash aggregate runs agree. Their workflows fetched `/state` and `/audit` separately and did not log the audit's source hash, save the raw input, or upload an artifact. Thus state/audit atomic coherence cannot be verified from those logs. Artifact listings for both runs and the later run were empty.

The archived schema probe, run `35532923937`, records **HTTP 401** for unauthenticated raw export. Its audit output exposes derived outcome fields and one sample per family, not all original CANDIDATE feature rows. No credentials were guessed and no growing live export was substituted.

The reviewed alternative `scalp_overnight_data.zip` has SHA256 `2eb1316bcd5d12e70366e3c38de285abcbb365d52d68987799c8a89b3a79f284`: 1,474 events and 5,863 snapshots from **September 3**, lacking original `candidate_id` and `record_type`. It is not this cohort. The older September 17 checkpoint pack reports source `2a429c8ba07b2b52eaf2e6a28aa58ea2c19d8dcc84eacf5806c941782976d683` and `live_raw_tape_audited=false`; it is also not a substitute. Targeted saved-file/context searches did not locate the requested raw bundle.

## Control versus candidate scorecard

**Recovered archived aggregates, not a newly reproduced raw-tape score.** Integer numerators below were recovered exactly from full-precision archived rates and checked for consistency. Universe: **352 reported full contracts / 563 historical control opportunities**. The earlier 349/560 snapshot and separate 609-entry protection study are excluded throughout.

| Metric | Historical immediate control | Candidate ≤50¢ / 30s |
|---|---:|---:|
| Actionable entries / control opportunities | 563/563 (100%) | 321/563 (57.02%) |
| Contracts with entry / full contracts | 334/352 (94.89%) | 236/352 (67.05%) |
| Mean / median actual ASK | 47.771¢ / 48¢ | 32.013¢ / 34¢ |
| ASK ≤35¢ | 181/563 (32.15%) | 181/321 (56.39%) |
| ASK ≤50¢ | 318/563 (56.48%) | 321/321 (100%) |
| Mean entry delay from movement setup | 0s | 0.04948s |
| Mean seconds left at entry | 574.959s | Unavailable in archived output |
| +5¢ recorded path hit | 470/563 (83.48%) | 266/321 (82.87%) |
| +10¢ recorded path hit | 375/563 (66.61%) | 213/321 (66.36%) |
| +15¢ recorded path hit | Unavailable | Unavailable |
| +20¢ recorded path hit | 206/563 (36.59%) | 135/321 (42.06%) |
| Observed protected exits | 325/563 (57.73%) | 203/321 (63.24%) |
| No observed protected exit | 238/563 | 118/321 |
| Reported +5¢ but no exit, derived from counts | 145/563 | 63/321 |
| No reported +5¢, including any missing/unscoreable paths | 93/563 | 55/321 |
| No actionable entry under value rule | 0/563 | 242/563 |
| Mean gross gain among protected exits only | +5.387¢, n=325 | Unavailable in archived output |
| Mean modeled taker/taker net, 1 lot; exits only | +1.572¢, n=325 | Unavailable in archived output |
| Mean modeled taker/taker net, 10 lots; exits only | +2.284¢, n=325 | Unavailable in archived output |

The candidate lowers entry cost and retains 57.02% of control opportunities; its +10¢ rate changes by **−0.252 percentage points**. These are descriptive development results, not independent improvement evidence.

**Winner-ID retention is unavailable.** It means retained original control +10¢ winner IDs divided by 375; `213/375` is not that metric because re-entering at another ASK can change an outcome. Set arithmetic alone bounds retained winner IDs between 133 and 321 (35.47%–85.60%); these are bounds, not measured retention.

The mean delay is across all candidate entries, not the waiting subset. Entry-delay median, waiting-subset timing, adverse excursion, +15¢, and ID-matched outcomes require the missing rows. The 93/55 no-+5 groups must not be called confirmed never-armed counts: missing PATH evidence was not separately reported. The 145/63 armed-without-exit groups remain unresolved/blocking under the preserved rule. The 238/118 without exits have no complete realized return and must not be assigned zero profit.

Candidate timing and protected-exit economics appear null because the comparison workflow reads the wrong schema for that lane: `seconds_left` instead of `seconds_left_at_entry`, `gross_protected_gain_c` instead of `100 * protected_exit_gain`, and nested `fee_scenarios` instead of the lane's flat net fields. The values cannot be reconstructed from aggregate counts. No result from the separate 609-entry study is used to fill them.

The replay's +5/+10/+20 labels and peak/adverse fields can include observations **after an earlier protected EXIT**. A synthetic test demonstrates a +20¢ path hit after an exit capturing only +4¢. Movement hits are not captured profit. Even the control's exit averages cover only 325/563 entries, not total P&L. The frozen fee model assumes `ceil-cent(0.07 * quantity * price * (1-price))` per taker side; those are historical modeling assumptions, not verified current fees or fills. There is no allowance here for manual reaction delay, slippage, depth, partial fills, or an exit policy for unprotected positions. No total-P&L claim is possible.

## False starts: exactly what is missing

The blocker is one coherent evidence bundle containing:

1. Exact raw export bytes matching the requested SHA, including passive rows used for the 352-contract denominator.
2. Original CANDIDATE records: stable candidate ID, contract, side, timestamp, ASK, seconds left, BTC/BRTI momentum, acceleration, confirmation and structure fields, spread, and other actually recorded decision-time inputs.
3. PATH rows with candidate IDs, observation timestamps/elapsed time, actual ASK/BID and executable gain, plus RESULT rows with terminal timestamps; enough to audit missing/duplicate IDs and cross-contract collisions before joining.
4. Coherent full state/audit metadata, cutoff, full development contract IDs, and a separate membership manifest for the 609-entry protection study.

Join original CANDIDATE inputs to PATH/RESULT labels by verified `(contract, candidate_id)`; retain assigned opportunity index for paired control/candidate outputs. The legacy builder joins on candidate ID alone, so global uniqueness must be checked first. Future peaks, adverse excursions, future BID, settlement, and exit outcomes are labels only. They were not used as entry features in this review. Without these original records, a false-start feature comparison would be invented; none was performed.

## Cohort boundaries and protected validation

- Existing collector branch/checkpoint remain `scalp-finalprod-clean-v1-20260920` / `f59276fd4733bbc374be53aaa4bb8063ed0f81ab`.
- Scoring branch observed at `fcc2af537326d4e7edc0012e5647adc673d22802`: `scalp-nextgen-finalprod-clean-v2-20260920`.
- Recorded clean collection boundary remains **2026-09-20T19:05:17.147189Z**. The source note records additional nanosecond digits; the scoring workflow uses this microsecond value.
- Historical V2 checkpoint metadata has cutoff **2026-09-16T22:30:00Z**. The exact 352-contract input's full first/last timestamp and membership list were not archived in the recovered logs, so that earlier metadata alone cannot certify its exact boundaries.
- Development scoring continued after clean collection began. A different service name is not proof of a disjoint holdout. The original 19:05 boundary alone is insufficient to certify eligibility.
- **Provisional conservative reservation: complete contracts starting at/after 2026-09-20T20:15:00Z**, on the existing tape, with every development contract ID excluded across sources (including the 609-entry study). This is a reservation, not certified eligibility. The exact eligible holdout remains blocked pending development membership recovery. Earlier collected contracts may be considered only after disjointness is proven; collection is not restarted or reset.
- Historical scores measure replay over the scalp research collector's tape. The clean collector uses qualified production data components but is a separate research process; it does not establish the actual production bot's emitted signal history. No before/after infrastructure-causality claim is made.

## Tests and files

Executed locally: **35 existing tests passed + 13 isolated review tests passed = 48 passed, 0 failed, 0 skipped**. An initial invocation failed to import two test modules because `requests` was absent from the default path; after adding the already-installed local dependency path, all 35 existing tests executed successfully. This was not a market-data failure.

The 13 review tests cover hash/cohort rejection, exact aggregate count recovery, 30-second boundary, actual ASK selection, future-outcome independence, exclusion of pre-entry BID, first observed giveback, missing outcomes, UP/DOWN and minimum-time qualification, and characterization of the legacy lifecycle/input assumptions. Three characterization tests document existing behavior; passing them is not approval of those limitations. The legacy lane also assumes valid quote/time inputs and can clamp negative elapsed time to zero; the missing raw tape prevents determining whether such inputs occurred. Synthetic tests are not forward validation.

Reproduction commands (with repository dependencies installed):

```bash
PYTHONPATH=shadow_diagnostics python -m unittest -q test_scalp_pullback_entry_forward_v1 test_scalp_nextgen_shadow_v2
python -m unittest discover -s research_review/ladder_20260920 -p test_review.py -v
python research_review/ladder_20260920/review.py
```

Changed files, all additive and research-only:

- `research_review/ladder_20260920/CLOSEOUT.md`
- `research_review/ladder_20260920/archived_workflow_evidence.json`
- `research_review/ladder_20260920/review.py`
- `research_review/ladder_20260920/test_review.py`
- `research_review/ladder_20260920/recovered_scorecard.json`
- `research_review/ladder_20260920/verification.json`

**Next bounded step:** recover the specified immutable bundle; verify its hash and IDs, reproduce only immediate control versus ≤50¢/30s using the original scorer, and reconcile the documented lifecycle/schema limitations before declaring any candidate ready. Then freeze the paired report and eligible ID manifest for one untouched forward comparison on the existing collector. No tuning or automatic promotion. Scalp movement conversion remains separate from FINAL directional accuracy; 93–95% goals are targets, not achieved facts.

**BLOCKED — exact-hash historical CANDIDATE/PATH/RESULT tape and development contract membership are unavailable.**
