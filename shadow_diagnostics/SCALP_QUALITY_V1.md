# Scalp Opportunity Quality Frontier V1

Research-only companion to the frozen scalp blueprint forward validator.

## Question
Can candidate-time BTC/BRTI/Kalshi path information improve the raw +10c conversion rate while preserving useful opportunity and contract coverage, affordable entry economics, and early timing?

## Baseline preserved
The scorer first reproduces the current protected serial lifecycle:
- at least 120 seconds remaining
- side-aligned 30-second BTC move at least 15
- no entry-price eligibility filter
- +5c arm
- protected exit after 4c giveback from running executable peak
- reset only after protected exit
- no artificial scalp-count cap

No production threshold is changed.

## Causal feature families
Only information available at the signal moment may enter the model:
- entry ask / spread / maximum possible upside
- seconds remaining
- side-aligned BTC 5s / 15s / 30s momentum
- side-aligned BRTI 5s / 15s momentum
- Kalshi ask movement over 5s / 15s
- acceleration / confirmation / short-range normalization
- BRTI latency / health
- structure and reversal flags
- engineered BTC+BRTI agreement and price-extreme telemetry

Future peak, adverse move, giveback, hit times, settlement result, future bid, and path outcome are labels only and are forbidden as model inputs.

## Validation
Contracts are ordered chronologically and split:
- first 60% DEVELOPMENT
- next 20% VALIDATION
- final 20% untouched HOLDOUT

Model family and probability threshold are selected only on VALIDATION. HOLDOUT is report-only.

A candidate is not allowed to look good solely because it fires a tiny number of times. The validation selector requires a minimum number of signals and contracts before a configuration can be considered.

## Candidate -> Verify economics
The diagnostic also checks 15s / 30s / 45s / 60s verification delays. Each delayed entry uses the **then-current Kalshi ASK** and measures subsequent **executable BID**, so waiting for confirmation cannot inherit the cheaper original entry price by mistake.

## Outputs
- `scalp_quality_opportunities_v1.csv`
- `scalp_quality_price_bands_v1.csv`
- `scalp_quality_validation_frontier_v1.csv`
- `scalp_quality_verify_frontier_v1.csv`
- `scalp_quality_report_v1.json`

## One-command run

```bash
python shadow_diagnostics/scalp_opportunity_quality_frontier_v1.py /data/scalp_move_shadow_v1_events.csv --outdir shadow_quality_out
```

## Promotion rule
This tool never promotes anything. A useful result must still preserve all of:
1. accuracy / executable move conversion,
2. actionable coverage,
3. entry economics,
4. timing,
5. signal-only/manual-execution behavior.

The 93% floor and 95% stretch markers are research targets, not automatic promotion triggers.
