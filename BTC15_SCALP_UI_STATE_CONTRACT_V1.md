# BTC15 Scalp UI State Contract V1

**PURE PRESENTATION | READ ONLY | SIGNAL ONLY | NO ORDERS**

This contract sits on top of the existing Combined State Bridge V5. It does not replace the bridge, detector, serial lifecycle, FINAL, EARLY, or any prospective research collector.

## Frozen display rules

### Scalp lifecycle
- `PASS` -> display `WAIT`
- `ACTIVE` -> display `ACTIVE`
- `PROTECT` -> display `PROTECT`
- `EXIT` -> display `EXIT`
- Any stale, misaligned, or integration-not-ready scalp source -> display `WAIT` fail-closed.
- The underlying lifecycle state remains visible for diagnostics and is never rewritten by entry-price guidance.

### Entry-price guidance
Presentation only; it cannot suppress or promote a signal.
- 25-35c -> `IDEAL_25_35`
- 36-50c -> `GOOD_36_50`
- >50c -> `CAUTION_ABOVE_50` / `CAUTION · WAIT FOR PULLBACK`
- <25c -> `BELOW_IDEAL_BAND` / review signal quality; it is not automatically treated as stronger confidence.

### Profit protection
The existing frozen scalp lifecycle remains authoritative.
- +5c protection arm is unchanged.
- Existing pullback context may be displayed as context.
- Existing frozen 4c giveback `EXIT` may be displayed.
- The new Watch->Exit 1c/2c/3c prospective research thresholds are **not** exposed in this V1 contract and cannot change the current lifecycle.

### Flip Risk
Numeric Flip Risk remains hidden in V1 even if an upstream payload accidentally contains a number. A separate certified integration is required before any numeric Flip Risk can become visible.

### Horizon separation
EARLY, FINAL and SCALP context may be shown together, but no blended accuracy or combined performance score is created.

### Serial scalp context
The contract exposes:
- current opportunity index;
- completed serial opportunities;
- whether the lifecycle is scanning for the next opportunity.

There is no artificial scalp-count cap in this presentation layer.

## Safety invariants
- `manual_execution_only = true`
- `orders = false`
- `order_action = null`
- no API/order side effects
- no production deploy from this research branch
- no threshold tuning
- no signal qualification
- no research promotion
