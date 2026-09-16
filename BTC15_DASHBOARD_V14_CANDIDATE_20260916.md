# BTC15 Dashboard V14 Candidate — 2026-09-16

**Presentation only · shadow only · signal only · manual execution · no orders**

## Status

`READY_FOR_HUMAN_VISUAL_REVIEW`

This status authorizes only iPhone/iPad visual acceptance. It does not authorize
production replacement, strategy changes, signal changes, or order automation.

## Railway

- Service: `combined-dashboard-shadow-v14`
- Service ID: `c1db8b80-f656-4295-ade8-812c129f6c72`
- Validated deployment: `95380505-ccb6-4489-bfec-299933596116`
- Research branch commit: `1c63eb3270509f01b976ec9709a5741f66796147`
- Domain: `combined-dashboard-shadow-v14-production.up.railway.app`
- Healthcheck: `/health` 200 on validated deployment.

## Automated gate

Validated deployment startup:

- `Ran 33 tests ... OK`
- `COMBINED DASHBOARD UI V14 SELFTEST PASS`
- V6 live preflight:
  - contract match = true
  - EARLY preserved = true
  - FINAL preserved = true
  - canonical clock = true
  - safety = true
  - serial safe = true
  - fresh/aligned = true
  - `NO ORDERS`

The gate includes inherited V13 behavior checks, V14 presentation-stability tests,
V14 static presentation-only audit, exact V13->V14 generated-HTML diff audit,
inherited V6/V7 server-envelope checks, V14 server-ownership checks, and V14
self-test.

## Exact allowed V13 -> V14 changes

V14 changes generated V13 HTML only by:

1. Replacing the exact BTC price color mutation
   `price.style.color=record&&!current?'var(--yellow)':'';`
   with a neutral inline color assignment so the numeric BTC value is not toggled
   yellow/white by ordinary stale/current updates.
2. Injecting the V14 presentation-stability CSS block.
3. Injecting the V14 marker.

The exact-diff test rejects any additional generated-page change.

## Stability behavior

- BTC numeric value: stable white presentation; no pulse animation/transition.
- Timer/price/probability changing numbers: tabular numerals and reserved inline widths.
- Existing older `#finalReason` fixed three-line box remains unchanged.
- `#finalActionSub`: bounded two-line region.
- `#earlyEntry` and `#earlyFlow`: reserved two-line regions.
- Existing V13 SCALP reason stability remains preserved.
- Exactly one visible main CONTRACT TIMER remains.
- No numeric Flip Risk is added.

## Frozen safety

V14 does not alter:

- protected EARLY qualification/state;
- protected FINAL qualification/LOCK state;
- V5 serial SCALP qualification or lifecycle;
- +5c arm / 4c giveback semantics;
- Kalshi price authority;
- canonical timer authority;
- V6 bridge safety envelope;
- price guidance vs qualification semantics;
- signal-only/manual-execution/no-orders behavior.

V12 and V13 services remain unchanged and available as fallbacks.

## Human review still required

Before V14 can replace any accepted dashboard candidate, visually confirm on both
an iPhone-size view and iPad-size view through at least one real contract rollover:

- BTC price no longer blinks/alternates color;
- FINAL card does not jump as reason/action text changes;
- EARLY card remains height-stable;
- timer/price digits do not visibly shift width;
- no duplicate timer/card appears;
- state wording remains readable and no protected signal is hidden.

Until that review passes, V14 remains a shadow candidate only.
