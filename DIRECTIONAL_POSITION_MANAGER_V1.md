# Directional Position Manager V1 — shadow delivery

Pure, offline, signal-only control layer. Nothing imports it from production and
no service or collector is connected to it. No deployment is part of this build.

Branch: `directional-position-manager-v1-shadow-20260921`

Base: `main` at `7339b87624e35314b9d2b94e8a4feefef02715dd`.

## Validation status

- **36 synthetic tests passed; 0 failed.** All 11 requested cases are covered.
- No historical market-performance validation was run. No clean EARLY or SCALP
  forward-validation samples, scores, logs, or state endpoints were inspected.
- Protect/exit cents: **RESEARCH / UNVALIDATED**. Both zones are `null`, including
  with complete inputs. There is no fabricated numeric formula or default zone.
- Confirmation-to-PROTECT management semantics are research-only. Losing a
  previously fresh protected FINAL confirmation, or a current opposing FINAL
  view, latches PROTECT. No new confidence threshold is introduced.
- EXIT requires a supplied severe `DangerAssessment` matched to a caller-reviewed
  `DangerRule`. **No historically validated danger rules ship enabled.** The
  example/test rule has scope `SYNTHETIC_ONLY`; it proves control flow only.
- Source timestamp freshness (15 seconds) comes from the existing dashboard.
  The two-second structural clock tolerance comes from the existing observer.
  Neither is a newly tuned signal threshold.

## Files added

| File | Purpose |
|---|---|
| `BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py` | Pure adapter, immutable state, reducer, atomic view, level-calculation API |
| `test_directional_position_manager_v1.py` | Offline synthetic control and safety tests |
| `directional_shadow_examples_v1.py` | Fabricated fixture builder and BUY/HOLD/PROTECT/EXIT demonstration |
| `directional_shadow_examples_v1.json` | Reproducible example output |
| `DIRECTIONAL_POSITION_MANAGER_V1.md` | Interface, behavior, validation limits, and delivery notes |

Existing files changed: **none**. In particular, no production source, deployment
configuration, SCALP module, BRTI or Kalshi implementation, provenance code,
protected qualification rule, or collector was edited.

## State machine

The normal path is `NO_POSITION -> BUY -> HOLD -> PROTECT -> EXIT`.
`PROTECT` renders as **PROTECT PROFITS**. One action is emitted in one atomic
view alongside FINAL's safety light; FINAL never owns cents boxes.

| Current state | Condition | Next state / behavior |
|---|---|---|
| NO_POSITION | Protected EARLY ready, fresh valid exact-side ASK/evidence, FINAL available and not opposing | BUY; capture hypothetical ASK and emit once |
| NO_POSITION | EARLY PASS, even if FINAL is highly confident | NO_POSITION; FINAL remains visible |
| BUY | Next distinct valid observation, no danger | HOLD |
| BUY / HOLD | Current FINAL opposes, previously strong FINAL loses confirmation, or reviewed PROTECT assessment | PROTECT |
| BUY / HOLD / PROTECT | Exact-position, exact-frame reviewed severe EXIT assessment | EXIT; may skip intermediate states |
| PROTECT | Evidence improves again | Remain PROTECT; no automatic recovery design is validated |
| EXIT | Any further same-position observations | Remain EXIT; no re-entry or repeated EXIT event |
| Any | Missing/stale/invalid source or required evidence/prices | Preserve lifecycle, disable actionable display, withhold levels |
| Any | Expiry / accepted later contract | Clear position, price, entry, and warning; later contract can qualify independently |

Missing information never manufactures a severe-deterioration classification.
Replay/out-of-order frames produce no event and no actionable quote display.
The lifecycle may retain BUY/HOLD while data are unavailable, but `actionable`
is false; a future renderer must respect this flag and display the reason.
The chronological contract watermark prevents an old contract returning after
rollover. Small permitted timestamp precision differences are not rollovers.

## Exact protected inputs

Source inspection was limited to code: current main's embedded
`BTC15_DASHBOARD_STATE_V2.py` inside `BTC15_INSTALL_LIVE_DASHBOARD_V13.py`, its
render wrapper, and the existing
`btc15_main_protected_state_adapter_v1.py` at research commit
`672f83a07a0be2cec3ff0b13cfab25f514952948`. The new module does not import or
execute any of those producers, models, or observers.

| Source fields | Use |
|---|---|
| `early.source` | Require existing `FROZEN_TIER1` producer identity |
| `early.ready` | Consume exact protected qualification boolean; never recompute it |
| `early.side` | Position side at entry; current evidence side after entry |
| `early.ask` | Hypothetical entry ASK; must equal the contemporaneous side-specific market ASK |
| `early.fair`, `early.edge` | Original and contemporaneous confidence/evidence, without new thresholds |
| `final.source` | Require existing `FROZEN_V4_6_FINAL` identity |
| `final.ready`, `final.side`, `final.confidence` | Current protected qualification, direction, and probability |
| `final.recorded_final_call`, `final.recorded_side`, `final.recorded_confidence` | Preserve prior protected call in display and future level context; never use a past call to mask current danger |
| `final.conditions` | Preserve existing protected evidence for display and future level context; no model reconstruction |
| Entire `final` object | Independent copied `protected_view`, always in the output; rejected foreign-contract data are withheld |

No `early.status`, entry ceiling, or price threshold is reinterpreted as a
qualification model. A management veto leaves the incoming `early.ready` and
all protected FINAL fields unchanged.

| Shared source fields | Use |
|---|---|
| `contract` | Exact contract identity; checked against the supplied close |
| `source_timestamp_utc` | Observation time, entry time, freshness and replay boundary |
| `timer.close_utc`, `timer.seconds_left` | Validate the existing 15-minute alignment and compute display time remaining against the caller's UTC clock |
| `health.source_fresh`, `health.market_open` | Existing source-quality gates |
| `health.paired_quotes` | Require the existing paired snapshot before using prices |
| `health.brti_fresh` | Require existing BRTI freshness for strong FINAL confirmation and level inputs; never derive BRTI |
| `market.up_bid`, `market.up_ask`, `market.down_bid`, `market.down_ask` | Held-side bid/ask; input dollars become display cents by multiplication by 100 |
| `safety.read_only`, `safety.orders_enabled` | Require true/false respectively |

Quote basis is explicitly `EXISTING_PRODUCTION_PAIRED_SNAPSHOT`. The source
timestamp is not relabeled as an exchange quote timestamp. The manager neither
reconstructs nor claims to independently certify quote provenance. It does not
fetch, synthesize, or fall back to alternate market quotes.

## API and rendering contract

```python
state, view = update(state, protected_snapshot, now_utc=explicit_utc_datetime)
```

The caller retains the returned immutable `State` before consuming an event.
The `event` field is emitted once per transition, while `state` is the lifecycle.
BUY is a shadow observation at ASK, **not a manual fill acknowledgement**.
No automatic restart runner or durable store is included. A future harness must
persist/restore State and event deduplication before being used across restarts;
reinitializing `State()` mid-contract discards that caller-owned history.

Render `view.early` as the EARLY top section, and root `view.action` plus
`view.levels` exclusively in EARLY's bottom action section. Render
`view.final.protected_view` and `view.final.safety_light` as FINAL's independent
outcome and position-safety lane. `view.final.fresh` and `blocked_reason` must be
honored. A retained protected direction is not a new BUY instruction.

Safety lights are STRONG CONFIRMATION for fresh live qualified agreement,
CAUTION otherwise, with PROTECT WARNING and EXIT WARNING floors imposed by
latched action state. A recovered raw FINAL view remains visible, but the
position's warning stays latched with `light_latched_to_action=true`.

`level_context(position, frame, light)` returns the complete `LevelContext` for
a future offline calculator: contract/position/side, original timestamp and ASK,
current bid/ask, remaining seconds, original and current EARLY fair/edge with
their sides, current protected FINAL state/conditions and recorded call, action,
and safety light. Missing price/evidence/BRTI freshness returns `None`.
`calculate_levels(context)` currently always returns unavailable zones.
No current quote is disguised as a calculated protect/exit zone.

An optional `DangerAssessment` must match position ID, contract, side, exact
source timestamp, rule ID, validation reference and allowed action. EXIT also
requires `severe=True`. Rule scopes are restricted to `SYNTHETIC_ONLY` and
`HISTORICAL_DEVELOPMENT`; a clean-forward scope cannot authorize a transition.
Rule references are caller-reviewed metadata, not independently certified by
this no-I/O module. The empty default registry cannot produce a validated EXIT.

## Synthetic examples

These values are fabricated source observations. They are neither recommended
entries nor validated protect/exit levels. Full outputs are in the JSON file.

| EARLY action | Original ASK | Current bid / ask | FINAL safety light | Protect / exit cents |
|---|---:|---:|---|---|
| BUY UP | 32¢ | 30¢ / 32¢ | CAUTION | Unavailable — research |
| HOLD UP | 32¢ | 63¢ / 65¢ | STRONG CONFIRMATION | Unavailable — research |
| PROTECT PROFITS UP | 32¢ | 59¢ / 61¢ | PROTECT WARNING | Unavailable — research |
| EXIT UP | 32¢ | 45¢ / 47¢ | EXIT WARNING | Unavailable — research |

The EXIT row uses the explicitly synthetic severe-danger reference; it does
not assert a market-validated exit rule.

## Reproduce safely

From this isolated branch, run only these offline commands:

```bash
python -m unittest -v test_directional_position_manager_v1
python directional_shadow_examples_v1.py
```

Tests cover all requested behaviors plus UP/DOWN ASK identity, stale/unpaired/
crossed/non-finite prices, future/naive timestamps, contract/timer mismatch,
clock precision, expiry during outage, old-contract rejection, source replay,
recorded FINAL masking, unknown/misbound/nonsevere warning rejection, empty
registry behavior, clean-forward scope rejection, recovery latch, immutable
inputs, complete level context, and single-action rendering. AST checks enforce
an import allowlist and absence of file/network/execution/order capabilities in
the pure module. The tests and examples access no market data.

SIGNAL ONLY / NO ORDERS. No production deployment, service restart, collector
reset, live dashboard update, or forward-test interaction was performed.
