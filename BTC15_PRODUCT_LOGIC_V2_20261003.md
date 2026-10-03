# BTC15 completed product logic — V2, 3 October 2026

Candidate: `BTC15_LADDER_COMPLETION_20261003_V2`. Development and offline functional verification only. PR #53 stays DRAFT / DO NOT DEPLOY. No Railway service, variable, volume, start command or deployment was changed by this completion work. The previously staged V1 qualification configuration is obsolete and must not be used.

This finishes the product logic with the strongest defensible recovered configuration presently available. It does **not** establish EARLY reliability of 85%/90%, FINAL calibration, profitable SCALP execution, or increased opportunity frequency. No new historical search, threshold sweep, prospective performance campaign or Ground Zero work was performed. Both failed Oct. 3 Ground Zero intervals remain excluded.

## Selected policy and exact recovery

| Reused implementation | Exact prior identity | V2 use |
|---|---|---|
| Generalized protection presentation, `btc15_scalp_management_presentation_v1.py` | Branch `scalp-ui-state-contract-v1`, commit `b0999fc80219f16c32a37a822127ed9dc2ad809e`, blob `45bd5b58a652957d0d415797264aac09bc4f45f8` | Byte-identical pure module. Arms at +5¢ observed executable gain, PROTECT while armed, warns on pullback, EXIT on 4¢ giveback. |
| `completion_audit/v81_exit_candidate.py` | Introduced `83c014a44523469988dbae079d9d636d61643e71`, blob `64cc18c4921b040c5d3d60b16f727e9cb6e8bb21` | Byte-identical module copied as `btc15_recovered_exit_engine_v1.py`; its parameterized `Policy`/`Lifecycle` executes the selected policy. Its predeclared research alternatives are not promoted. |
| Serial ownership and handoff | `BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1.py`, blob `06a4abed1a66ba61a1c9621dbc51259a34fcbee4`, recovered source and complete identity in the accepted PR53 audit; V5 checkpoint Sep15 | Reuse terminal-before-successor semantics. The live adapter retains an immutable terminal and requires two new qualifying observations strictly after it. Generalized research eligibility is not used as V8.1 eligibility. |
| Reversal/re-entry lane classification | `shadow_diagnostics/scalp_reversal_reentry_ladder_v1.py`, branch `b124c54ea9d015d88c5237d5e0bc45ded8a37f36`, function `_lane` | Reused first/same-side continuation/opposite-side recross classification from explicit predecessor identity. It cannot initiate an entry. |
| EARLY authority and position manager | `btc15_directional_signal_authority_v1.py` blob `693f87cddc41de58d59088ea67a921db0861406f`; manager commit `750cd2298d21405aa51987d32f232779ae71d294` | Existing PR53 recovery retained. EARLY creates its own origin; FINAL is additive. Recovered PROTECT remains latched. |

The **mechanism** is recovered code. Selecting 5¢ arm / 4¢ giveback for the current V8.1 guidance is a new, explicit risk-policy application, **not statistical promotion of historical generalized SCALP results**. It is chosen as the previously implemented baseline, without optimizing descriptive outcomes. The supplied `DESCRIPTIVE_ONLY_NOT_PROMOTABLE`, `policy_selection=NONE` analysis remains development evidence. Its fixed-origin results are not a replay of this serial strategy.

The known limitation remains material: the historical serial review recorded 51/57 exits beyond the ideal giveback trigger and nine nonpositive exits. The adapter therefore publishes the actual later accepted bid, never the theoretical trailing price as a fill or a guaranteed profit floor.

## Exact frozen decisions

### EARLY

Entry requires all current causal source checks, actual same-side ask `0 < ask <= .45`, model fair `>= .75`, 120–600 seconds remaining, and absolute Coinbase-to-official-target gap `>= $25`. The 8-point edge gate is removed because fair>=.75 and ask<=.45 already imply at least 30 points of model edge. This removes redundant logic, not a restrictive boundary; no frequency increase is claimed.

Target awareness is <=50¢; ideal awareness is 25–35¢. Neither expands eligibility. Qualified EARLY does not require FINAL to be ready. One immutable origin per contract stores side, actual ask, acceptance time, native decision identity, official target/window, model identities and causal source evidence. No manual fill is assumed.

This is completion-policy outcome **B for additional entry alpha**: no defensible additional expansion beyond the recovered entry state was established from available evidence. It is not an assertion that the sparse baseline achieves the desired reliability. The gate decisions were made explicitly:

| Gate | Decision and evidence |
|---|---|
| 45¢ ceiling | Retain. Expanding to50¢ improves nominal coverage but no accepted study establishes the added opportunities' reliability. Keep the50¢ objective visible. |
| 75% model floor | Retain without treating it as empirical accuracy. T1/T7 and broader tier/persistence variants failed the agreed objective. |
| 8-point edge | Remove as mathematically redundant. |
| 2–10 minute window | Retain; do not delay or backdate entry. Earlier runway and projected crossing alternatives failed. |
| $25 absolute gap | Retain pending genuinely new evidence. Its interaction with cheap asks is a documented coverage bottleneck, but blind removal was not supported by completed studies. |
| FINAL entry veto | Recovered EARLY-only authority keeps it removed; independent FINAL cannot cancel initial EARLY merely by being unready. |
| Corrected information | Use causal native model inputs, exact quote witness, fixed official target and BRTI<=5s. Do not treat provenance correction as new alpha evidence. |

The remaining recovered runway result (`7d07b17c5127a423dd384b36fc21b5d195c7e52c`, `research_review/early_settlement_runway_consensus_v1_20260920/RESULT.md`, blob `298491b6a64939947b49753c529180133c0426f2`) explicitly rejects 12/16=75% calls. Cheap-motion (`d31922b4c72d5bc7efa590eb1b3c4f86da71fc0d`, spec blob `4d6974941c6a41cc6aebddea61de33248f3f8bad`) and preprice (`0a2a8cdd29810fe765373948fbf113dad3b04466`, spec blob `6be316d7ed8bd658454a28852a90b785d7e8fe3f`) are frozen research specifications without a recovered supporting result; they are not silently labeled successful or rejected. Earlier feasibility75.6%, persistence78.9%, projected-cross13/33, target-hold0/57, tier expansion and T1/T7 dispositions remain as documented in the accepted audit. None supports a90% claim or another run of the same failed families.

### Independent FINAL plus EARLY helper

FINAL retains model UP/DOWN probabilities and preferred direction. A qualified FINAL call requires fair>=.90, <=480seconds remaining, absolute gap>=$75 above360seconds otherwise$50, distance/range>=1, target-side agreement, and BRTI more than$11 from target on that side. No artificial delay. Lock state is current `QUALIFIED`/`UNLOCKED`, not a future guarantee.

The independent FINAL publication is constructed before the EARLY manager transition; a manager error leaves qualified FINAL readable and the helper explicitly unavailable. The helper only links an actually accepted immutable EARLY origin:

- unchanged support: HOLD; strengthening/weakening probability deltas are explicit;
- stronger/qualified same-side FINAL: CONFIRMS and clearance=true;
- weakening support: WATCH, strengthened to CAUTION by late context;
- conflicting BRTI/target/model context or BRTI inside its existing neutral band: MIXED/CAUTION;
- loss of a previously qualified confirmation: material deterioration and latched PROTECT;
- FINAL opposition: latched PROTECT; a qualified opposite call after a prior qualified held-side call is explicitly FLIPPED;
- renewed agreement can report clearance while preserving the existing PROTECT latch.

Current same-side executable bid and gross movement from original ask accompany guidance. EARLY has **no evidence-supported automatic EXIT threshold** in this candidate: PROTECT means review/reduce exposure manually at the available bid, not a fabricated trade or hard exit signal. The UI says this explicitly. SCALP provides the selected actionable EXIT lifecycle below. PROTECT never asserts that a manual trade was performed.

### SCALP

Retain V8.1 30–45¢ entry band, existing V4/structure checks and CORE/SURGE routes. Keep two qualifying observations inside4seconds and20seconds same-side cooldown. Corrected safeguards require distinct later accepted books for confirmation, valid causal5/15/30second feature provenance, and no lookback more than6seconds behind its intended horizon. These are freshness safeguards, not coverage optimization. Confirmation never accumulates while a position owns the lane and never survives restart/outage.

The original executable ask and origin never move. Path observations require strictly later quote source and validation timestamps, same ticker/side, and advancing accepted book identity. Epoch changes/gaps mark missing paths; source or sequence rollback fails closed.

1. ENTER at the accepted origin ask; HOLD while support and timing permit.
2. WATCH/CAUTION on current target/BRTI conflict, late context or pre-arm pullback. None has automatic EXIT authority.
3. Arm profit protection when observed bid-original ask>=5¢; publish PROTECT. The trailing trigger is original ask+observed peak gain−4¢. At the minimum arm this implies a1¢ theoretical trigger cushion; there is no guaranteed executable floor.
4. First accepted bid with >=4¢ giveback produces latched EXIT at **that actual bid and actual observation time**. Later recovery cannot undo or reprice the historical EXIT.
5. The inherited180second horizon produces EXIT at the first qualified later same-contract bid at/after the deadline, with delay recorded. Stale/missing bids yield UNAVAILABLE until such a bid exists. Contract rollover without one is terminal/unpriced, never an invented EXIT fill.
6. A successor needs two fresh qualifying observations after the terminal, with same-side cooldown preserved. It records predecessor origin/EXIT identity and is labeled re-entry continuation or reversal/recross. EXIT is guidance, not proof that the user closed; successor guidance is conditional on the user having exited the prior signal.

+8/+10/+15/+20/+30¢ and−10¢ comparison-stop chronology, target-first/stop-first, time-to-target/stop, MFE/MAE, giveback, gaps and terminals are recorded through the actual lifecycle. **No fixed target or loss stop is selected from the descriptive study.** No settlement direction substitutes for executable SCALP performance.

### 5M / 3M / flip-risk

Inside5minutes, existing weakening/conflict/pullback context escalates WATCH to CAUTION; otherwise the card explains the need to monitor support and bid. Inside3minutes, active positions receive CAUTION for limited exit runway, or retain stronger PROTECT/EXIT. Neither time boundary changes entry thresholds or invents EXIT authority. Flip-risk remains the existing model probability opposite the current target side, labeled informational; it has no independent WATCH/EXIT threshold.

### Integrity and journal

Official900second windows and New York close-derived ticker are checked; fixed target cannot change under an origin. BRTI true source age<=5seconds; accepted quote age<=6seconds; Coinbase source age<=10seconds; no source clock after its causal cutoff. UI expiry uses server receipt and browser monotonic time, not the browser wall clock. Restart refuses another candidate’s checkpoint or an origin that disagrees with its persisted position. Missing/unqualified data yield UNAVAILABLE; qualified insufficient edge yields PASS. Independent FINAL remains visible when only its EARLY helper fails.

One queue of16 and one journal writer per lane. Transactional compressed event+checkpoint commits precede publication. Origins, FINAL identities/linkage, strictly later bids, transitions and terminals are retained. A bounded contract table distinguishes observed quiet slots, partial/missing slots, signal counts and unavailable observations, including missed slots across restart. Retention:30days or300,000events; SQLite page cap512MiB per lane; record/view cap64KiB. `/ladders/coverage` exposes at most96 recent contract summaries.

BRTI final60 closeout is recorded separately and never called authoritative settlement. A bounded GET-only reader (at most5known closed contracts/30seconds,5minute retry interval) records Kalshi `finalized` yes/no outcomes. Pending, disputed/nonbinary and unavailable results stay explicit. It cannot feed decisions or add orders. The documented market endpoint is https://docs.kalshi.com/api-reference/market/get-market .

## Sixteen-capability completion certificate

This certificate concerns implemented logic and focused offline tests, not live qualification or performance certification. Exact bytes are in `BTC15_LADDER_COMPLETION_FREEZE_20261003.json`.

| Required capability | Implemented authority / limitation |
|---|---|
| 1. Finished EARLY decisions | `btc15_ladder_product_v1.py::protected_frame`; outcomeB/no supported additional alpha expansion; reliability objective remains unproven. |
| 2. Independent FINAL | `Directional.process`; separate probability/call/lock output, original timing. |
| 3. FINAL→EARLY helper/protection | Immutable origin ID; confirm/strengthen/weaken/MIXED/oppose/flip; latchedPROTECT; unsupported EARLY EXIT explicitly absent. |
| 4. Actionable SCALP | `btc15_scalp_journal_v1.py::Scalp`; ENTER/HOLD/WATCH/CAUTION/PROTECT/EXIT/PASS/UNAVAILABLE. |
| 5. Recovered profit protection | Byte-identical management and parameterized exit-engine modules above. |
| 6. Latched EXIT | Immutable terminal survives recovery/restart; exact predecessor handoff. |
| 7. Executable price semantics | Immutable origin ask; actual current same-side bid; historical EXIT bid remains distinct; no fill claims. |
| 8. 5M CAUTION | `btc15_position_context_v2.py`; deterioration-aware caution. |
| 9. 3M guard rails | Same module; limited-runway caution without invented predictive authority. |
| 10. Flip-risk | Existing model context only. |
| 11. PASS/UNAVAILABLE | Separate qualified rejection and missing/stale/inconsistent source states. |
| 12. Permanent journal | Bounded SQLite events/checkpoints/contract denominator plus official result receipts; no generalized recorder. |
| 13. Kalshi alignment | Exact official ticker/window and immutable target checks in both lanes. |
| 14. BRTI<=5s | True source-time check at actual decision/publication; read-time expiry. |
| 15. SIGNAL ONLY | Payload, UI and journal enforcement; no assumed position or fill. |
| 16. NO ORDERS | No order endpoint, routing, order object, credential expansion or automated execution added. |

## Comparison with frozen production

| Dimension | V2 versus MAIN `abe212b…` / V8.1 `b05723e…` |
|---|---|
| EARLY coverage, entry price and PASS | Same effective positive-ask gate membership. No supported quantitative coverage gain or85% reliability claim. Explicit rejection reasons retained. |
| FINAL reliability/timing | Core decision thresholds and useful timing preserved; no delay-based accuracy inflation. |
| EARLY protection | Adds persistent origin, executable bid/movement, explicit FINAL relations and monotone protection. Historical genuine linked protection value remains unestablished. |
| SCALP frequency | Entry numerical gates retained; earlier EXIT can permit later serial entries, while integrity safeguards can reject stale/repeated evidence. Net live frequency is not established. |
| SCALP targets/stops | Correct executable chronology;5/4protection plus180second horizon selected as current risk policy. Prior descriptive target statistics do not qualify it. |
| Failure clusters | Gaps, trailing overshoot, unarmed losses, unpriced rollover and missing outcomes remain explicit. No guarantees against round-trip loss during missing prices. |
| Freshness/fail-closed | Corrected source lineage is enforced; neither HTTP polling nor repeated quotes create confirmations. |

## Qualification boundary

Run the exact frozen offline gate first. No further historical tuning or multi-day performance hold is required. A later explicitly approved staged live qualification must use these V2 identities, both lane artifacts, persistent journal storage for both lanes, and the correct V8.1 `/ladders` URL. V8.1's currently unprovisioned persistent volume remains a deployment prerequisite, not a product-logic change made here. Verify accepted live entry, later bid, protection/EXIT/handoff where observed, official alignment/freshness, durable journal readback/restart, and no orders. A fixture proves function; only an observed live event proves live wiring. No qualification or production deployment is authorized by this document.
