# BTC15 Scalp Economics + Exit Certification V1

**Mode:** RESEARCH ONLY / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION  
**Branch:** `scalp-economics-exit-cert-v1`  
**Base:** frozen Coverage Rescue forward foundation commit `22b8371bd12a714544396f4d073fccc7e038353f`

## Purpose

Measure what the existing serial scalp ladder actually captures at executable prices. A path touching +10c is movement evidence only; it is not treated as a realized +10c trade.

## Frozen accounting definitions

- Entry = executable candidate ASK.
- Existing detector and serial lifecycle remain unchanged.
- Existing protection lifecycle remains +5c arm / 4c giveback.
- Protected exit = first observed executable BID satisfying that lifecycle.
- Gross protected gain = protected exit BID - entry ASK.
- Unprotected paths receive **no synthetic realized exit**.
- MFE, MAE, +5/+10/+20 touches stay movement telemetry.
- Giveback from peak and capture efficiency are reported separately.
- Scalp #1/#2/#3/#4 are scored separately as well as together.

## Fee model

Kalshi event-contract fee schedule effective July 7, 2026:

- general taker fee: `ceil_cent(0.07 * M * C * P * (1-P))`
- general maker fee: `ceil_cent(0.0175 * M * C * P * (1-P))`
- general taker multiplier defaults to 1
- general maker multiplier defaults to 0 unless a series is listed otherwise

`KXBTC15M` was not found in the non-standard-series listing in the July 7, 2026 schedule. V1 therefore reports the general schedule as a modeled fee scenario.

Lot sizes 1, 10 and 100 are scored independently because order-level fee rounding changes per-contract drag.

Fee views:

1. TAKER_TAKER — conservative immediate entry + immediate exit scenario.
2. MAKER_ENTRY_TAKER_EXIT — resting entry under default maker multiplier plus active exit.

Gross and fee-adjusted results are never blended.

## Historical diagnostic first

The first live reviewer is historical diagnostic only. It may describe the existing tape but cannot certify or promote an exit/economics rule.

## Forward certification principle

After the historical diagnostic is read, any certification gate must be frozen **before** future contracts are used for certification. A future scorer must use a timestamp cutoff and must not retune the accounting rule or protection lifecycle after seeing prospective results.

## Safety

- no production logic changes
- no order capability
- no automatic promotion
- no fabricated fills
- no unprotected path counted as realized P&L
- no +10 touch counted as realized +10
