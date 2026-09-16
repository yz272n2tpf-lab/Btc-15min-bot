# BTC15 Scalp Coverage Rescue V1 — FROZEN

Status: **FROZEN BEFORE PROSPECTIVE WINDOW**  
Mode: **SHADOW / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION**

## Why this lane exists

The existing baseline is preserved unchanged:

- seconds left >= 120
- side is UP or DOWN
- side-aligned BTC30 >= 15
- +5c arm / 4c giveback serial lifecycle remains the baseline reference

The development gap audit found that the most recoverable missed-contract class was `BTC30_BELOW_BASELINE_15`. Coverage Rescue V1 is a separate lane for that class. It does **not** loosen the baseline.

## Frozen Rescue V1 trigger

A candidate is a Rescue V1 signal only when **all** are true at candidate time:

1. valid UP/DOWN side
2. seconds left >= 120
3. 8 <= side-aligned BTC30 < 15
4. baseline rule is false (therefore no duplicate baseline signal)
5. Kalshi entry ask <= 0.50
6. BTC 5-second normalized momentum >= 0.60
7. confirm count >= 2
8. absolute Kalshi 15-second ask move <= 0.02
9. structure is intact
10. primary BRTI feed is healthy
11. BTC/BRTI agree with the candidate side at both 5s and 15s
12. neither BTC nor BRTI is against the candidate side
13. no dual reversal evidence
14. maximum one Rescue V1 signal per contract

No PATH, RESULT, future bid, future gain, settlement, peak, +5/+10/+20 label, or other future field is allowed to affect this trigger.

## Mechanical evaluation repair — separate from predictive edge

Missing RESULT rows are not treated as model signal quality.

- If a signal has adequate PATH telemetry, its executable path may be evaluated and tagged `PATH_RECONCILED`.
- If PATH is inadequate, the signal remains `UNRESOLVED`; it is not silently scored as a win or loss.
- Serial reset is allowed only when the observed path proves the protected exit. No invented timeout/reset is used.
- Mechanical reconciliation does not change whether a signal fired.

## Prospective universe rule

The forward scorer requires an explicit UTC cutoff. A contract enters the prospective denominator only when:

- its **first passive observation is at or after the cutoff**, and
- it is later proven fully observed with >=840 seconds-left evidence and <=60 seconds-left evidence.

A contract already in progress at the cutoff is excluded. Historical/development contracts can never enter the prospective score.

## Frozen certification gates

No certification decision is allowed until both sample requirements are met:

- >=100 fully observed future contracts
- >=8 scoreable Rescue V1 signals

Then all of these must hold:

- Baseline + Rescue union true contract coverage >= 90%
- Rescue V1 scoreable +10c conversion >= 60%
- Union +10c conversion is no more than 3 percentage points below the contemporaneous baseline +10c conversion
- Rescue V1 average entry ask <= 50c
- Rescue V1 average entry timing >= 6.0 minutes remaining

Additional metrics remain visible: +5c, +20c, affordable-contract coverage, median ask/timing, unresolved signals, PATH-reconciled signals, and incremental rescue contracts.

## Interpretation

The historical gap/recovery tape was used only to develop this rule. It cannot certify it. The next prospective window is the deciding evidence.

Even if every gate passes, status is only **READY_FOR_MANUAL_REVIEW_PASS**. There is no automatic production promotion and no order capability.
