# Protected EARLY clean forward observer reset

Observer service: `early-forward-scorecard-v1` (`efb56ace-8c0e-4672-a772-6dd3b8633078`).
Branch: `scalp-move-shadow-v1-20260912`.
Frozen study: `13c8988fed8c97479203910f5620df64826246f3`.

## Scope

New isolated runtime `BTC15_EARLY_FORWARD_SCORECARD_V2.py` and its tests, with
the existing service's native start command updated. The old V1 file is also imported by the separate
EARLY/FINAL handoff service, so it is intentionally unchanged. No shared adapter,
production file, rule, threshold, FINAL, SCALP, BRTI, or Kalshi plumbing is edited.
The existing observer service alone switches entry point; no new service.

## Source and semantics

The only signal source is
`https://btc-15min-bot-production.up.railway.app/dashboard_state.json`.
Use the existing protected adapter's `early_state_from_main` and
`canonical_seconds_left` functions. The current nested `early.ready`, side, ask,
fair, edge and producer `FROZEN_TIER1` map directly. EARLY is never recalculated.

Frozen producer rule remains ASK <=45c, fair >=75%, edge >=8pp, 2–10 minutes
remaining, absolute exact target gap >=$25, first qualifying production state.
The observer imposes no additional ASK/fair/edge/target qualification.

Every process starts with empty state and a distinct run UUID. No previous state,
bootstrap variable, historical call, or provisional 03:00 UTC boundary is loaded.
The startup contract is excluded permanently. The first continuously observed
post-start rollover arms the run. `/plumbing` records its contract, exact UTC
contract start, first observed UTC time, source timestamp, commit and deployment.
The rounded quarter-hour close is checked against both the source timer and the
contract's Eastern-time ticker before deriving its exact start. Raw source times
are retained. A missed rollover waits for the next fully observed rollover.
Fresh opening data for the new contract is evaluated independently of stale
data in the preceding excluded startup contract; a prior gap cannot disqualify
an otherwise fully observed new opening. Skipped contracts remain excluded.

Capture the first protected call exactly once per eligible contract, even when
outside the study slice. Score it only if its source timer is inclusively
420–600 seconds. Later side/price/ready changes cannot replace that first call.

Poll every 5 seconds. Maximum source age, rollover arrival lag and observation
gap are 30 seconds; these are collection-quality guards, not signal thresholds.
Late/skipped rollovers and gaps before the first call or completion of the slice
are explicitly excluded, without backfill. A gap after a frozen call never
removes that call or its outcome. Coverage reports both started eligible
contracts and contracts with completed slice observation. Exclusions have an
auditable reason. No-call observed contracts remain in the denominator.

## Official settlement and frozen gates

GET the exact ticker from the official Kalshi market endpoint, then historical
market endpoint if needed. Require matching ticker, finalized/settled status,
literal yes/no result and no provisional flag. YES maps to UP; NO maps to DOWN.
Missing, interim, malformed or unreachable results stay pending and retry.
Store the official endpoint, retrieval time, final status/result and payload
hash with the score. BTC price, FINAL and model output never determine settlement.
An excluded startup-contract probe verifies this connection without entering
the forward sample or reporting that contract's result.

Primary success: first EARLY side equals official final settlement side.
ASK, 25–35c rate, <=50c rate, minutes left, UP/DOWN balance and coverage are
descriptive. No excursion determines success.

Frozen gates use the first calls in chronological call order, independent of
settlement response order. At 10: <=8 correct fails; 9 or 10 continues unchanged
to 15. At 15: >=14 is provisional support, <=13 fails. A failure at 10 remains
a failure even if later calls recover. There is no tuning or auto-promotion.

## Operation and reproducibility

`/plumbing` and `/health` contain no strategy-performance results. `/state`
contains the current run's records, coverage/exclusion audit, settlement evidence
and checkpoints. Structured stdout logs preserve run/start, rollover, first-call,
settlement and checkpoint events. The service currently has no persistent volume:
a process restart intentionally creates a NEW run and new rollover boundary,
never silently joins samples. Archive `/state` or run-tagged Railway events when
reviewing the study; do not merge different run UUIDs.

Only GET requests to the fixed dashboard URL or exact official ticker endpoints
are allowed. No credentials, trading clients or order endpoints are used. HTTP
POST/PUT/PATCH/DELETE on the observer return 405. SIGNAL ONLY / NO ORDERS.

Run tests:
`python -m unittest -q test_BTC15_EARLY_FORWARD_SCORECARD_V2.py test_btc15_main_protected_state_adapter_v1.py test_btc15_protected_module_adapter_v1.py test_btc15_signal_integration_v1.py`

Official response schema references:
- https://docs.kalshi.com/api-reference/market/get-market
- https://docs.kalshi.com/api-reference/historical/get-historical-market
