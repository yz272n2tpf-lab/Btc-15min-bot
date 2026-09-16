# BTC15 Market-Regime Ledger V1.1 — Semantic Repair

**Mode:** RESEARCH ONLY / DESCRIPTIVE ONLY / NO THRESHOLD SELECTION / NO ORDERS

## Why V1.1 exists

The existing candidate feature builder materializes several causal boolean flags as numeric floats (`1.0` / `0.0`). Market-Regime Ledger V1 reused a legacy parser that recognizes string `"1"`, `"true"`, etc., but not the numeric string representation `"1.0"`.

Result: true numeric flags such as structure, BTC/BRTI agreement and BRTI-primary health were reparsed as false. The causal tag coverage audit detected the contradiction: BTC/BRTI side-aligned movements were populated and positive, while agreement/structure showed 0% true.

## Exact repair

V1.1 changes only boolean interpretation:

- finite numeric `0` / `0.0` -> false
- finite numeric nonzero values, including `1.0` -> true
- native booleans preserved
- textual true/yes/y/t preserved

## What does NOT change

- Trend BTC5 normalized threshold: 0.60
- Trend BTC15 normalized threshold: 0.50
- Acceleration BTC5 normalized threshold: 0.75
- Chop BTC5/BTC15 normalized max: 0.45
- Kalshi-lag absolute 15s ask response max: 0.02
- causal feature set
- primary tag priority
- baseline scalp detector
- serial opportunity lifecycle
- +5c arm / 4c giveback lifecycle
- chronological development / validation / holdout split
- economics accounting

## Holdout handling

V1's holdout was already observed before the representation bug was found. Therefore the repaired V1.1 historical holdout is **descriptive only**. It may demonstrate what the corrected tagger would have labeled, but it cannot select a threshold, promote a regime rule, or be called untouched evidence for a V1.1 trading policy.

Any future regime-aware signal rule must be defined and frozen separately, then tested on contracts arriving after a fresh timestamp cutoff.

## Safety

- historical V1 preserved
- no threshold selection
- no signal suppression or rescue
- no automatic promotion
- no production writes
- no orders
- Coverage Rescue V1 and Economics Forward V1 remain independent/frozen
