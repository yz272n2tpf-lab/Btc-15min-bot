# BTC15 CURRENT AUTHORITY MAP — 2026-09-15

Status: research-branch continuity reference. This file does not authorize production changes.

## Production authority
- Service: `Btc-15min-bot`
- Service ID: `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`
- Branch: `main`
- Latest verified deployment: `49dfb1af-b29e-4c9a-a68d-e75c8632aef2` SUCCESS
- Production is intentionally untouched by current research.
- Signal only / manual execution / no orders.

## Frozen scalp lifecycle authority
- Service: `scalp-move-shadow-v1`
- Service ID: `8b40a28c-1beb-4020-bdc2-e7e236fe3501`
- Frozen behavior: serial opportunities, ENDED_UNARMED reset-only, armed/no-exit blocking, +5c protection arm, 4c giveback EXIT, no stop-loss, price telemetry/guidance only.

## Display bridge authority
- Service: `scalp-display-bridge-v6`
- Service ID: `90046a79-3f57-493f-b473-18d0031e8f0d`
- Display enrichment only. Does not qualify or suppress signals.

## Stable dashboard baseline
- V12 behavior remains the stable accepted shadow baseline behind the existing dashboard service.
- V12 preserves completed scalp context and suppresses user-facing PROTECT instructions when entry was >50c / no manual position assumed.

## V13 presentation candidate
- Service: `combined-dashboard-shadow-v13`
- Service ID: `b210d5f0-0616-4e39-9812-ce7b41b73d67`
- URL: `https://combined-dashboard-shadow-v13-production.up.railway.app`
- Latest verified research deployment: `0df31206-238e-46aa-b0f8-ef79773889b7` SUCCESS
- 19 tests PASS.
- Static presentation audit PASS.
- V13 self-test PASS.
- Live preflight: contract match true, EARLY preserved true, FINAL preserved true, canonical clock true, timer delta 0.0s, safety pass true, no orders.
- Presentation-only. Must not replace V12 or production automatically.

## BTC30-missing fresh-forward authority
- Service: `scalp-coverage-audit-v1`
- Service ID: `f020787f-00fb-4a46-a36c-710f18bbf31e`
- Active validated runtime remains the successful fresh-forward observer deployment beginning from cutoff `2026-09-15T14:16:00Z`.
- Latest checked state around 18:36Z: baseline 29 opportunities / 17 contracts; recovered 11 / 11 contracts; recovered +10 = 90.9%; recovered <=50c count = 3; baseline opportunity retention = 75.9%; baseline winner retention = 77.8%.
- Not sample-ready because <=50c recovery requirement is not met; no promotion.

## FINAL forward authority
- Service: `final-forward-scorecard-v1`
- Service ID: `fbe79688-25ed-4329-b0d6-c9b669559b17`
- Runtime: `BTC15_FINAL_FORWARD_SCORECARD_V2.py`
- Historical reference: 132/133 correct = 99.25%; 53.2% FINAL-only coverage; avg 5.04m left; avg locked-side ask 92.99c; 0/133 <=50c.
- Latest checked live sample: 4 observed, 4 locks, 3 settled, 3/3 correct; avg lock time ~5.84m left; avg ask ~97.6c; 0 <=50c.
- FINAL accuracy is separate from entry quality.

## Combined common-universe scorecard authority
- Service: `combined-forward-scorecard-v1`
- Service ID: `e9399baa-25a8-4801-a374-ae6c5401060d`
- Authoritative runtime: `BTC15_COMBINED_FORWARD_SCORECARD_V2.py` only.
- V1 is diagnostic-only and must not be used for final common-universe conclusions.
- V2 rules: V5 main-authority-first rollover capture, scalp alignment fail-closed, only contracts first seen within <=5 seconds count as fully observed, serial scalp opportunities preserved individually, UNION counts each contract once.
- Latest verified V2 runtime passed 25 tests and started clean with eligible=0 after reset.
- Frozen decision gate remains >=30 eligible full contracts and >=25 settled contracts.

## Closed / rejected research
- BTC30 >=20 tightening: rejected.
- Normalized momentum floors: rejected.
- Strict 15-second parity rule: rejected.
- Do not retune those ideas on the same samples.

## Non-negotiable system rules
- Signal only; manual execution only; no orders.
- EARLY, SCALP and FINAL remain separate paths.
- Preferred user entry <=50c, ideal 25-35c, but price is guidance/telemetry unless separately validated as a trigger rule.
- FINAL target remains 93-95%+ accuracy; historical protected FINAL exceeds this but is generally too expensive to serve as the cheap-entry path.
- No numeric Flip Risk percentage until independently calibrated and validated.
- No automatic production promotion from research or presentation candidates.
