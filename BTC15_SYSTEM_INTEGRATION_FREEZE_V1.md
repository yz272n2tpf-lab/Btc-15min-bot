# BTC15 System Integration Freeze V1

**Status:** FROZEN BEFORE COMBINED INTEGRATION  
**Mode:** SIGNAL ONLY | NO ORDERS

## Purpose

Define how the separately validated EARLY, FINAL, and SCALP modules are allowed to coexist before they are wired into one combined live system. This freeze is intentionally written before combined behavior is judged so integration cannot silently change the meaning of any protected signal.

## Modules entering integration

### Protected Tier-1 EARLY

Actionable directional entry only when the existing protected rule qualifies:

- preferred ask <= 45c
- preferred fair >= 75%
- edge >= 8 percentage points
- 2 to 10 minutes remaining
- absolute exact Kalshi target gap >= $25
- first qualifying row per contract

Reference holdout: 20/22 = 90.9%, 22% coverage, 31.9c average ask, 34.0c median ask, 6.09 minutes remaining on average.

The 2026-09-14 PRE-WATCH/handoff extension failed its frozen research gates and is NOT actionable. It must not be smuggled into integration as a second EARLY tier.

### Protected FINAL

Settlement-direction authority only when the existing protected rule qualifies:

- fair >= 90%
- <= 8 minutes remaining
- exact-target gap >= $75 when >6 minutes remain
- exact-target gap >= $50 when <=6 minutes remain
- distance / recent 5m range >= 1.0x
- preferred fair side = current target side

Historical untouched reference: 46/47 = 97.9% qualified accuracy, 47% coverage, average 4.64 minutes remaining.

FINAL is a settlement call. It is not automatically an attractive entry-price recommendation.

### Generalized SCALP

Locked short-horizon executable-price opportunity:

- first candidate per contract satisfying the frozen challenger
- seconds_left >= 120
- side-aligned btc30 >= $15
- no entry-price eligibility filter
- actual executable ask-to-future-bid economics
- management arms after +5c executable gain
- protect/exit after 4c giveback from running executable peak
- one primary qualified scalp signal per contract

Untouched forward confirmation: 40 completed qualified contracts, 93.0% actionable coverage, +5c 87.5%, +10c 62.5%, +20c 32.5%, managed average +11.23c, median adverse excursion -1.00c.

## Independence rule

EARLY, FINAL, and SCALP are separate authorities with different horizons. Integration must never turn disagreement into silent overwriting.

- EARLY answers: is there a validated cheap directional entry before Kalshi fully reprices?
- FINAL answers: which side is strongly favored to settle above/below the exact target?
- SCALP answers: is there a validated short-horizon executable Kalshi price move available now?

A SCALP may legitimately point opposite FINAL. That is a countertrend/reversal scalp, not automatically an error.

A later FINAL may disagree with an earlier EARLY entry. The combined system must preserve the historical EARLY call and separately show the newer FINAL state. Any exit/protection decision must come from separately validated management logic, not by rewriting the old signal.

## Canonical combined states

Every contract gets three independent module states:

- EARLY: `PASS` or `QUALIFIED`
- FINAL: `WATCH`, `QUALIFIED`, or `LOCK`
- SCALP: `PASS`, `ACTIVE`, `PROTECT`, or `EXIT`

`LOCK` is reserved for the protected high-confidence FINAL path and must not be generated from scalp momentum alone.

`PROTECT` / `EXIT` are scalp-management states only until a separate EARLY/FINAL exit model is validated.

## Display precedence — no signal deletion

The dashboard may choose a visual priority, but all active modules remain visible.

1. Safety/management message: SCALP `EXIT` or `PROTECT`.
2. FINAL `LOCK` / `QUALIFIED` settlement state.
3. EARLY `QUALIFIED` entry state.
4. SCALP `ACTIVE` opportunity.
5. WATCH/PASS context.

Priority controls presentation only. It never changes the underlying module result.

## Conflict labels

When modules disagree, emit an explicit context label rather than suppressing a signal:

- `COUNTERTREND_SCALP` — active scalp side differs from current FINAL favored side.
- `EARLY_FINAL_DIVERGENCE` — current FINAL qualified side differs from earlier qualified EARLY side.
- `ALIGNED` — active actionable modules point the same direction.
- `MIXED_HORIZONS` — more than one actionable module is active and at least one differs in side/horizon.

No conflict label may itself become a trade signal.

## Union actionable coverage

A contract is counted as actionable when at least one separately validated path qualifies:

- protected Tier-1 EARLY, or
- generalized SCALP primary signal, or
- protected FINAL qualified/lock state.

Do not double-count contracts with multiple paths. Report both module coverage and union coverage.

A WATCH state never counts as actionable coverage.

## Price semantics

- EARLY price is eligibility: protected ask cap <=45c.
- SCALP price is telemetry/economics only; never create a price eligibility filter from the forward sample.
- FINAL probability and FINAL entry economics are separate. A strong settlement call can exist when the Kalshi price is already unattractive for a new entry.

## Timing semantics

The combined system must preserve exact contract clock alignment and report seconds/minutes remaining from one canonical contract timeline.

No module may use an independently drifting 15-minute boundary.

## Flip / reversal risk

Do not display an uncalibrated numeric flip/reversal-risk percentage.

Until a separate calibration earns a numeric output, the integration payload may expose only evidence fields or a clearly non-numeric warning state. No fabricated percentage.

## Entry / exit messaging

The integration layer is advisory only:

- never submit orders
- never auto-buy or auto-sell
- never hold API order permissions as part of this layer
- user manually executes every trade

For SCALP, the validated management state may show protect/exit guidance from the +5c arm / 4c giveback rule.

For EARLY and FINAL, no new exit rule is invented during integration.

## Combined acceptance checks

Before this integration is called stable, verify:

1. Protected EARLY outputs are byte-for-byte/equivalently unchanged on replay fixtures.
2. Protected FINAL outputs are equivalently unchanged on replay fixtures.
3. Frozen SCALP qualification/management outputs are equivalently unchanged on its forward fixtures.
4. Module disagreement is visible and never silently resolved by overwriting.
5. Union actionable coverage is calculated once per contract without double counting.
6. No WATCH state is counted as actionable.
7. No unvalidated numeric flip risk is emitted.
8. Exact target and contract timer remain aligned.
9. Combined service remains SIGNAL ONLY / NO ORDERS.
10. A 20–30 minute integrated smoke test shows live feeds, state transitions, and management transitions without module regression.

## Next engineering step

Build a pure, side-effect-free integration/state-composition layer against this contract. Unit-test the state precedence and conflict rules offline before wiring it into the live bot/dashboard.
