# BTC15 V11 read-only live timing baseline — 2026-10-15

**Production deployment decision: NO-GO.** This is an observational baseline, not V11 deployment validation.

## Verified sources
- Railway production project `noble-warmth`: 15 services; MAIN, V81, primary BRTI, cockpit latest deployments SUCCESS; seven storage volumes preserved.
- A staged Railway patch from 2026-10-08 remains untouched.
- MAIN logs: latest 500 BRTI DELIVERY-filtered messages spanning approximately 19 minutes. The filter mixes `BTC15_BRTI_DELIVERY_V1` with `BTC15_DELIVERY_HEALTH_R1` diagnostic messages.
- In one read: 424 decision-delivery events, 76 diagnostic health messages. A separate read returned 425 decision-delivery events and 76 health messages due to the moving log window.
- Among the 424 decision-delivery events: source-age median ~1.69 s, p90 ~2.74 s, maximum ~3.82 s, none >5 s. The metrics apply to *observed decisions*, not every clock second or complete contracts.
- Decision-delivery spacing (exclude health messages): median ~2.50 s, p90 ~3.66 s, three intervals >5 s, two >10 s, maximum ~113.59 s. The maximum may span rollover or missing logging; do not interpret it as a continuous execution pause without source verification.
- MAIN last-hour CPU average ~1.93 vCPU and RAM average ~2.85 GB. These are production baseline figures, not V11 measurements.
- The isolated V11+V3 research acceptance workflow at commit `ece046178b05ebe6ae963c81e251285578cf3244` passed 60/60. The newer synthetic rollover acceptance run `38809884834` passed 26+34=60 tests. The synthetic rollover test does not check real Kalshi contract target, live quote publication, FINAL/EARLY/SCALP outputs, or source-clock equivalence.

## Acceptance gaps
1. Audit an isolated, immutable copy of the actual MAIN journal and closeout history for duplicates, conflicts, retention gaps and settlement identity.
2. Compare original and optimized outputs on the *same* replay fixtures: contract start/target, BRTI timestamp, Kalshi quote age, FINAL/EARLY/SCALP decisions, published timestamps and no-order guarantees.
3. Verify >=10 complete 15-minute rollovers on real-source replay; do not substitute 10 synthetic boundaries.
4. Measure baseline vs candidate per-child CPU/RAM and true-source-to-publication latency; demonstrate improvement without harming early-entry timing.
5. Establish reversible, owner-first deployment with backup/rollback and zero changes to ladder thresholds.

**No Railway deployments, restarts, journal writes, model changes, or orders were performed.**
