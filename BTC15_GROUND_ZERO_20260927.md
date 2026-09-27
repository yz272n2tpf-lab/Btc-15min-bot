# BTC15 Ground Zero — Frozen Baseline

Frozen: 2026-09-27
Production merge SHA: b3b58dcc3186fa1a7a0972bf9b2321b4577f9be6
Qualified candidate SHA: 526bd95c9aca63dbb5ecd5d0a7c2fbfc46767602
Qualification: 366/366 PASS

## Live acceptance
Contract: KXBTC15M-26SEP270915-15
Target: 84791.51
Authoritative BRTI settlement: 60/60
Final60 average: 84657.950166...
Final60 side: DOWN
Native cohort rows: 152
Disk-only scorer: COMPLETE
Missing: []

## Lane baseline
FINAL: PASS (no qualified FINAL CALL)
EARLY: PASS (no qualified provisional candidate)
TRUE SCALP: PASS (coverage proven; no qualified scalp)
PROFIT PROTECTION: NOT_APPLICABLE
SETTLEMENT: COMPLETE
SIGNAL_ONLY: true
ORDERS: false

## Frozen test objectives
Every 15-minute contract is observed and scored, including PASS/no-edge contracts.
FINAL qualified-call accuracy is measured out of sample.
EARLY-call timing and entry quality are measured; target buy <=50%, ideal 25-35%.
TRUE SCALP/reversal opportunities are measured separately from FINAL.
Flip Risk, 5m caution, 3m guard, exit/profit-protection behavior are retained.
Kalshi ticker/target/clock and BRTI settlement alignment remain mandatory.
Evidence completeness is mandatory; missing evidence is never silently scored as success.
Signal-only behavior is mandatory; no order execution.

This file freezes Ground Zero. Do not retroactively alter this baseline to improve later results.
