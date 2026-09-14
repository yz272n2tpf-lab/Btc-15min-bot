# BTC15 EARLY + FINAL Ladder — Post-Scalp Phase Plan V1

**Status:** preparation only; no live behavior changes  
**System:** SIGNAL ONLY; manual execution; NO ORDERS  
**Change-control:** preserve locked/provisionally locked anchors; fill gaps around them rather than weakening them.

## Why this exists

Once the frozen generalized scalp forward test is judged, development returns immediately to the EARLY + FINAL ladder. This document freezes the next-phase questions now so the project does not drift while scalp confirmation is collecting.

## Existing anchors that must be protected

### Tier-1 EARLY entry anchor

Current untouched historical holdout:

- qualified entry accuracy: 90.9% (20/22)
- coverage: 22%
- average actual Kalshi ask: 31.9c
- median ask: 34.0c
- average time left: 6.09m
- median time left: 6.0m

Current rule:

- ask <=45c
- fair >=75%
- edge >=8 percentage points
- 2–10 minutes left
- absolute exact Kalshi target gap >=$25
- no persistence requirement
- no strengthening requirement
- no forced current-side agreement

This tier is an anchor, not the finished early-entry ladder.

### High-confidence FINAL anchor

Current untouched historical holdout:

- qualified FINAL accuracy: 97.9% (46/47)
- coverage: 47%
- average time left: 4.64m
- median time left: 5.0m

Current rule:

- fair >=90%
- <=8 minutes left
- gap >=$75 when >6 minutes remain
- gap >=$50 when <=6 minutes remain
- distance / recent 5m range >=1.0x
- preferred fair side = current target side

This tier is a protected high-confidence FINAL anchor. Do not weaken it simply to create more calls.

## Ladder objective

Create one coherent 15-minute state progression that continuously explains what the bot believes without forcing a trade:

1. OBSERVE / PASS
2. EARLY WATCH
3. EARLY QUALIFIED (protected Tier-1 remains authoritative when its rule fires)
4. EARLY STRENGTHENING / WEAKENING telemetry
5. FINAL WATCH
6. FINAL QUALIFIED (protected FINAL rule remains authoritative when its rule fires)
7. LOCK when evidence supports >=90% final conviction with remaining-time context
8. WATCH / PROTECT / EXIT when post-entry evidence deteriorates

The labels above are UI/state-machine roles, not permission to invent new probability thresholds. Any new threshold must earn validation offline before it can become behavior.

## Permanent separation rules

- EARLY entry predicts an economically attractive directional entry before full repricing.
- FINAL predicts settlement direction versus the exact Kalshi target.
- SCALP predicts short-horizon executable price movement and may disagree with FINAL.
- EXIT / protection manages an already-actionable opportunity.
- One module may inform risk/context telemetry but may not overwrite another module's authority without a separately validated handoff rule.

## EARLY ladder unfinished questions

1. Can we identify a useful pre-Tier-1 WATCH state earlier than the current ~6-minute anchor without destroying accuracy/economics?
2. Can strengthening/persistence evidence raise confidence after a cheap entry without delaying the entry itself?
3. Can weakening evidence prevent bad Tier-1 calls or create an earlier WAIT/PASS state without gutting coverage?
4. Can pullback/re-entry add economic value after the first directional opportunity without duplicate-firing noise?
5. Can the ladder preserve the preferred <=50c ask, especially the ~20–40c range, while moving accuracy toward the agreed 93–95% target where evidence allows?
6. Can the bot explain WHY an early signal is WATCH / QUALIFIED / WEAKENING in plain language using only contemporaneous evidence?

## FINAL ladder unfinished questions

1. Continuous final UP/DOWN fair probability must remain visible every contract, including PASS states.
2. Determine the safest transition from FINAL WATCH to the protected high-confidence FINAL anchor without weakening the anchor.
3. Validate whether any earlier medium-confidence final tier adds enough coverage/economic value to deserve inclusion.
4. Explicitly model time-left and reversal susceptibility before declaring LOCK.
5. LOCK must be visually distinct from ordinary high confidence and must not be emitted from an uncalibrated flip-risk number.
6. Validate WATCH / EXIT / PROTECT transitions after a final-direction entry when evidence materially deteriorates.
7. Ensure exact Kalshi target/start-price alignment and contract clock remain hard prerequisites for all final states.

## Flip / reversal risk

- Do not display a numeric reversal-risk percentage until a calibrated model passes chronological validation and untouched testing.
- Until then, use validated mechanical warnings / qualitative risk state only.
- No fake precision such as "12% flip risk" from raw heuristics.

## Validation workflow after scalp decision

### Phase A — map current behavior

- replay existing Tier-1 EARLY and protected FINAL anchors on the same chronological contract universe
- verify current accuracy, coverage, ask and timing baselines reproduce
- produce one contract-level ladder timeline showing every state transition
- confirm no look-ahead leakage

### Phase B — offline ladder tournament

Test multiple legitimate extensions simultaneously OFFLINE, including:

- earlier WATCH-only states
- persistence/strengthening telemetry
- weakening/reversal guards
- medium-confidence FINAL candidates
- pullback/re-entry candidates
- state-transition debounce / duplicate suppression

Selection must optimize all four permanent requirements together:

1. accuracy
2. actionable coverage
3. entry price / economic value
4. timing / earliness

### Phase C — chronological validation + untouched holdout

For every candidate ladder extension report:

- EARLY qualified accuracy
- EARLY coverage
- average / median Kalshi ask
- average / median time remaining
- FINAL accuracy
- FINAL coverage
- average / median FINAL time remaining
- false-lock / reversal count
- union actionable coverage after adding validated scalp/reversal
- duplicate-signal rate
- PASS rate and reason distribution

No holdout tuning.

### Phase D — integrated live smoke

Only after an offline winner exists:

- 20–30 minute live smoke test by default
- verify exact contract rollover / target / timer alignment
- verify live Kalshi UP/DOWN prices
- verify ladder states change without UI movement/flicker
- verify no duplicate actionable signal spam
- verify NO ORDERS

Longer confirmation is reserved for the final integrated build, not ordinary iteration.

## Finished dashboard behavior to preserve

For every contract, even without an actionable trade:

- Final Outcome UP/DOWN probability + confidence
- EARLY opportunity state
- live Kalshi UP/DOWN prices
- exact target / BTC distance
- contract time left
- entry guidance with <=50c emphasis, especially ~20–40c when model edge exists
- scalp/reversal opportunity if independently validated
- signal strength / evidence state
- Watch / Protect / Exit guidance after entry
- qualitative reversal/flip warning until numeric risk earns calibration
- explicit LOCK when validated final evidence reaches the lock standard

## Anti-drift acceptance questions

Before any EARLY/FINAL ladder change is promoted, answer YES to all applicable items:

- Is protected FINAL accuracy preserved?
- Is protected Tier-1 EARLY quality preserved?
- Is entry economics preserved or improved?
- Is timing preserved or improved?
- Does actionable coverage improve or remain protected?
- Is any new threshold validated chronologically and on untouched data?
- Is exact target/clock/Kalshi parity preserved?
- Is the system still signal-only with manual execution?

## Immediate handoff after frozen scalp test

1. Judge frozen scalp challenger on >=20 fresh qualified contracts without retuning.
2. Keep or scratch the scalp challenger based on untouched evidence.
3. Reproduce EARLY + FINAL protected-anchor baselines.
4. Build the contract-level ladder timeline scorer.
5. Run the offline EARLY/FINAL ladder tournament.
6. Validate winner chronologically + untouched holdout.
7. Integrate only earned ladder extensions around the protected anchors and validated scalp module.
8. Produce combined full-system scorecard.
9. Run short live integrated smoke.
10. Only then run one longer final confirmation and freeze the finished trading logic.
