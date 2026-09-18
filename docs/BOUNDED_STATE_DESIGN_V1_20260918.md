# BTC15 BOUNDED STATE DESIGN V1 — RAM REMEDIATION

## Goal
Stop each forward/review service from retaining and reparsing ~350+ MB raw CSV into multi-GB Python object graphs every poll, while preserving exact frozen research semantics.

## State boundary
Persist only:
1. CSV header/schema fingerprint.
2. Last committed byte offset and source generation.
3. Per-contract raw rows for contracts that are not yet final/fully observed.
4. Immutable finalized-contract summaries sufficient for the frozen analyzer.
5. Frozen cutoff and experiment identity.
6. Source boundary SHA/byte count plus deployment segment ID.

Never mutate finalized historical contract state except by fail-closed rebuild from canonical source.

## Ingestion
- Request bounded deltas from scalp-incremental-evidence-v1.
- Verify X-Start-Offset == committed offset.
- Verify X-Chunk-SHA256.
- Parse only complete newline-terminated records.
- Group new records by contract.
- Commit offset only after state update succeeds.
- Generation mismatch => STOP / canonical rebuild; never splice generations.

## Finalization
A contract may leave hot raw-row memory only after the same existing full-observation rule used by the frozen analyzer proves it complete. Until then all rows for that contract remain hot.

## Equivalence proof
For identical source boundary:
- full reference analysis and bounded-state analysis must match source identity;
- denominator contract IDs/count;
- serial opportunity IDs/count;
- opportunity-index membership;
- regime tags / primary regime;
- protected exit counts;
- compact metrics and evidence readiness.
Floating metrics compare at deterministic serialization precision; discrete IDs/counts must match exactly.

## Memory target
Hot memory scales with open/recent contracts and finalized compact state, not total historical event rows. Target first canary steady RAM <= 0.75 GB; stretch <= 0.35 GB. No migration solely to hit RAM target if parity fails.

## Checkpoint format
Atomic JSON/SQLite-like durable checkpoint is preferred in next implementation. It must include schema version, cutoff, generation, offset, source boundary, finalized state digest, open-contract rows digest, and orders=false.

## Recovery
On restart load checkpoint, validate schema/cutoff/generation, request from committed offset, and continue. If validation fails, rebuild from canonical private source in a separate evidence segment and record the boundary.

## Scope
Infrastructure/evidence representation only. No threshold changes, no signal suppression/rescue, no auto-promotion, NO ORDERS.
