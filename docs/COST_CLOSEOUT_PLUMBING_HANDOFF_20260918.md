# COST CLOSEOUT + PLUMBING HANDOFF — 2026-09-18

## Hard engineering rule
Lowest sustainable monthly cost without sacrificing bot correctness, speed, freshness, reliability, integrity, signal behavior, coverage, timing, evidence or goals. ~$20/mo is a target, not a floor. Pursue below $20/mo whenever safely possible; never use cost reduction as permission to weaken the bot. Any cost optimization that worsens semantics/freshness/latency fails.

## Cost work already proven
- Railway billing showed egress was dominant historical cost: $227.79 / 4,555.71 GB at captured billing boundary.
- Internal scalp export paths moved away from public egress; V2 observed zero public TX in canary measurements.
- V2 incremental evidence service ~0.05 GB RAM.
- Retired mature/temp services: scalp-economics-forward-v1, scalp-economics-exit-review-v1, scalp-entry-profit-review-v1, scalp-ladder-research-v1, regime-incremental-canary-temp.
- Roughly ~14 GB average RAM removed from those five measured services.
- Protected production main remains untouched.

## Current one high-leverage optimization
Branch: main-runtime-artifact-canary-20260918
Goal: preserve exact fitted general RF + target-aware fair RF + sigmoid, but remove repeated live retraining/history reconstruction.
Acceptance: exact semantics; probability diff <=1e-12 on captured parity rows; same/faster state freshness/latency; lower RAM/CPU; no new public internal egress; NO ORDERS.
Temporary service: main-runtime-artifact-canary-temp.
Protected main: Btc-15min-bot remains control.

## Immediate finish line
1. Clean artifact-builder run (freeze marker + no canary storage crash).
2. Certify emitted fitted artifact through SHA/spec/feature/probability parity gate.
3. Reuse temporary service as fast artifact runtime canary.
4. Compare protected vs fast: outputs, Kalshi boundary, BRTI decisions, freshness, latency, startup/recovery, RAM/CPU/network.
5. If parity/performance passes, establish production replacement path and measured monthly run-rate.
6. If further savings would harm performance/integrity, stop and review tradeoff with user.
7. COST PHASE CLOSED.

## Next phase — no drift
Return immediately to plumbing/infrastructure:
- BRTI HTTP 429/freshness/heartbeat behavior.
- provider timeout/reset resilience.
- exact Kalshi KXBTC15M contract/start/target/rollover alignment.
- source timestamp -> compute -> published state latency.
- EARLY -> FINAL continuity and scalp synchronization.
- restart-safe logging/scoring.
- health checks that prove fresh/correct data, not merely process-online.
Then untouched end-to-end certification, then ladders/performance work.

Signal-only/manual execution remains non-negotiable. NO ORDERS.

## Permanent budget governance — user-approved 2026-09-18
- Prevent recurrence of runaway Railway cost as a permanent operational requirement.
- Normal objective: remain within the agreed operating budget at all times.
- No intentional architecture/service change that is expected to exceed the agreed budget without discussing the expected cost/performance tradeoff with the user first.
- Cost must be treated as a release/infrastructure gate alongside correctness, latency, freshness, reliability and NO ORDERS.
- New or materially changed services require a measured RAM/CPU/network baseline and explicit classification as permanent production vs temporary research/certification.
- Internal service-to-service data paths should use private networking; unexpected public internal egress is a regression.
- Temporary/research services require a defined purpose, evidence/finish condition, and retirement review; they must not silently become permanent.
- Track project run-rate and investigate material unexplained increases before expanding infrastructure.
- Cost reductions may never silently weaken signals, data freshness, timing, validation, reliability or bot integrity.
- If performance/integrity requires spending above budget, stop at the decision boundary, quantify the expected cost and benefit, and discuss with the user before proceeding.
