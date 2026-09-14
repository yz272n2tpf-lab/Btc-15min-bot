# BTC15 Protected FINAL Live Timing Checkpoint — 2026-09-14

**Mode:** OBSERVATION ONLY | SIGNAL ONLY | NO ORDERS  
**Protected FINAL thresholds:** UNCHANGED

## Purpose

Explicitly verify the old live bug — FINAL remaining in WAIT until the 15-minute clock reached zero — is not present in the current main-bot behavior.

## Observed contract

Contract: `KXBTC15M-26SEP141030-30`

The main service emitted:

- `POSITION-PROTECTION FINAL_TRIGGER | KXBTC15M-26SEP141030-30 | DOWN`
- timestamp: `2026-09-14T14:26:36.407Z`

The contract closed at 14:30 UTC, so the FINAL trigger occurred approximately **3 minutes 24 seconds before contract end**.

At the first normal status line immediately after the trigger (`14:26:39Z`):

- clock remaining: **3.34 minutes**
- BTC gap vs exact Kalshi target: **-$249.66**
- Kalshi DOWN: **95.6 bid / 95.8 ask**
- direct BRTI: **$78,242.64**
- direct BRTI gap vs target: **-$238.61**
- BRTI side: **DOWN**
- BRTI age: **0.6 seconds**
- BRTI ready: **True**
- live fair preferred: **DOWN, 90.1%**
- BRTI agreement: **True**

## Result

**PASS for the specific wait-to-zero regression check.**

The protected FINAL path demonstrably triggered several minutes before zero in live operation. This does not replace the historical holdout timing reference of 4.64 minutes average / 5.0 minutes median; it is one live integration checkpoint confirming the old zero-clock failure mode is not currently present.

## Remaining infrastructure note

BRTI HTTP 429 warnings were still visible immediately before and after this FINAL trigger. The call succeeded because a fresh authoritative BRTI observation became available in time. BRTI acquisition reliability remains an infrastructure item to improve without changing protected FINAL thresholds or freshness/side-agreement semantics.

## Guardrails

- No FINAL threshold changed.
- No BRTI freshness requirement changed.
- No Kalshi-price entry recommendation is inferred from the FINAL trigger.
- No orders.
