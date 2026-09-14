# BTC15 Scalp Profit-Protection Timing Audit — 2026-09-14

**Mode:** READ ONLY | SIGNAL ONLY | NO ORDERS  
**Purpose:** measure the already-frozen +5c arm / 4c giveback management on post-freeze forward data. No threshold selection or retuning.

## Forward timing sample

- Qualified primary scalp signals with PATH telemetry: **45**
- Protection armed after +5c: **37/45 = 82.2%**
- Frozen 4c-giveback EXIT observed: **22/45 = 48.9%**
- Median PATH sampling interval: **1.0 second**

The 1.0-second PATH interval is the measured event-tape cadence for this sample. Live dashboard alert latency still has to be measured end-to-end in the integrated smoke test.

## All qualified signals

- Median peak executable move: **+13.00c**
- Median peak-to-frozen-EXIT time among EXIT cases: **30.1s**
- Median +5c-arm-to-EXIT time: **75.0s**
- Median detected giveback at EXIT: **7.00c**
- Median overshoot beyond the nominal 4c giveback: **3.00c**
- Median executable gain remaining at EXIT: **+5.00c**
- Median retained share of peak among EXIT cases: **34.3%**

The exit overshoot is observational evidence about discrete executable price movement; it does not justify post-hoc retuning of the frozen 4c rule.

## Larger winners

### Peak >=10c

- n=26; 100% armed
- EXIT cases: 16
- Median peak: **+20.65c**
- Median peak-to-EXIT: **30.1s**
- Median detected giveback: **7.00c**
- Median EXIT gain: **+7.00c**
- Median peak retention: **56.3%**

### Peak >=15c

- n=20; 100% armed
- EXIT cases: 11
- Median peak: **+24.50c**
- Median peak-to-EXIT: **30.0s**
- Median arm-to-EXIT: **59.9s**
- Median detected giveback: **7.00c**
- Median EXIT gain: **+9.00c**
- Median peak retention: **58.8%**

### Peak >=20c

- n=13; 100% armed
- EXIT cases: 5
- Median peak: **+28.00c**
- Median peak-to-EXIT: **30.0s**
- Median arm-to-EXIT: **45.1s**
- Median detected giveback: **5.00c**
- Median overshoot beyond 4c: **1.00c**
- Median EXIT gain: **+12.00c**
- Median peak retention: **75.0%**

## Profit state at frozen EXIT

Across the 22 observed frozen EXIT cases:

- EXIT still positive: **68.2%**
- EXIT at least +5c: **50.0%**
- EXIT at least +10c: **18.2%**

## Integration decision

The frozen scalp entry and +5c/4c management thresholds remain unchanged.

For dashboard presentation, the +5c arm should become visibly obvious immediately so the user knows profit protection is active before a later giveback. The 4c giveback remains the frozen EXIT trigger. The integrated smoke test must measure the actual end-to-end delay from a PATH change to the visible dashboard warning and confirm that a large winner cannot silently round-trip without a protection warning.

## Guardrails

- No SCALP entry-price filter.
- No retuning from forward data.
- No change to `seconds_left >=120` or `btc30 >=15`.
- No change to +5c arm / 4c giveback.
- Presentation warnings are advisory; user manually executes.
- No order-placement code.
