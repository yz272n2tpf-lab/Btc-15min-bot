# BTC15 Kalshi Exact-Ticker Rollover Discovery Decision — 2026-09-15

**Research / shadow only · read only · signal only · manual execution · no orders**

## Frozen Probe V2 decision

**REVIEW_SAMPLE_READY_REJECTED**

The Probe V2 gate was frozen before the four eligible rollovers were complete. The old 18:45 UTC Probe V1 rollover is excluded because V1 incorrectly treated placeholder YES 0/0 and NO 1/1 books as usable. Probe V2 required every bid/ask strictly inside (0,1), bid <= ask on both YES and NO, exact ticker identity, exact expected open/close clock, and active market status.

### Predeclared gate

- at least 4 new Probe V2 rollovers;
- at least 3 direct-vs-production-style broad comparisons;
- exact ticker identity correct on all reviewed direct evidence;
- expected 15-minute open/close clock correct on all reviewed direct evidence;
- exact ACTIVE + USABLE-QUOTED by +5 seconds on at least 75% of reviewed rollovers;
- median lead versus broad `status=open` ACTIVE discovery at least 10 seconds.

### Four-rollover evidence

| Boundary UTC | Exact ACTIVE+usable | Broad ACTIVE | Direct lead |
|---|---:|---:|---:|
| 19:00 | +4.533s | +29.214s | 24.681s |
| 19:15 | +11.150s | +29.671s | 18.521s |
| 19:30 | +5.255s | +30.092s | 24.837s |
| 19:45 | +11.641s | +30.155s | 18.514s |

Identity integrity: **4/4**.
Clock integrity: **4/4**.
Direct usable by +5s: **1/4 = 25%**.
Median direct lead versus broad discovery: **21.601s**.

## Decision

The direct exact-ticker path is consistently and materially earlier than the production-style broad listing, but it failed the frozen +5-second reliability requirement. Therefore this Probe V2 gate is **REJECTED** and does not authorize deployment of the already-built exact-ticker fallback shadow server.

No production change is authorized. Do not relax the +5-second criterion and relabel these same four rollovers as validation.

## Research interpretation

The rejected gate still provides useful hypothesis-generation evidence:

- deterministic ticker identity was correct on every reviewed rollover;
- exact open/close clock was correct on every reviewed rollover;
- the exact market became active almost immediately;
- placeholder 0c/100c books persisted variably before a real usable book appeared;
- once usable, direct exact-ticker quotes preceded broad ACTIVE discovery by roughly 18.5–24.8 seconds in every reviewed rollover.

A materially different operational hypothesis may be tested only on a NEW future-only sample with a new cutoff. Any such test must be frozen before those future outcomes are observed and must authorize at most a separate shadow validation, never production promotion.

## Safety

- Production unchanged.
- V5/V6/V12 unchanged.
- No signal thresholds changed.
- No exact-ticker fallback deployed from this rejected gate.
- No orders or automated execution.
