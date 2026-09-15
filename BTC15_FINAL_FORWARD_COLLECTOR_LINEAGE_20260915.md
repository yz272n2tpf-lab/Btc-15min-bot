# BTC15 Protected FINAL Forward Collector Lineage — 2026-09-15

**Read only · signal only · manual execution · no orders**

## Historical protected FINAL reference

Frozen historical OOS reference remains:

- universe: 250 contracts;
- protected FINAL calls: 133;
- correct: 132/133 = 99.25%;
- FINAL-only coverage: 53.2%;
- average call time remaining: 5.04 minutes;
- median call time remaining: 5.0 minutes;
- average locked-side Kalshi ask: 92.99c;
- median locked-side ask: 94.4c;
- calls at or below 50c: 0/133.

This historical reference is an audit baseline only. It does not replace clean live confirmation.

## V2 — diagnostic only

`BTC15_FINAL_FORWARD_SCORECARD_V2.py`

V2 correctly separated direction accuracy from price/timing economics and excluded the contract already in progress when its process started. However, its background observer could stop advancing while the Railway HTTP process still remained SUCCESS. It also described the first newly discovered contract as a "full contract" even when production broad contract discovery occurred roughly 20–35 seconds after canonical start.

V2 gathered a small five-settled-lock live sample, including 4/5 correct, but that sample is **diagnostic only** and must never be combined with or quoted as the authoritative live confirmation sample.

## V3 — collector-health repair, diagnostic only

`BTC15_FINAL_FORWARD_SCORECARD_V3.py`

V3 changed collector reliability only:

- independent supervisor heartbeat;
- observer stale threshold of 30 seconds;
- stale/dead observer worker replacement without restarting or changing the protected model;
- generation guard to prevent stale worker continuation;
- watchdog state exposed through read-only health/state endpoints.

V3 passed 16 tests and demonstrated healthy real rollover advancement with zero observer restarts. It proved the silent-green collector failure was fixed.

V3 still inherited V2's inaccurate "full contract from rollover" denominator language. Therefore V3 live evidence is also **diagnostic only**.

## V4 — authoritative fresh live confirmation collector

`BTC15_FINAL_FORWARD_SCORECARD_V4.py`

Authoritative deployment:

- Railway service: `final-forward-scorecard-v1`
- service id: `fbe79688-25ed-4329-b0d6-c9b669559b17`
- deployment: `48b86488-3688-40d3-82b4-ad5fe028a61f`
- commit: `5a767fd40d394f86e9012bd96a9efefabfd081bf`
- status: SUCCESS
- regression gate: 22 V1+V2+V3+V4 tests PASS
- fresh cutoff: `2026-09-15T20:00:00Z`

### V4 coverage-universe rule

The protected FINAL path cannot qualify before the contract reaches **8:00 remaining**. Therefore second-zero observation is not required to grade FINAL coverage correctly.

A contract is eligible for the V4 live FINAL denominator only when the observer first sees that contract with at least **480 seconds remaining**, before the protected FINAL eligibility window can open.

A contract first seen with fewer than 480 seconds remaining is excluded fail-closed because an earlier protected FINAL lock could have been missed.

V4 explicitly records:

- `coverage_universe_semantics = FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW`;
- `full_contract_from_second_zero_required = false`;
- `full_contract_from_second_zero_claimed = false`;
- `protected_final_thresholds_changed = false`;
- `production_behavior_changed = false`;
- `orders = false`.

### V4 inherited protections

- V3 watchdog/supervisor preserved;
- protected FINAL model/thresholds unchanged;
- first protected lock per eligible contract only;
- official Kalshi settlement truth;
- direction accuracy, coverage, timing, and locked-side price scored separately;
- price remains evaluation telemetry, not a hidden FINAL qualification filter;
- no numeric flip-risk percentage introduced;
- no orders or automated execution.

## Live V4 confirmation gate

Do not call the live FINAL path confirmed until the frozen sample reaches at least:

- 30 eligibility-complete contracts; and
- 12 officially settled protected FINAL locks.

At that gate report separately:

- protected FINAL accuracy;
- FINAL-only coverage;
- average/median minutes remaining at lock;
- average/median locked-side Kalshi ask;
- count/rate/accuracy of any <=50c FINAL locks;
- number of contracts excluded for first observation after the <=8m eligibility window opened;
- watchdog restart/health status.

## Research-integrity rule

Do not combine V2 or V3 diagnostic live records with the V4 live sample. Do not retune protected FINAL thresholds from the V4 confirmation sample. Any later threshold change requires a separately declared research hypothesis and new future evidence.

## Safety

Production remains untouched. Protected FINAL remains signal-only/manual/no-orders.
