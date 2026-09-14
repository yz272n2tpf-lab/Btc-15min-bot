# BTC15 Generalized SCALP EXIT-Latch Regression Result — 2026-09-14

**Status:** PASS  
**Mode:** SIGNAL ONLY | NO ORDERS

## Bug found by live smoke

The first V3 live transition smoke correctly produced:

`ACTIVE -> PROTECT -> EXIT`

but the read-only integration adapter later reverted the same primary scalp from `EXIT` back to `PROTECT` after Kalshi price recovered. That contradicted the frozen forward scorer, which exits chronologically at the first post-arm 4c giveback and does not resurrect the already-exited primary signal.

This was an integration-state bug, not a problem with the frozen generalized SCALP entry rule.

## Fix

`btc15_protected_module_adapter_v1.py` now scans PATH rows chronologically:

1. build running executable peak,
2. arm once running peak reaches +5c,
3. detect the first >=4c giveback,
4. latch EXIT at that observation,
5. stop processing that primary signal for management state.

A later recovery cannot turn the exited signal back into ACTIVE/PROTECT. Any future re-entry would require a separately validated re-entry module.

## Regression suite

Deployment: `ecf8b89c-b808-4bd2-bf5e-2d781218bfc7`

- total tests: **66**
- result: **OK**
- marker: `INTEGRATION_LATCH_TEST_EXIT=0`

The suite included:

- pure integration invariants,
- protected-module adapter tests,
- V2/V3 state-bridge tests,
- scalp management presentation tests,
- cross-service combined payload tests,
- fail-closed resilient BRTI helper tests,
- protected FINAL BRTI authority-semantic tests,
- explicit later-recovery-after-EXIT regression cases.

## Persistent-tape live verification

When the fixed deployment started, the persistent volume still contained the earlier live contract in which price had recovered after the first EXIT.

At `2026-09-14T14:30:41.812Z`, the fixed monitor replayed/derived the completed contract as:

- contract: `KXBTC15M-26SEP141030-30`
- state: **EXIT**
- side: UP
- latched executable exit gain: **+6.0c**
- latched running peak at exit: **+11.0c**
- giveback at exit: **5.0c**
- message: `EXIT / PROTECT PROFITS NOW`

This is the same contract that had previously reverted to PROTECT after a later recovery. Under the fixed chronology it correctly remained EXIT.

The next contract then rolled to `KXBTC15M-26SEP141045-45` and began cleanly as PASS before a new independent scalp candidate appeared.

## Integrity checks

- Exact generalized collector bootstrap SHA remained unchanged: `52b79e239c0be2b5ece93e3387063185ce51be8a01413f6b76bc5939924fb3ad`.
- No SCALP entry threshold changed.
- No price eligibility filter added.
- +5c arm / 4c giveback unchanged.
- No order code.

## Decision

**EXIT-latch regression is fixed and the fix matches the already-frozen scorer chronology.**

Continue the short live integration smoke for state/timer/feed behavior, but do not reopen or retune the generalized SCALP rule from this result.
