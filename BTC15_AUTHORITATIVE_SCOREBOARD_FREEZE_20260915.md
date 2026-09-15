# BTC15 Authoritative Scoreboard Freeze — 2026-09-15

**Read only · signal only · manual execution · no orders**

Purpose: freeze the meaning of the project scoreboard before more fresh-forward
results accumulate. The scoreboard is a presentation/aggregation layer only. It
must never recompute or alter protected EARLY, FINAL, SCALP, Flip Risk, or
production behavior.

## Frozen metric semantics

### FINAL
- Report protected FINAL directional accuracy only from officially settled
  protected FINAL locks.
- Report FINAL-only coverage separately.
- Report timing and locked-side Kalshi ask separately.
- A correct expensive FINAL remains expensive; accuracy does not imply entry
  quality.

### EARLY
- Report protected EARLY coverage, entry ask, timing, fair, and edge.
- Settlement same-side rate is secondary context only and must never be labeled
  FINAL accuracy.

### SCALP
- +5/+10/+15/+20 measures are price-movement / management metrics.
- They must never be labeled FINAL directional accuracy.
- The frozen reference currently carried by Scoreboard V1 is 115 completed serial
  opportunities with 77.4% +10c movement rate, plus a separate fresh reference
  cohort of 61 opportunities / 33 contracts with 82.0% +10c movement rate.

### EARLY excursion utility
- Entry is the protected EARLY ask.
- Tradable excursion is later same-side Kalshi BID minus entry ask.
- MFE/MAE and +5/+10/+15/+20c are descriptive utility measurements only.
- No excursion checkpoint becomes a new EARLY qualification rule automatically.

### EARLY -> FINAL handoff
- Only the frozen common-universe handoff audit may report union/any-anchor and
  dual-anchor coverage for its own sample.
- Separate EARLY and FINAL coverage percentages from different collectors or
  different start times must never be added together.

### Overall system
- Do not publish one blended "system accuracy" number. The modules measure
  different tasks and denominators.
- The >=90% actionable-union target is `NOT CERTIFIED` until an authoritative
  common-universe sample reaches its frozen review gate.

### Numeric Flip Risk
- Numeric Flip Risk remains hidden unless all are true:
  1. the future-only calibration collector reaches its frozen sample gate;
  2. numeric calibration passes its frozen validation requirements;
  3. a later manual review explicitly approves user-facing numeric display.
- Until then, the scoreboard must show `HIDDEN_UNTIL_VALIDATED` rather than a
  guessed percentage.

## Fail-closed rules
- Any input explicitly reporting `orders=true`,
  `manual_execution_only=false`, or `production_behavior_changed=true` invalidates
  that scoreboard combination.
- Missing sources must be shown as `NOT CONNECTED`, never silently replaced with
  historical numbers.
- Historical references and fresh-forward confirmation samples must remain
  labeled separately.

## Implementation
- Pure combiner: `BTC15_AUTHORITATIVE_SCOREBOARD_V1.py`
- Regression suite: `test_BTC15_AUTHORITATIVE_SCOREBOARD_V1.py`
- This freeze does not authorize a production deployment or dashboard replacement.
