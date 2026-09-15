# BTC15 Kalshi Rollover Operational Replication Freeze — 2026-09-15

**Research / shadow only · read only · signal only · manual execution · no orders**

## Why this is a new test

Probe V2's predeclared +5-second gate was rejected after four eligible rollovers. Those four rows are development/hypothesis-generation evidence only for the next question and must never be counted toward this replication.

The rejected sample nevertheless showed exact deterministic contract discovery roughly 18.5–24.8 seconds before the production-style broad `status=open` listing. The new operational question is therefore different:

> Can exact deterministic KXBTC15M discovery provide a correctly identified, correctly timed, active, genuinely usable four-sided book within the first 15 seconds of a contract often enough, and consistently enough ahead of broad discovery, to justify a separate shadow fallback validation?

## Frozen future-only cutoff

**2026-09-15T20:00:00Z**

No boundary before this cutoff is eligible.

## Frozen replication gate

Require all of the following:

- at least **8** fresh rollover boundaries at/after the cutoff;
- at least **6** valid direct-vs-broad ACTIVE comparisons;
- exact ticker identity correct for **100%** of reviewed direct evidence;
- exact expected 15-minute open/close clock correct for **100%** of reviewed direct evidence;
- exact market ACTIVE + strict usable four-sided book by **+15.0 seconds** on at least **7/8 = 87.5%** of eligible rollovers;
- exact ACTIVE+usable must precede broad ACTIVE discovery on **100%** of valid comparison rows;
- median direct lead versus broad ACTIVE discovery at least **15.0 seconds**;
- placeholder 0c/100c books never count as usable;
- bid must be <= ask on both YES and NO.

## Decision semantics

- Before sample size: `COLLECTING_FRESH_OPERATIONAL_REPLICATION`.
- Gate met: `READY_FOR_EXACT_TICKER_SHADOW_VALIDATION`.
- Sample ready but any gate fails: `OPERATIONAL_REPLICATION_REJECTED`.

A PASS authorizes only deployment of the already-built isolated exact-ticker fallback **shadow evidence server**. It does not authorize production switching, signal qualification changes, or orders.

## Research integrity

- Do not add the rejected 19:00/19:15/19:30/19:45 Probe V2 rows to this sample.
- Do not change the +15s/87.5%/15s-lead gate after seeing replication outcomes.
- Do not sweep alternative timing thresholds on the same replication sample.
- If rejected, either freeze this path or formulate a materially different hypothesis with another future cutoff.

## Safety

- Production unchanged.
- V5/V6/V12 unchanged.
- Protected EARLY/FINAL unchanged.
- Scalp qualification/lifecycle unchanged.
- No price filter added.
- No orders or automated execution.
