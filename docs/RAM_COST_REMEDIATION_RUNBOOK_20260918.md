# BTC15 RAM COST REMEDIATION RUNBOOK — 2026-09-18

## Scope
Infrastructure-only. Preserve all frozen strategy logic, cutoffs, signal-only behavior, and NO ORDERS.

## Current baseline
- Public scalp export egress: migrated 13/13 to Railway private networking.
- Incremental adapter: scalp-incremental-evidence-v1, read-only, chunked 4 MiB, per-chunk SHA, manifest SHA/byte parity.
- Research lab baseline (producer + adapter + 13 consumers): about 39.5 GB avg RAM and 1.67 avg vCPU in the captured 1h window. This is a noisy engineering baseline, not an invoice.

## Canary
Target: Regime Observation, but NEVER replace the protected live service until isolated parity passes.
Canary branch: regime-incremental-canary-20260918.

Hard gates:
1. Static tests pass.
2. Same frozen cutoff.
3. Incremental reconstructed bytes == adapter manifest bytes.
4. Incremental reconstructed SHA256 == adapter manifest SHA256.
5. Analysis source_rows/source_bytes/source_sha256 match a same-boundary control.
6. Key Regime outputs match control at same source SHA.
7. orders=false, automatic_promotion=false, no threshold selection/suppression.
8. Health passes.
9. Measure RAM/CPU; no broad migration unless evidence parity is exact.
10. On any mismatch: stop; live Regime remains unchanged.

## Stage 2
Transport parity alone is NOT a RAM win. After parity, replace repeated full-tape reconstruction with bounded state keyed by contract / finalized opportunity, while preserving frozen analysis semantics. Validate state output against full recomputation at identical source SHA before promotion.

## Migration order by cost impact / evidence risk
1. Regime isolated canary.
2. Blueprint / Unarmed only after timer-segment semantics are explicitly preserved.
3. Coverage Rescue / Gap Recovery.
4. Nextgen / Watch-Exit / Economics / Density / Pullback.
5. Holdouts last; prefer freeze-and-stop when evidence objective is complete.

## Rollback
Never delete protected evidence. Keep old service/config until replacement parity is proven. Revert transport/state path immediately on mismatch. Record deployment boundary and source SHA. Never concatenate timer segments across restart boundaries as if continuous.

## Cost closeout
After stabilized migration: measure all active service avg RAM/CPU + residual public network. Use Railway billing/usage UI for ACTUAL accrued dollars; metrics-based estimates are projections only.
