# BTC15 Rollover Probe V1 Diagnostic — 2026-09-15 18:45 UTC

## Status

**DIAGNOSTIC ONLY — EXCLUDED FROM THE FROZEN V2 FOUR-ROLLOVER DECISION SAMPLE**

Reason: V1 initially classified Kalshi placeholder books (`YES 0/0`, `NO 1/1`) as valid four-sided quotes because its numeric validity check allowed 0 and 1. This was discovered on the first live boundary before any multi-rollover decision was made.

## Observed 18:45 UTC rollover

Target exact ticker: `KXBTC15M-26SEP151500-00`

- Exact ticker already returned HTTP 200 before rollover.
- Returned ticker identity matched the requested ticker.
- Exact open/close clock matched the expected 18:45–19:00 UTC window.
- Exact status changed to active by approximately **+0.3s**.
- Placeholder book remained `YES 0/0`, `NO 1/1` through approximately +8.6s.
- First observed non-placeholder four-sided book was approximately **+10.7s**: `YES 43/44c`, `NO 56/57c`.
- Production-style broad `status=open` + `series_ticker=KXBTC15M` search first included the correct active ticker at approximately **+14.8s**.
- Approximate non-placeholder exact-vs-broad lead on this single diagnostic rollover: **~4.1s**.

## Probe V2 correction

`BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2.py` keeps V1 identity/clock/active timing logic but changes quote usability to require:

- all four YES/NO bid/ask prices strictly inside `(0,1)`;
- YES bid <= YES ask;
- NO bid <= NO ask.

Therefore 0c/100c placeholder books cannot satisfy the V2 `exact_active_quoted` measurement.

## Research integrity

- This 18:45 boundary does not count toward the frozen V2 gate.
- The predeclared minimum remains four new V2 rollovers.
- Thresholds are unchanged: exact ACTIVE+USABLE-QUOTED by +5s on >=75% and median lead >=10s, with exact ticker identity and clock integrity preserved.
- A pass can authorize only a separate shadow fallback test.
- No production change, no signal-threshold change, no orders.
