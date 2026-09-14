# BTC15 Generalized SCALP Live Transition Smoke Checkpoint — 2026-09-14

**Status:** FIRST LIVE MANAGEMENT TRANSITION PASSED  
**Mode:** SIGNAL ONLY | NO ORDERS

This checkpoint records the first live state-transition sequence after the V3 integration-state bridge and 0.5-second read-only transition monitor were deployed. It is not the full combined EARLY + FINAL + SCALP smoke test.

## Infrastructure / invariants

- Deployment: `fb54ba15-5409-4690-afe7-7898c5205f48`
- Transition monitor compiled successfully: `TRANSITION_MONITOR_COMPILE_EXIT=0`
- V3 state bridge started successfully.
- Exact generalized collector bootstrap SHA remained unchanged: `52b79e239c0be2b5ece93e3387063185ce51be8a01413f6b76bc5939924fb3ad`
- Collector remained PRICE-AGNOSTIC and SIGNAL ONLY / NO ORDERS.
- BRTI was PRIMARY_OK at smoke startup.

## Contract rollover behavior observed

The monitor safely crossed from `KXBTC15M-26SEP141015-15` into `KXBTC15M-26SEP141030-30`.

On the new contract it initially emitted:

- `PASS / NO QUALIFIED SCALP`

The first raw DOWN candidate did not satisfy the frozen generalized primary qualification. The bridge therefore remained PASS rather than inventing an actionable signal.

A later UP candidate earned the frozen challenger and the integrated state changed to ACTIVE.

## First live ACTIVE -> PROTECT -> EXIT sequence

Contract: `KXBTC15M-26SEP141030-30`

### ACTIVE

At `2026-09-14T14:17:17.434Z`:

- state: `ACTIVE`
- side: `UP`
- executable gain: `-1.0c`
- running peak: `-1.0c`
- message: `SCALP ACTIVE · BUILDING`
- current contract time left: `768.5s`
- event age at integrated observation: `1.06s`

### PROTECT / protection armed

At `2026-09-14T14:17:57.500Z`:

- state: `PROTECT`
- side: `UP`
- executable gain: `+11.0c`
- running peak: `+11.0c`
- giveback: `0.0c`
- message: `PROTECTION ARMED · WINNER RUNNING`
- current contract time left: `736.4s`
- event age at integrated observation: `0.72s`

This confirms the protection warning was visible while the winner was still at its running peak, rather than waiting for the frozen EXIT giveback.

### EXIT

At `2026-09-14T14:18:24.767Z`:

- state: `EXIT`
- side: `UP`
- executable gain: `+6.0c`
- running peak: `+11.0c`
- giveback observed: `5.0c`
- message: `EXIT / PROTECT PROFITS NOW`
- current contract time left: `704.4s`
- event age at integrated observation: `1.43s`

The executable market moved through the nominal 4c giveback threshold between observations, so the first observed EXIT row showed 5c giveback. No threshold was changed.

## What this proves

- The frozen generalized challenger can transition live from ACTIVE to management states.
- The +5c protection arm becomes user-visible before EXIT.
- A real live +11c winner produced `PROTECTION ARMED · WINNER RUNNING` while still at peak.
- The later frozen EXIT became visible with roughly 1.4s event age in this example.
- Contract rollover did not blend an old scalp into the new contract.
- No order action was created.

## What is still not proven by this checkpoint

- This single sequence is not enough to call the entire integrated smoke complete.
- We still need additional live time/state coverage, especially first-pullback advisory behavior when a move does not jump directly through the 4c EXIT threshold.
- Protected FINAL must still be explicitly verified to transition before contract zero in the combined payload.
- Protected EARLY + FINAL + SCALP cross-service contract/timer alignment still needs the combined live smoke.
- Dashboard end-to-end rendering latency still needs final verification after the main app is wired to the combined payload.

No trading threshold was selected or retuned from this smoke checkpoint.
