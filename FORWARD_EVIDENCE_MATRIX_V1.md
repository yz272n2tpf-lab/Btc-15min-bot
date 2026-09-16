# BTC15 Forward Evidence Matrix V1

**RESEARCH GOVERNANCE ONLY · NO PRODUCTION LOGIC · NO ORDERS**

Purpose: keep every prospective evidence stream separate so coverage, movement, timing, economics, calibration, and user-warning evidence cannot be blended into a misleading overall PASS.

| Stream | Frozen cutoff / start | Primary denominator | What it may answer | Review-size marker | What it may NOT do |
|---|---|---|---|---|---|
| Coverage Rescue Forward V1 | 2026-09-16T05:00:21Z | All fully observed future contracts | Incremental true-contract coverage from one frozen rescue rule; <=50c coverage; +5/+10/+20 context | Existing frozen forward rule | No same-sample retune or automatic promotion |
| Economics Forward V1 | Frozen prospective economics cutoff | Future serial opportunities / protected exits, plus true contract context | Executable protected-exit economics after fees for frozen +5c arm / 4c giveback | Frozen lane-specific review gates | +10 touch is not realized profit; no automatic promotion |
| Regime Observation V1.1 | 2026-09-16T11:03:16Z | Fully observed future contracts | Incidence and descriptive economics of fixed corrected regime tags | 100 full contracts + 50 protected exits | Historical repaired holdout cannot select a rule; no tag retune |
| Candidate->Verify Forward V1 | 2026-09-16T11:10:33Z | Fully observed future contracts and unchanged immediate serial opportunities | Cost/benefit of IMMEDIATE vs 5/10/15/30s confirmation using actual delayed ASK and subsequent BID | 100 full contracts + 100 immediate signals + 50 30s-verified signals | First sample cannot select/promote a delay |
| Flip Risk V2 | Existing future-only V2 start | Fresh settled prediction-complete contracts / review predictions | Probability calibration, reliability, high-stay behavior, time buckets | >=30 contracts + >=240 predictions plus frozen quality gates | Numeric Flip Risk remains user-facing disabled until later manual display review |
| Watch->Exit Warning Forward V1 | 2026-09-16T11:48:06Z | Fully observed future contracts / armed serial signals | Whether 1c/2c/3c post-arm Watch warnings precede the frozen 4c Exit with useful lead time; false warnings/recoveries | 100 full contracts + 50 armed signals | Cannot select a Watch lane; cannot alter frozen Exit |
| Opportunity Density Forward V1 | 2026-09-16T11:56:59Z | ALL fully observed future contracts, including quiet contracts | 0/1/2/3/4+ opportunity frequency; any/<=50c/25-35c coverage; timing zones | 100 full contracts | Density readiness is not a performance PASS; movement is context only |
| Pullback Entry Forward V1 | 2026-09-16T12:05:59Z | Fully observed future contracts and unchanged immediate serial opportunities | Whether a real executable ASK <=50/40/35c appears within 30/60s and what executable movement remains after actual entry | 100 full contracts + 100 immediate opportunities | Development sample cannot select/promote a pullback lane |

## Global interpretation firewall

1. **No blended accuracy or score.** FINAL accuracy stays separate from EARLY utility, scalp movement, coverage, economics, calibration, timing, and warning studies.
2. **True denominators stay true.** Quiet fully observed contracts remain in coverage/frequency denominators when the study definition requires them.
3. **Movement is not profit.** A +10c touch is never relabeled as realized +10c profit.
4. **Readiness is not PASS unless the frozen study explicitly defines a quality gate.** Sample-size readiness only means enough observations for manual review.
5. **Development samples cannot certify rules they select.** Any rule selected after reviewing a comparison/development window must be frozen and tested on a new future certification window.
6. **Historical repaired/observed holdouts do not become untouched again.** Once seen, they are descriptive only for later semantic repairs or changed rules.
7. **No automatic promotion.** Production logic, dashboard behavior, numeric Flip Risk visibility, and signal suppression/rescue require separate explicit manual review.
8. **No orders.** Every stream is signal/research only; user execution remains manual.

## Decision sequence when samples mature

For each stream independently: verify collector integrity -> verify prospective cutoff/denominator -> verify sample readiness -> read its own frozen metrics/gates -> record a stream-specific manual decision. Only after all relevant stream decisions exist may an implementation proposal be drafted, and that proposal must state which evidence supports each behavior separately.
