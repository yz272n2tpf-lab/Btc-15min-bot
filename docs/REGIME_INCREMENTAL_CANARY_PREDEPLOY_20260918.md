# REGIME INCREMENTAL CANARY — PREDEPLOY CHECKPOINT

Prepared: 2026-09-18

## Protected live control
Service: scalp-regime-review-v1
Branch: scalp-regime-ledger-v1
Start: python -u shadow_diagnostics/scalp_regime_forward_observation_v1_1.py
Captured baseline: ~2.74 GB avg RAM, ~0.034 avg vCPU, public TX 0 GB.
Live service remains untouched.

## Latest observed control evidence
Future full contracts reached 180 in the captured logs and continued advancing.
Frozen semantics remain descriptive-only, automatic_promotion=false, orders=false.

## Canary branch
regime-incremental-canary-20260918

Static source checks at checkpoint:
- no literal backslash-n artifacts: PASS
- bounded chunk SHA gate: PASS
- strict offset gate: PASS
- manifest byte/hash parity gate: PASS
- POST/PUT/PATCH/DELETE absent: PASS
- orders=false present: PASS

## Required isolated-runtime comparison
At a common source SHA compare source_rows, source_bytes, source_sha256 and all compact Regime outputs. Any mismatch is a STOP. Do not modify protected live control.

## Stage-2 success criterion
A parity-passing transport canary is only Phase 1. Cost success requires bounded state that avoids retaining/reparsing the complete historical tape and produces identical frozen analysis at the same evidence boundary.
