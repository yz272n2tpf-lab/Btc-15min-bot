# BTC15 Shadow Diagnostic Pack V1

This folder is a **research-only diagnostic lane** for the BTC / Kalshi 15-minute signal-only project.

It exists to answer one question without weakening the frozen/provisionally locked ladders:

> Can the information we already collect identify a durable direction materially earlier and/or at a cheaper Kalshi ask while preserving the evidence-backed accuracy target and improving useful coverage?

## Safety / change control

- `bot.py` and production ladder logic are **not imported or modified**.
- The V4.7 FINAL anchor and Tier-1 EARLY anchor are replayed as baselines only.
- The script never places orders.
- All output is written under a separate `shadow_diagnostics/output_v1/` directory.
- Exploratory threshold rows are **not** production candidates until they pass chronological validation, untouched holdout, and later live confirmation.
- Official Kalshi settlement truth is required for correctness metrics.

## What V1 builds

### 1. First-fire signal frontier

Sweeps report-only combinations of:

- preferred fair probability
- actual preferred-side Kalshi ask
- absolute BTC distance from the exact target
- distance / recent 5-minute range
- time remaining

Each combination is scored on the **first qualifying snapshot per contract** and reports:

- accuracy
- coverage
- average / median ask
- percent of calls at <=50c
- average / median time remaining

This directly measures the tradeoff we care about instead of blindly lowering a threshold.

### 2. Tier-1 EARLY blocker ledger

Replays the locked Tier-1 requirements:

- ask <=45c
- fair >=75%
- edge >=8 percentage points
- 2-10 minutes left
- absolute target gap >=$25

For every missed contract it records the closest snapshot and the failed gate(s). It also runs a **one-gate-removed rescue audit** so we can see whether one gate is suppressing otherwise-good calls, and what those rescued calls would actually have scored.

### 3. Lead-survival / flip-hazard lane

Builds a causal snapshot of the side currently leading the fixed Kalshi target and asks:

> What is the probability this lead survives to official settlement?

Inputs include, when available:

- time remaining
- absolute and range-normalized target distance
- current Kalshi ask / fair / edge
- 5s / 15s / 30s / 60s / 120s BTC movement
- direct BRTI agreement and target gap
- BRTI vs Coinbase
- Kalshi 15s / 30s lag flags
- quote advantage
- side-stability time / recent target recross
- reversal state
- recent range / volatility

The model uses chronological **train -> validation -> untouched holdout** contract splits. A survival threshold is selected on validation only and then reported once on the untouched holdout.

### 4. Candidate -> Verify transition lane

Creates a broader cheap candidate pool and checks whether short verification windows improve reliability without waiting until the market is already expensive.

Report-only verification windows:

- +15 seconds
- +30 seconds
- +60 seconds

Verification variants progress from simple persistence to fair-value hold, BRTI agreement, and short-horizon momentum confirmation.

## Run

From the repository root:

```bash
python shadow_diagnostics/kalshi_shadow_diagnostic_pack_v1.py \
  --input kalshi_subminute_unified_v1_1.csv \
  --truth fresh_oos_market_manifest.csv \
  --out shadow_diagnostics/output_v1
```

For a settled forward window whose contracts are not already in the local truth file:

```bash
python shadow_diagnostics/kalshi_shadow_diagnostic_pack_v1.py \
  --input kalshi_subminute_unified_v1_1.csv \
  --start 2026-09-14T00:00:00Z \
  --end 2026-09-15T23:59:59Z \
  --fetch-truth \
  --out shadow_diagnostics/output_v1
```

`--fetch-truth` only fills settlement truth for observed contracts. It does not place or modify trades.

## Outputs

- `baseline_anchor_replay_v1.csv`
- `first_fire_frontier_v1.csv`
- `early_blocker_ledger_v1.csv`
- `early_blocker_summary_v1.csv`
- `survival_descriptive_bins_v1.csv`
- `survival_validation_frontier_v1.csv`
- `survival_selected_holdout_v1.csv`
- `survival_snapshot_predictions_v1.csv` when the model runs
- `candidate_verify_transition_v1.csv`
- `shadow_diagnostic_summary_v1.md`
- `run_metadata_v1.json`

## Smoke test

```bash
python -m unittest -v shadow_diagnostics/test_shadow_diagnostic_pack_v1.py
```

The smoke test checks preferred-side snapshot collapse, actual ask handling, exact Tier-1 replay, and blocker identification.

## Decision rule

The pack is designed to prevent us from fooling ourselves with a tiny sample or a late expensive call.

A promising result must improve the **four project requirements together**:

1. accuracy
2. actionable coverage
3. entry price / economic value
4. timing / earliness

If cheaper/earlier rows collapse below the required accuracy on chronological and untouched data, the answer is **not** to keep loosening thresholds. That means the current information is insufficient and the next work should focus on a genuinely new predictive path.
