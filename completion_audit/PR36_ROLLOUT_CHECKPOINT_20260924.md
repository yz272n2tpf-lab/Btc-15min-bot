# PR36 controlled rollout checkpoint — 2026-09-24

**Initial live data-path acceptance PASS. Performance acceptance remains pending. Runtime is frozen. SIGNAL ONLY / NO ORDERS.**

- Approved candidate: `e02f7373415f42f2738825cd8720abbf45c69b68`.
- Merged PR36 / production commit: `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`.
- Exact tested release tree: `586f8cfd635d6ed817c63202cdec0b8bcc454e0c`.
- Railway deployment: `f82466d0-70ab-4779-a0fd-58832ad31513`, SUCCESS.
- Deployment created **19:51:42.581 UTC**; container started **19:53:40.642993804 UTC**; dashboard runner started **19:53:46.605580681 UTC**; Railway SUCCESS **19:53:51.576 UTC**; core loop started **19:54:18.990766070 UTC**.
- Rollback remains `1730ceff180394fbd2ebae7a5fddc4acd1e76194`, deployment `454f53ad-b269-4133-b0f5-60098978db71`, preserved branch `rollback/btc15-before-pr36-20260924`. No rollback was required.

## Frozen prospective boundary

Use the immutable [boundary manifest](PR36_PROSPECTIVE_BOUNDARY_20260924.json). The 19:45 slot is mixed/restart; the 20:00 slot is conservatively warmup/infrastructure-only. **First full prospective corrected contract opens at 20:15 UTC.** This rounds core-loop startup plus six minutes up to the next official boundary.

Keep 20:15, 20:30, 20:45 and 21:00 contracts separate from all pre-correction evidence. The fixed validation end remains **21:15 UTC on September 24**. No tuning after **17:00 UTC**. Preserve subsequent reserved validation and untouched holdout through **October 9, 21:15 UTC**. Any restart or code/config/model change ends this uninterrupted runtime identity. Do not retune the running candidate.

## Verified checks

- Exact CI merge tree equals candidate and actual production merge tree. [Hosted CI36047874781](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/36047874781): **238/238** passed. Focused local checks: **44/44**, 3.378 seconds. Weights, thresholds, five-second BRTI limit and original decision timestamps unchanged.
- Preserved existing archive and /data mount. Main volume10GB; clean collector50GB. Main authenticated Kalshi read HTTP200; direct main BRTI upstream explicitly skipped.
- Frozen fair weights `95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6`; artifact `1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816`; **NO STARTUP FIT** for this fair artifact.
- From19:54:24.113222 through20:01:25.231306 UTC: **72/72 reviewed BRTI decision records ready**, source age1.116–3.353s, median2.156s. Zero source/receipt/decision/check chronology or freshness violations. These are decision samples, not continuous availability or full-universe coverage.
- **22 parity PASS / 6 WAIT** in the fixed observation interval. WAIT correctly covered expired or absent quote proof and the prior-contract snapshot during rollover; it is not an alignment PASS. All PASS records had clock0.0s, target$0.00, quote0.0c deltas and BRTI publication match.
- Twelve reviewed fair-value heartbeats contained fair output, including the next contract after a real late-window empty-book interruption.
- Two read-only hosted HTTP jobs passed: [startup36051568832](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/36051568832), [incremental36051964425](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/36051964425). **63 corrected input frames** across two runtime contracts verified exact journal identity, range SHA256, fixed per-contract target, causal BTC clocks and model hashes. Historical rows were excluded, not relabeled.
- The **71.05251-second input-journal gap** during late empty-book WAIT and new-book initialization remains a real gap. No fill-forward or fabricated freshness. Fair output resumed at the first usable new-contract decision.
- One localhost client disconnect caused a startup BrokenPipeError; subsequent HTTP200 plus hosted health/manifest/export checks passed. No persistent endpoint failure observed.
- Owner13 heartbeat samples remained PRIMARY_OK/clean, ages0.912–2.911s, zero429s and ten unchanged historical recovered errors. Owner was not restarted. Clean collector remained same deployment/run; one restart checkpoint had3/4 source fetches and later checkpoints4/4, with preserved sequence.
- Existing main-branch subscription rebuilt V6 parked service. Its unchanged PARKED sleep/no-polling command and startup message were verified. It did not become an active upstream owner.

## Warmup rollover at20:00 UTC

Exact ticker `KXBTC15M-26SEP241615-15`; official20:00–20:15 UTC; fixed target$84,372.51.

| Stage | Seconds after open |
|---|---:|
| Exact-ticker staged handoff |4.960|
| Target and BTC ready |5.104|
| Timestamped book |5.330|
| Contiguous quotes usable |10.219|
| Source snapshot |10.220|
| First causal fair-input decision |10.217|
| Full parity PASS |22.671|

This shows the installed BTC-history/BRTI path operating through a real quote wait and rollover. It is **not** a quantified reduction of the former5/15 missing-fair defect across a completed prospective cohort, and does not prove trading improvement. Do not count this warmup slot as one of four full corrected validation contracts.

## Continue collection; no further mutation or tuning

Only elapsed prospective evidence remains for this controlled-rollout stage:

1. Verify four complete consecutive20:15–21:15 contracts against each readiness stage, causal source qualification, parity and fair continuity. Record all missing/offline/WAIT periods.
2. Measure fresh-input eligibility separately from model/gate rejection on this exact runtime; do not compare selected decision samples with the old all-observation denominator.
3. Evaluate EARLY, FINAL and both-direction SCALP/V8.1 and connected exits prospectively. MFE is not realized profit; retain stop-first chronology and fees. No93–95% claim from tiny or uncertified samples.
4. Keep runtime frozen. Roll back on verified candidate acceptance failure; do not improvise a production patch.

Full machine-readable evidence: [initial live acceptance](PR36_INITIAL_LIVE_ACCEPTANCE_20260924.json).

Next exact-feature export: identity `7b9f685f1a3bedfb3afed0dfdb7163806e42dc9ace3ac035ce08870713da0996`, offset **4446952**, max range1048576. Current endpoint is plain NDJSON with range SHA256, not gzip; gzip CRC applies to the separate clean common export.

Clean common collector remains `clean-source-v2-1s-20260923` / deployment `df8385ff-46a2-4dfb-af0a-07c25e5382aa`; never combine the former five-second run. This turn used minute collector checkpoints, not a fresh complete raw common export. Preserve its existing independent incremental-export checkpoint.
