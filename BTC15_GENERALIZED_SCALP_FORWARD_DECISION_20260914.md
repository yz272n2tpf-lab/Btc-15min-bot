# BTC15 Generalized Scalp Forward Decision — 2026-09-14

**Status:** KEEP / LOCK FOR INTEGRATION  
**Mode:** SIGNAL ONLY | NO ORDERS  
**Decision basis:** frozen untouched forward confirmation plus descriptive stability audit. No thresholds were retuned from forward data.

## Frozen challenger — unchanged

- First candidate per contract satisfying all frozen gates.
- `seconds_left >= 120`.
- Side-aligned `btc30 >= $15`.
- No entry-price eligibility filter.
- Management: arm after executable gain reaches +5c, then protect/exit after a 4c giveback from running executable peak.
- One primary qualified challenger signal per contract.
- Signal only. Never place orders.

Freeze timestamp: `2026-09-14T02:24:03.366238Z`.

## Development reference — context only

- Candidate-bearing contracts: 49.
- +10c: 77.6%.
- +20c: 34.7%.
- Managed average: +10.06c.
- Managed median: +10.00c.
- Positive managed exit: 83.7%.

These numbers were development evidence only and were not used to retune the forward challenger.

## Untouched forward scorekeeper — primary decision sample

Exact frozen scorekeeper, after the forward freeze:

- Observed contracts: 43.
- Qualified unique contracts: 40.
- Completed qualified contracts: 40.
- Pre-frozen minimum decision gate: 20.
- Qualified actionable coverage: 93.0%.
- +5c hit rate: 87.5%.
- +10c hit rate: 62.5%.
- +15c hit rate: 47.5%.
- +20c hit rate: 32.5%.
- +30c hit rate: 15.0%.
- Average peak executable move: +16.60c.
- Median peak executable move: +14.00c.
- Median adverse excursion: -1.00c.
- Managed average: +11.23c.
- Managed median: +7.50c.
- Positive managed exit: 77.5%.
- Median time to +5c among hits: 33.0s.
- Median time to +10c among hits: 44.5s.
- Median time to +20c among hits: 101.0s.

Side balance:

- DOWN: n=21, +10=61.9%, +20=28.6%, managed average=+10.00c.
- UP: n=19, +10=63.2%, +20=36.8%, managed average=+12.58c.

## Stability audit — descriptive support, not retuning

The later read-only stability audit contained 41 qualified forward signals because one additional contract completed after the primary scorekeeper run.

Overall:

- n=41.
- +5c: 87.8%.
- +10c: 63.4%.
- +20c: 31.7%.
- Managed average: +10.76c.
- Managed median: +7.00c.
- Positive managed exit: 75.6%.
- Median adverse excursion: -1.00c.

Side stability:

- UP: n=19, +10=63.2%, managed average=+12.58c.
- DOWN: n=22, +10=63.6%, managed average=+9.18c.

Entry timing was positive in all populated slices; the strongest descriptive slice was 5–10 minutes remaining, but no new timing filter is created from this result.

BTC30 intensity slices all retained positive managed average. Price slices are telemetry only and remain forbidden as eligibility filters. The `<20c` bucket contained only two observations and performed poorly; this small descriptive slice does not justify changing the frozen price-agnostic rule.

UTC stability was observed in 00–08Z and 08–16Z. The audit contained no qualified observations in 16–24Z. This missing session is an explicit limitation and may be monitored during later integrated smoke/confirmation, but it is not used to alter the frozen challenger.

## Decision

**KEEP. LOCK THE CURRENT GENERALIZED SCALP CHALLENGER FOR INTEGRATION WITHOUT RETUNING.**

Rationale:

- Forward sample doubled the pre-frozen 20-contract minimum.
- Qualified actionable coverage reached 93.0%.
- +5c behavior remained strong and stable.
- +20c behavior was close to development despite the untouched test.
- Managed average improved versus development, even though +10 hit rate and managed median softened.
- Median adverse excursion remained only -1c.
- UP and DOWN results both retained positive managed performance with similar +10 rates.
- Broad populated time-of-day and momentum slices did not reveal a collapse.

The softer +10 hit rate, lower managed median, and unobserved 16–24Z session are retained as limitations. They are not reasons to move the goalposts after the forward result.

## Integration guardrails

- Do not add an entry-price eligibility filter.
- Do not tighten or loosen `btc30 >= $15` from this forward sample.
- Do not change the `seconds_left >= 120` guard from this forward sample.
- Do not alter +5c arm / 4c giveback management from this forward sample.
- Scalp may disagree with EARLY or FINAL; modules remain independent unless a separately validated handoff rule exists.
- No uncalibrated numeric reversal-risk percentage.
- SIGNAL ONLY. NO ORDERS.
- Protected Tier-1 EARLY and protected FINAL remain unchanged.

Next phase: run the already-frozen EARLY ladder research pipeline, judge its validation and REPORT_ONLY gates exactly as frozen, then integrate only modules that have separately earned their evidence.
