# EARLY observer freshness / rollover V3: BLOCKED, NOT DEPLOYED

## Decision

The requested observer-only repair cannot restore the inspected missing openings
while preserving the existing 30-second opening standard. The production source
really stops publishing valid frames around these boundaries. Per the explicit
stop instruction, no observer runtime, production, strategy, collector, service
configuration, or deployment was changed. This job is **not qualified as a
successful repair**. A passing synthetic test suite does not qualify live data.

## Proven causal chain

Inspected observer: `BTC15_EARLY_FORWARD_SCORECARD_V2`, deployed commit
`672f83a07a0be2cec3ff0b13cfab25f514952948`, deployment
`764934d0-a646-4363-942d-bba62e94a1b3`, service
`efb56ace-8c0e-4672-a772-6dd3b8633078` (`early-forward-scorecard-v1`).

Inspected production: commit `7339b87624e35314b9d2b94e8a4feefef02715dd`, deployment
`e9ae8eee-b1e4-412e-8fb3-48fd0cd0f4c4`.

1. The production main loop in
   `bot_two_output_build_v4_13_profit_protection_shadow.py` calls
   `get_active_market()`. If no active market is returned, it sleeps and continues
   without publishing the synchronized source row.
2. Its existing quote-provenance gate likewise sleeps and continues when
   `consume_ws_quotes(...)` returns no verified quote. That occurs **before** the
   unified source write. At near-expiry empty-book periods, logs explicitly show
   `KALSHI QUOTE EMPTY SIDE` and repeated `KALSHI QUOTE WAIT`.
3. The deployed dashboard state builder reads those synchronized CSV rows. HTTP
   200 and a newly generated response do not make the underlying source new. The
   source timestamp stays old until the producer writes another usable frame.
4. `health.source_fresh` in that unchanged producer requires paired quotes,
   source age from zero through 15 seconds, and an open contract. The observer
   honors that flag and separately enforces source age <=30 seconds and future
   skew <=2 seconds. Thus the log first reports `production source not fresh`
   and later the combined `stale/future production source` error as age rises.
5. New valid frames in the examples below carry timestamps already 34–53 seconds
   after opening. Their observer receipt delay is only 0.14–1.79 seconds. They
   correctly miss the existing 30-second source-opening grace.

The logs do not establish why the active-market lookup has no usable result
during every opening delay (for example, API publication timing versus another
discovery issue). That requires a separately scoped, read-only source-path
investigation. They do establish that the observer did not receive a healthy
opening stream during the inspected failures. No clock-skew storm was proven;
the combined error label alone does not distinguish stale from future data.

## Runtime examples (all 2026-09-21 UTC, before any repair)

| Contract | Opening | First accepted source | Observer receipt | Source elapsed | Receipt minus source | Decision |
|---|---|---|---|---:|---:|---|
| KXBTC15M-26SEP210730-30 | 11:15:00 | 11:15:53.295141 | 11:15:53.438859 | 53.295141 s | 0.143718 s | Excluded |
| KXBTC15M-26SEP210745-45 | 11:30:00 | 11:30:48.936398 | 11:30:49.949544 | 48.936398 s | 1.013146 s | Excluded |
| KXBTC15M-26SEP210800-00 | 11:45:00 | 11:45:34.514139 | 11:45:36.302145 | 34.514139 s | 1.788006 s | Excluded |

At 11:44:14, production parity was PASS. At 11:44:19 it entered QUOTE WAIT;
11:44:20 logged an empty `no` side. At 11:44:29 and 11:44:44, parity reported WAIT
with source ages 15.9 and 31.0 seconds. At 11:45:04, BRTI finalized with 60/60
readings, while the main loop reported NO ACTIVE CONTRACT at 11:45:04, :09, :14,
:19 and :24. At :29 it reported QUOTE WAIT and connected the new contract's
websocket. The new dashboard source begins at :34.514. Parity recovers to PASS
at :45. This explains why a healthy BRTI closeout or later parity PASS does not
prove that an EARLY opening frame existed.

The 11:15 and 11:30 windows independently show the same quote-wait/empty-side,
stale parity and delayed new-contract websocket sequence. New quote connections
are logged at 11:15:43.533 and 11:30:44.128 respectively.

## Observer mechanics audited

- `poll_loop` samples `utcnow()` **after** `fetch_json()` returns. A request-start
  versus response timestamp bug is not present in the deployed loop.
- Nominal sleep is five seconds after each request, with a five-second HTTP
  timeout. Observed warning cadence is approximately five seconds. Request time
  can extend poll intervals; no timing-limit change was made.
- Responses request `Cache-Control: no-cache`; production sends `no-store`.
  Repeated underlying frames are distinct from HTTP transport failure.
- Fresh duplicate/reordered source timestamps return before observation/call
  creation. A repeated frame eventually becoming truly stale still fails closed.
- Commit `672f83a` already removed the prior-gap dependency from new rollover
  qualification. Fresh consecutive openings can qualify after a stale prior
  contract. Skips and late openings remain excluded.
- Opening grace remains 30 seconds. Increasing it to absorb the observed delays
  would admit contracts whose beginnings were not captured under the current
  definition. No missed contract was reconstructed from history or chart points.
- Secondary diagnostic limitation: current `/plumbing` labels time since last
  accepted observation as `source_age_sec`, rather than time since source. This
  field is not the `read_frame` freshness gate and does not cause these boundary
  exclusions. It was left unchanged under the stop decision.

## Tests and old-versus-requested behavior

Baseline: **59 passed, 0 failed**. Added diagnostic regressions: **14 passed,
0 failed**. Combined: **73 passed, 0 failed**.

```sh
python -B -m unittest -q test_BTC15_EARLY_FORWARD_SCORECARD_V2.py test_BTC15_EARLY_OBSERVER_V3_SOURCE_BLOCKER.py test_btc15_main_protected_state_adapter_v1.py test_btc15_protected_module_adapter_v1.py test_btc15_signal_integration_v1.py
```

| Required check | Result |
|---|---|
| Continuous rollover exactly once | PASS |
| Rejected stale prior frame followed by fresh new opening | PASS |
| Truly stale new source rejected | PASS |
| Material future source rejected | PASS |
| Bounded network jitter / clock skew | PASS without increasing limits |
| Duplicate timestamps / observations / calls | PASS |
| Skipped contract excluded | PASS |
| Late first observation excluded | PASS, including three actual source offsets |
| Restart / previous contract backfill | PASS |
| First protected EARLY call immutable, once only | PASS |
| Exact-contract official settlement attachment | PASS |
| Protected threshold/adapter integrity | PASS; no production diff, adapter byte guards |
| Production behavior unchanged | PASS; only diagnostic test and this report added |
| SIGNAL ONLY / NO ORDERS | PASS; GET allowlist, HTTP write rejection, safety envelope |

The old-failure reproduction deliberately remains **excluded**, even with zero
HTTP delay, for the three late source timestamps. Healthy synthetic openings
still pass; no repaired live behavior is claimed. An observer-only patch cannot
turn these missing openings into defensible full observations.

## Protected code and deployment integrity

Added files only:

- `test_BTC15_EARLY_OBSERVER_V3_SOURCE_BLOCKER.py`
- `BTC15_EARLY_OBSERVER_V3_BLOCKED_20260921.md`

Every existing tracked file is byte-identical to the observer baseline. No
production branch was modified. The decoded deployed dashboard state source has
SHA-256 `66cdbaa21daa848f261e87e1528dce5a0cadd700fe3be22567f664f968f6d1b7`.
Its frozen constants remain ASK <=0.45, fair >=0.75, edge >=0.08,
2–10 minutes remaining, absolute target gap >=25. The observer still delegates
to `early_state_from_main` and does not reconstruct the qualification rule.

Production, protected EARLY, FINAL, SCALP, BRTI transport, Kalshi quote plumbing,
Directional Position Manager, dashboard semantics and settlement definition are
unchanged. No orders or order-capable route was added. No Railway service was
created, reconfigured, restarted or deployed.

The running clean SCALP service remains on deployment
`93f2b49c-9078-4653-bd27-567d093df57a`, commit
`f59276fd4733bbc374be53aaa4bb8063ed0f81ab`.

## Sample / handoff status

Diagnostic branch: `repair/early-observer-freshness-rollover-v3-20260921`.
The commit containing this report is a **diagnostic-only** commit.

- New Railway deployment ID: **none**.
- Fresh clean process start: **none**.
- First eligible fresh clean contract: **none**.
- Post-fix rollover examples: **none; not deployed**.
- Existing contaminated process remains `c34a3b19-b703-428e-a2e6-56f2d23741d0`,
  started `2026-09-21T03:33:20.526369Z`. It was not relabeled as clean.
- A read-only snapshot of the old state and matching runtime evidence was
  archived for diagnosis. It is not a final end-of-run archive: the old process
  was left running because deployment gates did not pass.
- No old sample was loaded into a new process, scored for this work, used for
  threshold selection, or used to evaluate calls/no-calls. No strategy accuracy
  or coverage-performance conclusion was computed.
- Existing state shows an exact-contract official-settlement startup probe
  verified at `2026-09-21T03:46:30.685808Z`. That is pre-fix plumbing evidence,
  not post-deployment qualification or strategy validation.

Safest next work: a separately authorized **read-only audit** of active-contract
discovery and quote readiness across opening, identifying whether any already
available protected source can supply valid opening frames. Keep every existing
gate in place. Any necessary producer/quote-plumbing change requires new scope;
no such change is included here.
