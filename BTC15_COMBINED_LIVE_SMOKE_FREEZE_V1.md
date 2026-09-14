# BTC15 Combined Live Smoke Freeze V1

**Status:** FROZEN BEFORE CROSS-SERVICE LIVE SMOKE  
**Mode:** SIGNAL ONLY | NO ORDERS

## Purpose

Define the acceptance checks for the short live smoke that combines protected EARLY, protected FINAL, and generalized SCALP. This smoke validates integration behavior only; it does not retune trading thresholds or re-score historical model accuracy.

## Fixed authority rules

- Main protected dashboard state is the authority for contract, exact target, Kalshi quotes, and canonical time remaining.
- Protected Tier-1 EARLY is read without recomputing or weakening its rule.
- Protected FINAL is read without recomputing or weakening its rule.
- Generalized SCALP comes only from the frozen V3 read-only state bridge.
- A SCALP contract mismatch fails closed and must never be blended into the main contract.
- A SCALP opposite FINAL is visible as a horizon conflict; neither signal is silently deleted.
- SCALP EXIT remains latched after the first frozen post-arm 4c giveback.
- No numeric flip/reversal-risk percentage.
- Manual execution only. No orders.

## Smoke duration

Target approximately **20–30 minutes** of combined live observation, long enough to cover at least one normal 15-minute contract rollover.

A contract does not have to produce every possible signal state for the smoke to pass. A valid PASS/WATCH contract remains legitimate when no protected gate qualifies.

## Acceptance checks

The integration smoke passes only if all observable checks hold:

1. **Contract sync:** when main and SCALP contract IDs match, states may compose; when they do not, SCALP fails closed as `SCALP WAIT · CONTRACT SYNC`.
2. **Canonical clock:** displayed/combined time remaining always comes from the protected main state, never an independently drifting scalp clock.
3. **Rollover:** no signal from the previous contract is shown as actionable on the next contract.
4. **EARLY preservation:** protected EARLY state/side/ask/fair are passed through unchanged.
5. **FINAL preservation:** protected FINAL state/side/fair are passed through unchanged.
6. **FINAL zero-clock regression:** if a protected FINAL qualifies during the smoke, it must become visible before contract zero. A contract with no qualifying protected FINAL is not forced to call.
7. **SCALP protection:** +5c arm is visibly represented as protection armed; an observed pullback after arm may warn before the frozen EXIT; first frozen 4c giveback latches EXIT.
8. **Management display latency target:** when the event tape changes into PROTECT/EXIT, the integration monitor/dashboard path should surface the new management state within **3 seconds** under normal service health. This is a UI/integration responsiveness requirement, not a trading threshold.
9. **Conflict visibility:** opposite active horizons emit explicit context instead of overwriting one another.
10. **Union counting:** a contract is actionable once if any separately validated path qualifies; WATCH/PASS alone never count.
11. **Fail closed:** malformed/stale/unavailable cross-service input must not fabricate an actionable state.
12. **No orders:** no order-placement action or credential-bearing payload is introduced.

## Existing checkpoints entering this smoke

Already established before this combined smoke:

- pure integration unit tests passed,
- deterministic combined fixture scorecard passed,
- generalized SCALP forward challenger earned KEEP,
- first live scalp management sequence showed protection state at ~0.7s event age and EXIT at ~1.4s event age,
- EXIT-resurrection bug was found and fixed; 66-test regression suite passed,
- persistent-tape regression confirmed EXIT remains latched after later price recovery,
- one protected FINAL live trigger occurred roughly 3m24s before zero, explicitly disproving the old wait-to-zero failure mode for that checkpoint.

The combined smoke must preserve those behaviors; it may not change their thresholds.
