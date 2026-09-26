# Joint ladder diagnosis and correction — September 24, 2026

The accumulated cohort supports a concrete diagnosis, not a performance certification. **822 gate configurations were tested on tuning data; none justified changing production thresholds or weights.** A separate input-timing defect was reproduced, corrected, regression-tested, deployed through PR32, and verified live. SIGNAL ONLY / NO ORDERS.

## Evidence and separation

- Parent frozen cohort: `fcc75fdc1ace0f31e959d59f5038cfaa530da6147e0870e5b811246ba2d0163e`.
- Exact collector: `clean-source-v2-1s-20260923`, commit `e98576f23e247349b90717aea3a3ad832d409354`. No five-second-run pooling.
- Immutable downloaded prefix: **410,496,309 bytes**, SHA256 `decabbc24c8ec0fedcd7b4eb1f0b538c38d07249d977bebd0d20e8d7b4726bde`. **84,266 gzip members passed CRC; zero damage.** All 72 new bounded ranges passed SHA256/offset checks. Prior 123,094,707-byte prefix and its SHA256 remain unchanged.
- Analysis interval: Sep24 **00:15–12:15 UTC**, main revision `d543219`, frozen weights `95fc4e89…520ba6`. **43,194 observations per service**, four services, zero observed HTTP failures; maximum request gap **1.203 seconds**, no gap over 1.5 seconds. This is sampled evidence, not continuous availability. There are **20,661 clean input observations**; those inputs are not themselves a one-second continuous book tape.
- Precommitted split: **26 tuning contracts, 00:15–06:45**; one purged slot **06:45–07:00** retained in the parent calendar; **21 internal-validation slots, 07:00–12:15**, of which **13 official contracts and eight missing-official slots**. All eight expected market endpoints returned 404; label responses and hashes are preserved separately. The purge is not silently counted as a production PASS.
- Candidate lock `ca9e1b410b797cb931dd88f14bab6e385c60936576fb4be401867659c4d035c8` was committed before opening internal-validation labels. Original Sep24 21:15 validation and Sep25–Oct9 untouched holdout were not analyzed. No selection/refitting on internal validation.
- Counts below use first qualified call per lane/contract at the actual observation time. Gate attribution uses **4,100 unique qualified source frames** in tuning, avoiding inflated independent sample claims from repeated cached reads. **Zero mismatches** between replayed baseline gates and published raw gates, in both partitions.

## What the three ladders do

They are distinct action families sharing the target-aware fair model, not three independent model votes. No invented voting weights or ladder removal is warranted.

| Ladder | Existing inputs and gates | Unique role and principal failure mode |
|---|---|---|
| FINAL | Preferred fair ≥90%; ≤8 minutes left; gap ≥$75 above6 minutes, otherwise ≥$50; distance/recent5m range ≥1; target-side agreement; true BRTI authority outside ±$11 and same side; qualified quotes/publication | Eventual outcome anchor. High confidence and distance gates select very expensive contracts; no DOWN prediction reached90% in the tuning slice. |
| EARLY | Preferred side ask ≤45c; fair ≥75%; edge ≥8c; 2–10 minutes left; absolute gap ≥$25; qualified source state | Favorable entry before FINAL. Preferred side is usually already expensive; the learned reversal probability cannot reach the75% gate. |
| SCALP/reversal | Core: ask≤70c, fair≥52%, edge≥0,3–10m left,gap≥$50. Separate V8.1:30–45c, timestamped contiguous quotes, BRTI≤5s, publication≤3.5s, short BTC/BRTI impulse, acceleration,30s structure, CORE/SURGE route and two confirmations within4s | Executable movement rather than eventual outcome. Core's gap requirement selects costly sides. V8.1's impulse plus near-static quote requirement rarely coexists after replacing stale REST prices. Both directions preserved. |

The forest has900 trees; its sigmoid coefficient is2.99105798 and intercept−2.27863390. For any raw forest flip probability in[0,1], calibrated flip lies approximately[9.291%,67.094%]. Therefore maximum stay confidence is **90.709%**, barely above FINAL's90% gate. A preferred reversal side cannot reach EARLY's75% gate. These are mathematical output limits of the current model, not evidence that confidence should be boosted.

Tuning UP predictions:1,659 frames, maximum90.683%,324 frames≥90%. DOWN:2,080 frames, maximum89.242%,**zero≥90%**. Another361 qualified source frames lacked a preferred model side. The same model supplies all core ladders, so their confidence errors are correlated. Changing a monotone calibration scale would largely restate a confidence-threshold change; it would not independently improve ranking.

## Suppression, overlap and incremental contribution

| Ladder | Failed tuning-frame gates (overlapping counts) | Sole blocker / controlled ablation |
|---|---|---|
| EARLY | ask3,835/4,100; fair2,290; time1,676; gap1,199; edge3,183 | Ask alone blocks162 frames. Removing only ask yields15 calls,9 correct, median68c—fails attractive-entry objective. Removing only gap yields2 calls,0 correct. Removing only fair produces no calls. |
| FINAL | fair3,776; ratio3,531; gap2,709; time1,966 | Fair alone blocks283 frames; ratio alone83. Removing only fair gives14 calls,13 correct, median91.3c. Removing ratio gives6 calls,5 correct. Expensive near-certainties cannot certify the product goal. |
| Core SCALP | gap2,253; edge2,078; time1,974; ask1,975 | Gap alone blocks648 frames. Removing it gives20 calls,14 eventual-direction wins, median63c. Removing fair changes no first calls in this slice, but does not prove global redundancy. |
| V8.1 |8,059 in-band qualified source frames;7,828 feature-ready. CORE/SURGE route fails7,996; BTC5 fails7,250; BTC15 fails7,122; BRTI5 fails7,147; structure fails5,634; ask5 fails3,025 | Only3 frames are blocked solely by route and1 solely by ask5. The overlap of impulse, lag and route constraints is the bottleneck; feature warm-up is not the main explanation. Baseline produces0 entries. |

Tuning observed union: **13/26 contracts**. FINAL adds4 uniquely; core SCALP adds9 uniquely; EARLY adds0. No pairwise contract overlap in this segment. In internal validation, the baseline union is8/13 official contracts: FINAL adds1 unique contract; SCALP adds5; EARLY's one contract overlaps SCALP; FINAL/SCALP overlap one contract. This is descriptive incremental coverage, not causal feature importance. Full failed-gate intersections, leave-one-gate-out results and12 locked joint core-ladder combinations are in the JSON reports.

## Baseline performance, kept separate by partition

| Lane | Tuning: calls / official; direction correct | Tuning median ask / minutes left | Internal validation: calls / official / scheduled; direction correct | Validation median ask / minutes left |
|---|---|---|---|---|
| EARLY |0/26; unavailable|Unavailable|1/13/21;1/1|33c /7.229m|
| FINAL |4/26;4/4|97.9c /5.377m|2/13/21;2/2|99.8c /1.324m|
| Core SCALP |9/26;6/9|69c /8.933m|7/13/21;6/7|68c /9.411m|
| V8.1 |0/26|Unavailable|0/13/21|Unavailable|

FINAL accuracy intervals are extremely wide: tuning4/4 Wilson95%[51.0%,100%]; internal validation2/2[34.2%,100%]. Calls are expensive and validation calls late. **This does not demonstrate the93–95% goal.** Historical263/278 remains uncertified.

EARLY's validation33c entry had sampled MFE+66.8c and MAE−17c. One call cannot establish calibration or coverage. Core SCALP tuning:4UP/5DOWN, mean sampled MFE+13.59c, MAE−27.51c;7/9 positive excursions,6/9 reached+10c. Internal validation:5UP/2DOWN, mean MFE+19.96c, MAE−20.29c;7/7 positive excursions,6/7 reached+10c. Eventual direction is secondary for SCALP and is not an exit/profit statistic.

Excursions use independent timestamped clean **bid minus entry ask**, require true BRTI≤5s, and are censored. Gaps reach27.03s in baseline tuning paths and19.04s in validation paths. Subsequent asks do not always confirm the recorded entry price. No fills, complete paths, fees-adjusted profit, or executable availability between samples are inferred.

At fixed validation clock anchors, model preferred-direction accuracy is75% at8m,75% at5m and83.3% at2m (12 contracts each); Brier scores0.1783,0.1698,0.0957. Repeated time anchors are not independent contracts. Failure tickers, directions, reversal-state labels, volatility and per-call paths remain in the machine-readable report.

## Batch search and separate validation

The bounded grid tested192 EARLY configurations,288 FINAL,288 core SCALP and54 V8.1: **822 total**. Identical first-call sets were grouped, leaving26/159/68/16 distinct sets respectively. All source/ticker/freshness protections remained fixed. Single-gate ablations are attribution only; safety-gate ablation was prohibited. The shortlist was frozen before validation; no runner-up was selected after seeing validation.

| Locked diagnostic probe | Tuning result | Internal validation result | Decision |
|---|---|---|---|
| EARLY≤50c,fair60%,gap$11,existing2–10m |5/9 directional wins, median43c |2/6 wins, median45.5c |Reject threshold promotion. |
| FINAL fair87.5%,ratio1,≥2m left,gaps50/25 |9/9, median96.3c |3/3, median98.3c |Too small and already expensive; not a defensible product improvement. |
| FINAL fair87.5%,ratio.5,≥2m left,gaps50/25 |12/13, median93c |6/7=85.7%, median83c |Misses accuracy objective; reject. |
| Core cheap-path≤50c,gap$11,3–10m |9 contracts,5 direction wins,median42c |9 contracts,5 direction wins,median46c;6 reached+10c |Price/path improvement is exploratory; coverage timing, adverse movement and exits not validated as an overall improvement. |
| V8.1 half route floors,ask5≤3c/ask15≤5c,2 confirmations |2 entries;1 sampled+10c |4 entries;3 sampled+10c;1 eventual-direction win |Insufficient sample, substantial adverse movement; keep research-only. |
| Same V8.1 single-observation control |10 entries;7 sampled+10c |9 entries;5 sampled+10c |Confirmation relaxation increases false-positive exposure; no promotion. |

Neither model refitting nor a forest-weight search is defensible from the old journal: it did not preserve the exact20-feature vectors and BTC receipt provenance used for each inference.43,194 repeated observations are not43,194 independent outcome labels. Reconstructing different input histories and calling them the same runtime would invalidate the comparison. PR32 now preserves those vectors for future analysis. No ladder is declared redundant or removed.

## Exit/protection diagnosis

The four existing PR26 hypotheses were applied separately to the locked V8.1 hypothetical entries. On the persistent probe's4 validation entries,5c-arm/2c-giveback produced4 observed protection marks averaging+5.75c. The8c-target/10c-stop produced3 stops and1 target, average−6.5c. The10c-arm/4c-giveback had2 marked exits and2 unpriced horizons. These are sampled hypothetical marks, not selected live advice or profits. Missing horizon quotes remain missing; they are not silently converted into fills.

The disagreement shows why choosing an exit from favorable MFE alone would be wrong. **Actual V8.1 published entries remain0; actual connected stop/protection acceptance remains open.** No exit threshold was selected on validation.

## Coordinated correction and live check

Main captured `now` before its BTC HTTP read. Its causal feature reader then excluded the newly received tick, while target/entry gates used the new tick. In tuning, absolute target-gap versus model-distance mismatch was median$3.73,p95$19.547,max$76.93;21 strong-confidence frames disagreed with the contemporaneous target side. This was a caller timing defect, not a reason to allow future inputs.

[PR32](https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/32) moves the decision cutoff after validated BTC receipt, fails closed across close/future/stale inputs, retains source and receipt clocks separately, and appends exact model inputs to `/data/kalshi_fair_input_frames_v1.jsonl`. It leaves frozen weights, thresholds, entry/target/settlement semantics, staged rollover, BRTI≤5s, V8.1≤3.5s, and signal-only behavior intact.

- Head `79ac5a0276b0d3d3336ebfc4c9b0b0a351e01c40`; merge `1730ceff180394fbd2ebae7a5fddc4acd1e76194`.
- Hosted CI [36001671100](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/36001671100): SUCCESS. **208 runtime regressions,29 audit regressions,three static path/authority gates PASS.** Diagnosis branch:40 analysis regressions PASS, including8 new separation/accounting checks. An initial targeted audit invocation had2 import-path errors; the corrected full audit invocation passed29/29. No failed test result is concealed.
- Railway deployment `454f53ad-b269-4133-b0f5-60098978db71`: SUCCESS. Startup12:54:43.752856839 UTC confirms identical immutable weight/artifact hashes and **NO STARTUP FIT**. Prior `d543219` / deployment`0b2ef3ff-1499-432a-ac70-52b997bb2e26` remains rollback evidence.
- Existing evidence archive reported PRESERVED_EXISTING; main10GB and clean50GB persistent mounts remain. Owner, V8.1 and clean deployments were unchanged.
- **22 distinct new producer frames** had gap-distance mismatch median0,max1.42e−14 dollars. Live parity returned PASS with clockΔ0,targetΔ$0,quotesΔ0c and matched true BRTI publications. This is a short integrity check, not new contract/performance acceptance. External ad-hoc client sampling had timeouts; they are preserved and not misattributed to production downtime.
- The first post-correction boundary, **13:00 UTC**, staged the exact ticker at **+0.675s**. Official target plus BTC were ready at **+15.911s**, contiguous quotes at **+26.135s**, and the first logged full parity PASS at **+32.123s**. The earlier target-readiness event had `target_ready=false` and is not counted as success. This partial boundary does not establish a completed contract or four-rollover acceptance; raw events are in `PR32_BOUNDARY_20260924T130000Z.json`.

## Forward checkpoint and remaining blockers

The old main identity closes at restart.12:45–13:00 is mixed/late join;13:00–13:15 is warm-up/transition. Both stay in the parent calendar. New immutable cohort `btc15-causal-cutoff-20260924T131500Z`, hash `fc61b525e2c50e0d6023a2ddb9be8d1bfceb9ad930564236e34a79c66f3681a7`, begins13:15 UTC. Tuning ends17:00; purge17:00–17:15; internal validation17:15–21:15. Original reserved validation and October holdout boundaries remain fixed. Do not slide windows or pool revisions.

1. Measure new aligned-input contracts and source-qualified coverage before any further threshold/weight selection. First rerun baseline and gate diagnosis; do not recycle the rejected threshold probes as validated candidates.
2. Publication/source availability remains distinct from owner health: pre-correction12h main had15,883/43,194 combined-qualified sampled responses. This includes the eight missing slots. Owner was PRIMARY_OK in43,180/43,194 samples,14 error samples, cumulative errors7,zero429; median source age1.906s,p95 3.074s,max13.181s during interruption. Five-second producer cadence plus true-source age can still make retained frames ineligible; do not fake freshness or equate parity with continuous usable publication.
3. Obtain≥4 complete rollovers on the new code identity, with target/book/source/parity/publication milestones separate. Prior acceptance is retained as historical evidence, not reused for PR32 acceptance.
4. Useful EARLY coverage/entry quality; FINAL coverage/timing/calibration and meaningful held-out accuracy; both-direction SCALP false positives and adverse paths remain unaccepted. The data demonstrate the bottlenecks, not conflicting goals proven impossible.
5. Select and connect V8.1 stop/protection only after valid fresh entry/path evidence supports a policy. Current hypothetical marks cannot certify actual integration. Preserve reversal behavior and both directions.
6. Carry forward existing effective-restart-policy/raw-reference visibility limits, long-run retention/recovery scope, and exact historical research-crash causes. No obsolete service was restarted, no evidence/service deleted, no credential created/rotated and no order capability added.

Fresh corrected-cohort evidence is the next dependency for defensible performance work. This checkpoint does **not** claim that waiting alone completes the remaining engineering or certifies the bot. Final visual dashboard development remains separate.
