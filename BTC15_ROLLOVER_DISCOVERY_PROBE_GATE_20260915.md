# BTC15 Rollover Discovery Probe Gate — 2026-09-15

## Status

PREDECLARED / FROZEN BEFORE LIVE PROBE OUTCOMES

READ ONLY / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION

## Problem being measured

Production has repeatedly remained on the ending KXBTC15M contract for roughly 18–34 seconds after a 15-minute boundary while logging `NO ACTIVE KXBTC15M CONTRACT — retrying...`.

Current V4.13 discovery requests `/trade-api/v2/markets` with:

- `status=open`
- `series_ticker=KXBTC15M`
- `limit=1000`

and then selects a returned market whose `open_time <= now < close_time`.

The probe compares that production-style broad search with a direct read-only GET of the deterministically scheduled next ticker.

## Frozen sample requirement

Do not decide from one rollover.

Minimum review sample:

- at least **4 separate 15-minute rollovers** with probe samples spanning the boundary;
- at least **3 rollovers** must contain a valid direct exact-ticker response and a valid broad-search response;
- target ticker open/close times must match the expected boundary and boundary+15m on every direct-ticker sample used for review;
- no order endpoint, credential mutation, trading action, or signal qualification may be involved.

## Candidate fallback support criteria

A direct scheduled-ticker discovery fallback may advance to a separate shadow-integration test only if all are true:

1. Exact-ticker identity is correct on 100% of reviewed rollovers.
2. Direct ticker is active with valid four-sided bid/ask data by **+5 seconds** on at least 75% of reviewed rollovers.
3. Direct-ticker availability/quote readiness leads the production-style broad `status=open` discovery by at least **10 seconds median** across reviewed rollovers.
4. There is no rollover where the direct ticker points to the wrong open/close window.
5. No reviewed direct response carries stale prior-contract timing while being classified active.
6. The result is repeatable across multiple rollovers, not driven by one outlier.

If exact-ticker market data itself is unavailable or unquoted until approximately the same time as broad discovery, reject this fallback hypothesis and investigate upstream Kalshi publication/listing timing instead.

## If criteria pass

Only then build a separate shadow discovery candidate. It must:

- predict the scheduled next KXBTC15M ticker from the canonical 15-minute boundary;
- directly fetch that ticker read-only;
- validate exact `open_time` and `close_time` against the expected window;
- require valid quotes before exposing actionable EARLY/SCALP data;
- preserve fixed Kalshi start-price alignment;
- preserve canonical timer ownership;
- fail closed on mismatch/staleness;
- preserve EARLY, FINAL, serial scalp lifecycle, +5c arm / 4c giveback, and all existing safety rules;
- remain signal-only / manual execution / no orders;
- run in shadow before any production integration.

## Explicit non-goals

- Do not alter FINAL thresholds.
- Do not alter EARLY thresholds.
- Do not alter scalp qualification or BTC30 rules.
- Do not use price as a hidden trigger filter.
- Do not add a stop-loss.
- Do not invent numeric flip risk.
- Do not modify production from probe results automatically.
