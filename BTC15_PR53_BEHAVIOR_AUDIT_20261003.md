# BTC15 PR #53: behavior audit and corrected recovery

Status: INCOMPLETE PRODUCT — NO QUALIFICATION OR DEPLOYMENT.

This audit examines PR #53 at `979f07aa3a000d66673aeb7cc24ef1c4c5272707`,
before any new policy change. The separate V8.1 companion is
`ccb2528e8e158010ef901741410cdc640cb82eb3`. Neither is a finished ladder product.
The 61 focused tests cover their implemented mechanics; they do not establish
missing behavior, profitable exits, improved entry frequency, or 85% reliability.

Production baseline remains MAIN `abe212b513827c8cec28a2f64e0161e79296bd82`
and V8.1 `b05723ec622f901a05402ecf27f4d33505753ef1`. No Railway mutation was
made during this corrective audit. The earlier 19-change qualification patch
remains staged and unapplied. It must not be accepted under the current instruction.

## Classification and exact sources

“IMPLEMENTED AND ACTIVE” below means wired into the named candidate's executable
path, or explicitly identified existing production code. It does **not** mean
PR #53 has been deployed. A separate V8.1 companion is not code integrated into
MAIN merely because MAIN contains its journal module.

Source keys resolve to exact immutable commits/files:

- **P** — [PR53 product engine, protected_frame / Directional.process](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/979f07aa3a000d66673aeb7cc24ef1c4c5272707/btc15_ladder_product_v1.py).
- **A** — [PR53 recovered authority, reduce_signal](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/979f07aa3a000d66673aeb7cc24ef1c4c5272707/btc15_directional_signal_authority_v1.py).
- **M** — [PR53 recovered manager, update / _strong](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/979f07aa3a000d66673aeb7cc24ef1c4c5272707/BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py).
- **N** — [unchanged native bot, EARLY / FINAL / true-SCALP / profit shadow](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/abe212b513827c8cec28a2f64e0161e79296bd82/bot_two_output_build_v4_13_profit_protection_shadow.py), blob `f547ab4238592910ed76fee61870cd18714d09f0`.
- **V** — [production V8.1 feed, publish_signal / quality_30_45 / confirmed / loop](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b05723ec622f901a05402ecf27f4d33505753ef1/v81_30_45_live_feed.py).
- **C** — [V8.1 companion feed](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/ccb2528e8e158010ef901741410cdc640cb82eb3/v81_30_45_live_feed.py), same entry/detector/lifecycle loop, new journal submission and route.
- **J** — [PR53 bounded journal worker](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/979f07aa3a000d66673aeb7cc24ef1c4c5272707/btc15_ladder_journal_v1.py).
- **S** — [PR53 SCALP journal processor](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/979f07aa3a000d66673aeb7cc24ef1c4c5272707/btc15_scalp_journal_v1.py); connected to V8.1 only in C.
- **I** — [existing informational clock](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/abe212b513827c8cec28a2f64e0161e79296bd82/btc15_information_v1.py).
- **E** — [offline V8.1 exit Lifecycle / POLICIES](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/abe212b513827c8cec28a2f64e0161e79296bd82/completion_audit/v81_exit_candidate.py), introduced `83c014a44523469988dbae079d9d636d61643e71`; research branch `fb40269fb3cb973deb3f987899dd466a3da287cc`.
- **G** — [older generalized SCALP protected adapter](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/btc15_protected_module_adapter_v1.py), blob `1ef4194cc9342b5ff14a59481399cf7ff2bbb094`; chronological EXIT latch commit `862ff089b603fb20380e3c8fda7181ceac9e7239`.
- **R** — [older serial state engine](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1.py), blob `06a4abed1a66ba61a1c9621dbc51259a34fcbee4`.
- **U** — [older SCALP management presentation](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/btc15_scalp_management_presentation_v1.py), blob `45bd5b58a652957d0d415797264aac09bc4f45f8`.

## All 26 requested capabilities

| # | Capability | Classification | Exact behavior present / missing, and source |
|---|---|---|---|
| 1 | EARLY ladder logic | IMPLEMENTED AND ACTIVE | P reproduces N's ask<=45c, fair>=75%, edge>=8 points, 2–10 minutes remaining, absolute BTC gap>=$25; required causal inputs gate availability. A creates an origin without a FINAL entry veto. |
| 2 | EARLY value-entry improvements | MISSING | No new value-entry alpha or increased opportunity frequency in PR53. The 50c target/25–35c ideal are display awareness. Removing the recovered manager's FINAL entry veto is a lifecycle correction, not proof of improved entry discrimination. P/A. |
| 3 | Independent FINAL ladder | IMPLEMENTED AND ACTIVE | P computes FINAL eligibility regardless of whether an EARLY origin exists. Core: fair>=90%, <=8min, gap>=$75 above6min otherwise$50, distance/range>=1, target-side and BRTI-side agreement. No clearance delay. Independent output is inside the shared product processor, not a separately fault-isolated publisher. |
| 4 | FINAL probability/direction/confidence/lock | IMPLEMENTED AND ACTIVE, PARTIAL | P publishes UP/DOWN probabilities, side, confidence, ready, and FINAL_CALL/PASS. It does not provide a separate durable lock lifecycle or a full weakening/MIXED/flip state model. |
| 5 | FINAL→EARLY helper/confirmation | IMPLEMENTED AND ACTIVE | P/A/M: immutable origin ID; FINAL publications explicitly carry it; strong same-side ready FINAL yields CONFIRMED. Origin-side probability and change from entry are included. |
| 6 | FINAL→EARLY deterioration warnings | IMPLEMENTED AND ACTIVE, PARTIAL | P/M: loss of previously strong confirmation latches PROTECT; never-confirmed origins get WATCH. Numeric confidence deltas are informational; no material-deterioration threshold or distinct CAUTION/EXIT action is selected. |
| 7 | Opposition/flip protection | IMPLEMENTED AND ACTIVE, PARTIAL | M latches PROTECT on any valid opposing side, even ready=false. It does not distinguish weak opposition from a qualified flip, and A explicitly rejects EXIT transitions. |
| 8 | MIXED/clearance | RESEARCH ONLY | Historical scoring files exist; P has only FINAL_CALL/PASS and no explicit MIXED/clearance lifecycle. Same-side loss of readiness can protect an origin previously confirmed, but that is not a clearance implementation. |
| 9 | SCALP/V8.1 entry | IMPLEMENTED AND ACTIVE IN EXISTING SEPARATE V8.1 | V retains 30–45c, fresh BRTI, V4+structure, CORE/SURGE, two qualifying observations within4s. C leaves detector behavior unchanged. This is distinct from the generalized detector behind G/R. |
| 10 | SCALP executable entry | IMPLEMENTED AND ACTIVE | V/C validate original same-side ask against immutable entry provenance. S records that original ask and identity. This is a quote, never a claimed manual fill. |
| 11 | SCALP HOLD | MISSING AS AN EXPLICIT MANAGEMENT STATE | V retains an active signal for180s but displays WATCH/ACTIONABLE/ACTIONABLE_EXPANSION/PROTECT based on current gain. An active flag is not the requested evidence-based HOLD guidance. Older explicit HOLD research exists outside PR53. |
| 12 | SCALP CAUTION | MISSING | No deterioration-based CAUTION transition in V/C/S. Older presentation price caution is not a live deterioration rule. |
| 13 | SCALP profit protection | IMPLEMENTED BUT SHADOW/INFORMATIONAL ONLY | N runs true-SCALP profit shadow; S records arms/giveback. G/R/U contain a real older shadow management state machine but are not integrated into PR53. |
| 14 | SCALP PROTECT | IMPLEMENTED BUT INFORMATIONAL ONLY IN V8.1 | V labels current gain>=20c PROTECT. It can disappear as gain falls: no running-peak latch/exit management. G's latched +5c arm is a different, recovered-but-unintegrated implementation. |
| 15 | SCALP EXIT guidance | MISSING IN PR53 | S sets exit_guidance=None and EXISTING_180S_LIFECYCLE_NO_SELECTED_STOP_OR_TRAIL. E and G have coded research exits, not connected V8.1 user guidance. |
| 16 | Executable exit-price guidance | MISSING | Current bid is displayed, but no selected EXIT event binds a reason/time/accepted quote and fresh executable exit price. No defensible range or fill is produced. G's adapter reconstructs bid from entry+exec_gain; direct accepted-quote binding is still needed. |
| 17 | Target behavior | IMPLEMENTED BUT INFORMATIONAL ONLY | V displays +5/+10/+20 levels. S records +8/+10/+15/+20/+30 hits. None terminates C's signal or releases serial ownership. N's +20 target belongs only to its shadow. |
| 18 | Stop behavior | RESEARCH ONLY | S records -10c comparisons; E contains an8c-target/10c-stop hypothesis. No selected stop action in V/C/P. Do not call a logged crossing an EXIT. |
| 19 | Trailing/giveback | RECOVERED BUT NOT INTEGRATED | G/R implement +5c arm/4c giveback and U exposes pullback protection. N has different10/20/6/4 shadow rules; E has5/2 and10/4 hypotheses. S only records peak/giveback; no selected executable trail. |
| 20 | Reversal | RECOVERED BUT NOT INTEGRATED | Older serial research classifies a later opposite-side qualified candidate after a terminal. V may issue an opposite signal after expiry, but no exit-linked predecessor/reversal lifecycle exists in C/S. |
| 21 | Re-entry | IMPLEMENTED AND ACTIVE, PARTIAL | V scans again after180s/rollover with20s same-side cooldown. G/R's explicit terminal-linked serial handoff is absent. S has no predecessor/terminal linkage for later entries. |
| 22 | 5M CAUTION | IMPLEMENTED BUT INFORMATIONAL ONLY | P/I: countdown flag at<=300s. It does not change entry, protect or exit behavior. |
| 23 | 3M GUARD RAILS | IMPLEMENTED BUT INFORMATIONAL ONLY | P/I: countdown flag at<=180s. No additional actionable guard rule is implemented by that label. |
| 24 | Flip-risk | IMPLEMENTED BUT INFORMATIONAL ONLY | P/I expose existing model probability against current target side. Not a separately calibrated reversal-risk probability or an executable exit trigger. |
| 25 | Permanent journals | IMPLEMENTED AND ACTIVE IN CANDIDATE, INCOMPLETE PRODUCT PROOF | J commits compressed events/checkpoint before JSON projection,16-item queue,30days/300k rows,512MiB DB limit. P stores origins/FINAL linkage and copies existing complete closeouts; S stores later-bid chronology. No live proof; V8.1 has no persistent volume yet. Full contract-slot denominator accounting and all terminal/serial guidance events are not completed. |
| 26 | Signal-only/no-order | IMPLEMENTED AND ACTIVE | P/J/S read/compute/journal/publish; no added order creation, routing, preparation or execution. V/C advertise manual-only/order_action=null. Safety flags support the boundary; flags alone are not proof of complete product behavior. |

## Additional recovery that the previous inventory missed

The prior “furthest state” conclusion was incomplete. A generalized SCALP
management/serial/UI stack was actually coded and operated in shadow, beyond
the standalone serial research scorer previously listed. It is not the same
system as V8.1 and cannot be silently relabeled as current V8.1.

| Recovered work | Exact identity | Coded / merge / deployment / supersession evidence | Causal validity and role in completion |
|---|---|---|---|
| Generalized ACTIVE→PROTECT→EXIT adapter | G; latch change862ff089b603fb20380e3c8fda7181ceac9e7239 | Coded. Current blob in b0999fc; absent from baseline and PR53. MAIN path-history query returns no commits, not a known MAIN revert. | Reuse chronological latch semantics. Existing code accepts exec_gain and candidate-linked rows, not modern independent contract/side/source witnesses. It needs a qualified adapter; not safe to call its old envelope current-source-qualified. |
| Serial terminal ownership | R; runtime projection1925121c35b57eca424c270c4755153ad2897137 | Coded, with recorded V5 shadow integration. Not merged into this MAIN lineage. Old primary-only restriction was superseded by serial handoff. | Reuse predecessor/terminal sequencing. ENDED_UNARMED is retirement, never sale. Armed/no-exit remains blocking. A new exit policy changes later opportunity membership and must be replayed as a whole. |
| Profit warning presentation | U; UI contractaeb5de49ea5edbbb2c8cd947299ad8a14a6ebfc4 | Coded on b0999fc, absent PR53. +5c arm visible, any positive post-arm pullback warns,4c crossing displays EXIT. | Reuse language/state mapping only after the policy and accepted executable quote support it. “Pure presentation” does not itself grant authority to make the decision. |
| V5 integration and earlier live shadow | [scalp_integration_state_bridge_v5.py](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/scalp_integration_state_bridge_v5.py), blobfbbec35d0119ecd7dca4f0be3a0f0024a8ec9a75 | [Sep15 checkpoint](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/BTC15_SCALP_SERIAL_LIFECYCLE_CHECKPOINT_20260915.md) records65-test Railway startup gate/live shadow preflight. It says NOT READY TO FREEZE, not promoted MAIN. These are historical checkpoint claims, not a new live verification. | Reuse existing integration structure where appropriate. Old15s event-envelope freshness is not the required5s BRTI source test; it must not replace corrected provenance. |
| Earlier HOLD/WATCH/TAKE_PROFIT/EXIT engine | [scalp_profit_protection_shadow_v1.py](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/b0999fc80219f16c32a37a822127ed9dc2ad809e/scalp_profit_protection_shadow_v1.py), blobaf3c975daabfe070e86012c15ee53fedea070498 | Coded standalone hypothesis. No MAIN path history; no production connection established. Not proven rejected merely because shadow. | Handles pre-expansion failure, momentum deterioration and profit zones. Numeric thresholds and permissive missing-BRTI handling are research assumptions, not selected product rules. Preserve as development evidence, do not copy wholesale. |
| Entry+profit policy/serial replay | [scalp_entry_profit_ladder_v1.py](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/14ef7cf264eb2e53246082038bd90eef9dde63da/shadow_diagnostics/scalp_entry_profit_ladder_v1.py), blob56bb8f74e2341dceb761d807c002772148f3d89a | Coded research: immediate/affordable wait/ideal entries;5/4,5/3,5/2,steplock,10/4 exits. Explicit no auto-selection. No promotion established. | Reuse serial replay, not a new fixed-origin optimizer. Legacy exit_gain can contain a terminal mark when no protected exit occurred; only protected_exit_gain is an observed protection exit. Admission must reject future/same-origin quotes and retain unresolved paths. |
| Economics/exit accounting | [scalp_economics_exit_cert_v1.py](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/ebae93d1260c9ec8a91de8a746a14b498972a1e1/shadow_diagnostics/scalp_economics_exit_cert_v1.py), blobc4d4f09adba1becec97ad4549e49ede6e0ca0563 | Coded research; realized protected bid separated from touches/unprotected marks; no auto-promotion. | Preserve gross-vs-fee-scenario separation. Historical fee assumptions have not been reverified here and are not current fee advice. No need to rebuild this scorer. |
| Watch-before-exit study |7d5bc7cfce61fb0ee1d2c67fc67c04ed096f212a, shadow_diagnostics/SCALP_WATCH_EXIT_WARNING_V1_FREEZE.md | Coded1/2/3c post-arm warning comparisons;4c exit unchanged; shadow only. | Provides development candidates, not a reason to select the best-looking exposed result. Existing any-pullback presentation U is separately recoverable. |
| FINAL protection collectors V1/V2/V4 | MAIN V1 blob3534af0e36847ed31e398e07cc5cb0e2bd0a8a45; V2 blob726975ab5f15f1ccf7e03e3d2207a3f421e2d67c; btc15_final_position_protection_shadow_v3.py blobb5533bc3c2812e4a4ed6103a1f0a35d8f2493fb1 | V1/V2 inea2a66e; later collectora2665e3 then low-memorya4b2036, data-path updatea4ff2b6. Filenamev3 contains V4. Coded/merged telemetry; not a hidden actionable exit policy. | Records FINAL trajectory/protection features. V1/V2 recovered CSVs were header-only. Does not create authentic immutable EARLY→FINAL linkage; never infer that linkage. Reuse field semantics as needed, not another collector. |
| Full directional manager and EARLY-only authority | manager750cd2298d21405aa51987d32f232779ae71d294; authority blob693f87cddc41de58d59088ea67a921db0861406f in9aa9ebf569c559a1e5daf7e8654738cfd7e957f8 | Actually coded; recovered into PR53. Earlier manager FINAL entry veto superseded by authority's EARLY-only origin. Old infrastructure blocker is distinct from evidence rejection. | Reuse origin/linkage/restart/latched protection. EXIT is explicitly unavailable; no native WEAKENING action. Product extension still required. |

## EARLY: evidence and remaining gate work

The Sept29 EARLY report identifies a concrete redundant gate: fair>=75% and
ask<=45c already imply edge>=30 points, so the8-point edge test rejects nothing
additional. Removing that redundancy alone cannot improve frequency.
The $25 gap and cheap-ask combination excluded every2–10m opportunity in that
recorded cohort. That identifies a coverage bottleneck, not evidence that a blind
gap removal yields reliable entries. The corrected architecture supplies causal
inputs; it does not retroactively qualify an old model or create missing targets.

| Earlier development | Exact source | Recorded disposition; completion use |
|---|---|---|
|1-minute feasibility / persistence | MAIN early_entry_feasibility_frontier_summary.txt blob269cdd8c138c888902be6769cd79108ccd4ae389; early_persistence_meta_summary.txt blob9b225cc4b9ae9c4f5deb9d3590103845950092b0 |41 fresh calls75.6%;19 fresh persistence calls78.9%. Recorded NOT READY; no85/90 claim. Already-coded alternatives, not missing implementation. |
| Projected crossing |a21e4bd0e1275de16457cac81098993f8a90756f, research_review/early_projected_cross_v1_20260920/RESULT.md |Explicitly rejected13/33. Attractive29.87c mean did not imply settlement quality. Original subminute dataset has known provenance limitations; not a current causal validation. |
| Target hold |b0810f637f1d722cd6adacccb94cd46ce7b2ad8c, research_review/early_target_hold_v1_20260920/RESULT.md |Explicitly rejected0/57: sustained target cushion and cheap price incompatible in that test. Do not repeat by small threshold loosening. |
| Tier expansion |fb1ff533811230b300af17e30dd0e91b1bb051ae, research_review/early_coverage_ladder_v1_20260921/REPORT.md |Coded A/B/C study; A zero; B/C additions failed reliability. Same native rule's September8/14 contrasts with August36/38; native is not established85% merely by retaining it. |
| Breakout/pullback renewal |543e7d960f1b8aeb9f7c7de2645f46d5b1e181ab, research_review/finishline_20260921/CLOSEOUT.md |51/147 affordable calls; coverage/follow-through instability; no stable candidate. SCALP quality filter in same study rejected for discarding too many opportunities/winners. |
| Later T1–T7/persistence/context |BTC15_EARLY_Value_Entry_Research_Report.pdf, recovered Sep29 report |Eight recorded-feature rules failed development selection. T1 28/84 and T7 15/47 descriptive pooled results. No re-opening rejected families without a genuinely different causal basis. |

This audit does not select the native EARLY as a finished value-entry product.
It establishes which prior proposals failed and which actual bottlenecks remain.
Remaining work is a bounded, evidence-backed gate decision, including honest
“no supported change” where warranted; it is not a license to claim85% or merely
increase call count. The extra cheap-motion, runway and preprice branches have
been located at d31922b4,7d07b17c and0a2a8cdd; their complete outcome artifacts
are not yet adjudicated by this corrective audit. Recovery must not be called
exhaustive before those dispositions are checked.

## FINAL/MIXED: preserve both roles

Keep independent probability/call separate from origin-relative guidance.
PR53 does not yet distinguish strengthening, same-side weakening, MIXED,
loss of confirmation, weak opposition and qualified opposing FINAL as separate
transition reasons. It also supplies no executable directional EXIT rule.

The Oct3 package reconciles two different historical policies: clearance within45s
was21/23; delay at least45s was22/22 on a selected in-sample grid. These are not
interchangeable, and neither justifies delaying independent FINAL or inventing
origin protection. Source: frozen score_final_mixed_45s_union_impact_v1.py
blobfa28c81357f9522e9469faa9eae5978018886468 and
score_final_mixed_delay_recheck_v1.py blobb7920f818824cb5378f128bd130b8d1d899797f7.

The Sept29 FINAL report has zero evaluable authentic protected linked trajectories.
It supports reuse of code semantics and rejects invented linkage; it does not
prove a numeric75/60 warning/exit policy or disprove every future helper design.

## Oct3 SCALP evidence: useful development evidence, no selected policy

The supplied package's requested_ladder_analysis.json explicitly says
DESCRIPTIVE_ONLY_NOT_PROMOTABLE and policy_selection=NONE. Failed Oct3 Ground
Zero intervals remain excluded. The following figures retain their original
fixed-origin definition and are not current V8.1 performance:

| Target versus -10c | Serial103 origins: target-first / stop-first | Native true-SCALP76 origins: target-first / stop-first |
|---|---|---|
|+8c|83 /9|70 /5|
|+10c|79 /10|70 /5|
|+15c|66 /12|64 /7|
|+20c|43 /14|54 /9|
|+30c|20 /15|36 /10|

Unresolved/unavailable origins are not silently added to successes. Serial
complete paths99; native66. Mean sampled MFE/MAE: serial+19.29/-4.74c,
native+27.47/-3.25c. The older serial5/4 review records57 exits,11 unarmed
retirements,34 armed/no-exit and1 incomplete;51/57 exits overshot the4c trigger.
Those are concrete lifecycle weaknesses to address, not grounds for throwing
away the state engine or automatically promoting another threshold.

## Product gaps to resolve before qualification

1. Finish the remaining EARLY recovery/disposition and make an explicit gate
   decision using existing evidence. Do not represent baseline safety as85% quality.
2. Extend the recovered directional lifecycle with separate origin-relative
   warning reasons and a defensible exit decision, while preserving independent
   FINAL output. Missing data must remain UNAVAILABLE, not market deterioration.
3. Reuse the recovered SCALP manager/serial/presentation components rather than
   rebuilding them. Bind every gain and exit to original ask and a strictly later
   accepted same-contract/side bid; distinguish trigger level from observed bid.
4. Resolve pre-arm failure, target/stop/trail choice, horizon terminal, armed-no-exit,
   reversal and re-entry ownership together. Test the entire chronological
   detector+management+serial path; fixed-origin target scores cannot do that.
5. Integrate guidance into the established three-ladder display. PR53's appended
   panel is not the recovered integrated SCALP UI or a completed mobile product.
6. Complete contract denominators, missing intervals and every selected lifecycle
   event in the existing lightweight journals. Do not build another recorder.

No numeric policy was selected or changed in this audit. No test, qualification,
deployment, order, prospective waiting campaign or Ground Zero work was started.
The received correction ends at “The guidance should answer the practical
question:”. The missing remainder is needed before interpreting the final
protection/exit requirement as complete.
