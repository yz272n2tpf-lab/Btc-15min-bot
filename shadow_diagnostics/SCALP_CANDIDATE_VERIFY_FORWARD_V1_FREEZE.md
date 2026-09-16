# BTC15 Candidate -> Verify Forward V1 — Prospective Freeze

**Prospective cutoff:** `2026-09-16T11:10:33Z`  
**Local equivalent:** `2026-09-16 07:10:33 EDT`  
**CI-gated code commit before cutoff:** `7ecfb408a7d3e4550747352c6fcaf52f2699fe9e`  
**Mode:** SHADOW ONLY / DEVELOPMENT COMPARISON / NO ORDERS / NO AUTO-PROMOTION

## Fixed policies

The future comparison is frozen to exactly:

- Immediate entry
- Verify after 5 seconds
- Verify after 10 seconds
- Verify after 15 seconds
- Verify after 30 seconds

No delay may be added, removed or redefined using this future sample.

## Executable-price accounting

For each delayed policy:

1. Start from the unchanged baseline serial candidate.
2. Wait until the requested delay.
3. Enter at the **first then-current executable ASK observed at or after the delay**.
4. Ignore all price movement before that verified entry.
5. Score only **subsequent executable BID** versus the delayed ASK.
6. Rebase the +5c arm / 4c giveback protection lifecycle from the delayed entry.
7. Use the same fee scenarios as Scalp Economics V1 for observed protected exits.

A pre-delay +10c move cannot count for a delayed policy. A +10c touch remains movement telemetry and is not automatically realized profit.

## Prospective denominator

A contract enters only if:

- its first passive tape observation is at or after `2026-09-16T11:10:33Z`, and
- it is later proven fully observed from >=840 seconds left through <=60 seconds left.

Contracts already underway at the cutoff are excluded. Quiet fully observed contracts remain part of the true future denominator.

## Reported tradeoffs

For each policy:

- scoreable signals and unavailable verified entries
- signal retention vs Immediate
- contract retention vs Immediate
- true future-contract coverage
- actual delay achieved
- entry ASK and entry slippage versus the candidate ASK
- <=50c and 25–35c entry rates
- +5c / +10c / +20c movement
- protected-exit rate and gross captured gain
- conservative 1-lot and 10-lot taker/taker net economics
- timing and scalp opportunity index

## Development evidence-readiness

The comparison remains `COLLECTING` until all are true:

- >=100 fully observed future contracts
- >=100 Immediate serial signals
- >=50 scoreable 30-second verified signals

Then it may become `READY_FOR_MANUAL_DEVELOPMENT_COMPARISON`.

This is **not** a production promotion gate. If a delay is selected after reviewing this sample, that policy must be frozen and tested on a later fresh prospective certification window before any use in the live signal ladder.

## Safety

- no policy selection in code
- no same-sample promotion
- no production writes
- manual execution only
- no orders
- Coverage Rescue V1 remains untouched
- Economics Forward V1 remains untouched
- Regime Observation V1.1 remains untouched
