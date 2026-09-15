# BTC15 CURRENT AUTHORITY MAP — 2026-09-15

Status: research-branch continuity reference. This file does not authorize production changes.

## Production authority
- Service: `Btc-15min-bot`
- Service ID: `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`
- Branch: `main`
- Latest verified deployment: `49dfb1af-b29e-4c9a-a68d-e75c8632aef2` SUCCESS.
- Production is intentionally untouched by current research.
- Signal only / manual execution / no orders.

## Frozen scalp lifecycle authority
- Service: `scalp-move-shadow-v1`
- Service ID: `8b40a28c-1beb-4020-bdc2-e7e236fe3501`
- Frozen behavior: full-contract serial opportunities, ENDED_UNARMED reset-only, armed/no-exit blocking, +5c protection arm, 4c giveback EXIT, no prearm stop, no hidden price filter, price telemetry/guidance only.
- This architecture remains frozen while forward diagnostics collect.

## Display bridge authority
- Service: `scalp-display-bridge-v6`
- Service ID: `90046a79-3f57-493f-b473-18d0031e8f0d`
- Display enrichment only. Does not qualify or suppress signals.

## Stable dashboard baseline
- V12 remains the current accepted shadow display baseline.
- Existing service ID: `87801206-d705-43d6-8aa2-bfb1b11c1ff6`.
- Verified deployment: `12a26d34-ffe5-46b5-a29e-5f8a43a12a17` SUCCESS.
- Expensive qualified scalp is shown as tracking/no manual position rather than misleading PROTECT/EXIT instructions.

## V13 presentation candidate
- Service: `combined-dashboard-shadow-v13`
- Service ID: `b210d5f0-0616-4e39-9812-ce7b41b73d67`
- Verified deployment: `0df31206-238e-46aa-b0f8-ef79773889b7` SUCCESS.
- Presentation-only. Must not replace V12 or production without user visual acceptance.

## FINAL forward authority — V4
- Service: `final-forward-scorecard-v1`
- Service ID: `fbe79688-25ed-4329-b0d6-c9b669559b17`.
- Authoritative deployment: `48b86488-3688-40d3-82b4-ad5fe028a61f` SUCCESS.
- Runtime: `BTC15_FINAL_FORWARD_SCORECARD_V4.py`.
- Fresh cutoff: `2026-09-15T20:00:00Z`.
- Coverage universe: first seen with >=480 seconds left, before protected FINAL eligibility can open.
- Frozen review gate: >=30 eligibility-complete contracts and >=12 officially settled protected FINAL locks.
- Watchdog-supervised; protected FINAL thresholds unchanged; no orders.
- Latest checkpoint at this map update: 3 eligibility-complete contracts, 2 locks, 2 settled, 2/2 correct; watchdog restarts=0.
- Historical protected FINAL 132/133 = 99.25% remains historical reference only and must not substitute for the fresh V4 sample.

## EARLY forward authority — V1
- Service: `early-forward-scorecard-v1`.
- Service ID: `efb56ace-8c0e-4672-a772-6dd3b8633078`.
- Authoritative deployment: `32b3b7f1-ae00-4e45-8609-84eb3a2409f8` SUCCESS.
- Runtime: `BTC15_EARLY_FORWARD_SCORECARD_V1.py`.
- Startup contract excluded; collection arms on first post-start rollover.
- Coverage universe: first seen with >=600 seconds left, before protected EARLY's 10-minute window opens.
- Protected EARLY remains producer authority; scorecard does not requalify it.
- Frozen producer source facts: ask <=45c, fair >=75%, edge >=8pp, 2–10m left, absolute target gap >=$25.
- Frozen review gate: >=30 eligibility-complete contracts and >=12 officially settled protected EARLY calls.
- Settlement same-side rate is secondary directional context, never FINAL accuracy.
- Railway deploy-log visibility is incomplete for this service, but build healthcheck succeeded and runtime/service activity is present; the health watch fails closed if its heartbeat does not advance.

## Protected EARLY → FINAL workflow authority — handoff V1
- Service: `early-final-handoff-v1`.
- Service ID: `174bd89d-264b-4882-8d5a-b8dbacf97181`.
- Authoritative deployment: `43e32eee-afea-4986-a944-803a53945852` SUCCESS.
- Runtime: `BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`.
- Code commit: `8c6ebedb14eea11072c0acc1404aa0b68fabb7be`.
- Test commit: `cb05a536a1164132d4a4b872bb90b7bcd1a804d3`; 10 tests PASS.
- Frozen before live collection in `BTC15_EARLY_FINAL_HANDOFF_FORWARD_FREEZE_20260915.md` commit `8c5212cb3587be9d61a9bcbcbc486a07e491e887`.
- Startup contract excluded; authoritative sample begins after runtime START and first post-start rollover.
- Coverage universe: first seen with >=600 seconds left.
- Frozen review gate: >=30 eligibility-complete contracts, >=10 real protected EARLY+FINAL handoffs, >=12 officially settled protected FINAL locks.
- Measures EARLY/FINAL/union/dual coverage, handoff time, confirm/flip, entry-to-lock price progression, and official FINAL accuracy without changing either signal.
- Latest runtime checkpoint: three consecutive healthy heartbeats, restarts=0, clean zero live sample while waiting for first post-start rollover.
- The automatic initial `main` bootstrap deployment was removed and is non-authoritative.

## Kalshi rollover discovery authority — Probe V3
- Runs on service `combined-forward-scorecard-v1`.
- Service ID: `e9399baa-25a8-4801-a374-ae6c5401060d`.
- Authoritative deployment: `4b23c967-5cae-49f0-b2de-7ee2aa74a8e1` SUCCESS.
- Probe V3 cutoff: `2026-09-15T20:00:00Z`.
- Frozen gate: >=8 new rollovers; >=6 valid direct-vs-broad comparisons; 100% ticker identity; 100% expected clock integrity; exact ACTIVE + strict four-sided usable book by +15s on >=7/8; direct usable before broad ACTIVE on every valid comparison; median lead >=15s.
- Latest checkpoint at this map update: 3/8 rollovers, 3/3 by +15s, identity/clock clean, direct before broad on all comparisons, median lead 10.225s; still collecting / not passed.
- PASS would authorize only isolated exact-ticker shadow validation, never automatic production change.

## Combined / UNION evidence
- Older combined V1/V2 samples requiring near-second-zero discovery are diagnostic-only for final UNION claims because production-style discovery can lag rollover.
- Do not quote those older combined numbers as authoritative overall coverage.
- The new handoff V1 provides an honest common EARLY/FINAL observability universe, but it is still collecting and does not include SCALP union authority.

## Closed / rejected research
- Missing-BTC30 recovery: rejected / closed after serial baseline and winner-retention failure; V5 qualification unchanged.
- BTC30 >=20 tightening: rejected / closed.
- Normalized momentum floors: rejected / closed.
- Strict 15-second parity rule: rejected / closed.
- Failed-prearm stop/release: rejected / closed; no prearm stop added.
- Probe V2: rejected / closed under its predeclared <=5s gate.
- Do not retune these ideas on the same samples.

## Evidence registry
- `BTC15_AUTHORITATIVE_EVIDENCE_REGISTRY_20260915.md` is the authoritative classification of active, historical, diagnostic, and rejected evidence.
- Latest registry update commit: `183524c31111922b68675e27a8c734b58fd988f4`.

## Non-negotiable system rules
- Signal only; manual execution only; no orders.
- EARLY, SCALP and FINAL remain separate paths.
- Preferred user entry <=50c, ideal 25–35c; price is guidance/telemetry unless separately validated as a trigger rule.
- FINAL target remains 93–95%+ fresh accuracy; do not claim it from a tiny fresh sample.
- No numeric Flip Risk percentage until independently calibrated and validated.
- No automatic production promotion from research or presentation candidates.
