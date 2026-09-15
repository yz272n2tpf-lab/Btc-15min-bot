# BTC15 Combined Forward Scorecard Freeze — 2026-09-15

**Mode:** FRESH FORWARD OBSERVATION ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

## Purpose
Measure the already-protected EARLY, current serial V5 SCALP, and protected FINAL modules on one common live contract universe without retuning any module.

## Frozen start / sample integrity
- Frozen cutoff: `2026-09-15T18:00:00Z`.
- The contract in progress when the observer starts is excluded.
- The observer arms only on the first observed contract rollover at or after the cutoff.
- Therefore every counted contract is observed from its beginning.

## Frozen review sample
- Minimum fully observed contracts: **30**.
- Minimum officially settled contracts: **25**.
- This is an integration/measurement smoke gate, not a strategy-promotion gate.
- No EARLY, FINAL, or SCALP threshold may be selected or changed from this sample.

## Contract-level union semantics
A contract is `union_actionable=True` if at least one independently validated path qualifies:
- protected EARLY,
- serial V5 SCALP,
- protected FINAL.

A contract is counted **once** in UNION coverage even when:
- EARLY and FINAL both qualify,
- EARLY and one or more SCALPs qualify,
- FINAL and one or more SCALPs qualify,
- all three paths qualify,
- two, three, or more serial SCALPs occur in the same contract.

Serial SCALP opportunity count is preserved separately from contract coverage.

## Metrics
### EARLY
- calls / contract coverage
- official-settlement accuracy
- actual entry ask
- <=50c count/rate/accuracy
- timing

### SCALP
- contracts with at least one qualified serial opportunity
- total serial opportunities
- contracts with 2+ serial opportunities
- +5c / +10c / +15c / +20c completed-opportunity rates
- protected exits / positive protected exits
- ENDED_UNARMED count (non-actionable exit invariant)
- entry price and timing telemetry

### FINAL
- calls / contract coverage
- official-settlement accuracy
- locked-side Kalshi ask
- <=50c count/rate/accuracy
- timing

### Combined
- UNION actionable coverage
- uncovered contracts
- path-combination counts
- common settled contract universe

## Safety / anti-drift
- Production code is not changed.
- Protected EARLY thresholds are not changed.
- Protected FINAL thresholds are not changed.
- Frozen V5 serial SCALP qualification / +5c arm / 4c giveback are not changed.
- SCALP price remains telemetry/guidance, not a hidden eligibility filter.
- ENDED_UNARMED remains informational lifecycle metadata, never an EXIT instruction.
- Armed/no-validated-exit remains protected; no reset loophole.
- No numeric flip-risk percentage is invented.
- No orders, no auto trading, no auto promotion.
