# BTC15 V3-to-V2 journal integration assessment — 2026-10-15

**Status: NO-GO production.** Research-only assessment against baseline `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`.

## Verification

- Existing V1–V3 research suite re-run: **68/68 PASS** (some Python ResourceWarnings about unclosed SQLite connections).
- Four new offline structural SQLite contract tests: **4/4 PASS**, total **72/72**.
- Actual V2 `btc15_ladder_journal_v1.Journal` has sequential events and no unique per-contract BRTI_CLOSEOUT index; duplicates are permitted by its schema.
- `btc15_v2_product.journal.RevisionWorker._offer_closeout` waits for durable queue processing but has no persisted closeout idempotency key or caller-visible journal sequence.
- Legacy `btc15_ladder_product_v1.settlement` uses its own `_worker`, whereas V2 starts `btc15_v2_product.directional._worker`; this is a source-code mismatch, not proof of lost live settlements.
- Original closeout path fsyncs a cohort JSONL row and then separately submits settlement; those operations are not atomic.
- V3's unique-closeout journal is a research test double, not the actual V2 journal.

## Required integration gate

1. Inventory BRTI_CLOSEOUT events in an **isolated copy** of the real V2 journal, including duplicate/conflicting payloads and retention gaps. Never mutate live evidence.
2. Implement idempotent check-and-commit within the **single existing V2 journal writer** and same SQLite transaction as native events. Preserve original format/identity protections unless a separately reviewed migration is authorized.
3. Return a durable sequence + digest receipt to the outbox; crash after commit but before ack must recover without a duplicate.
4. Keep native cohort JSONL single-writer; expose closeouts via read-only projection or separately owned durable artifact, not competing appends.
5. Fail closed on historical conflicts, rotation, torn writes, uncertain acknowledgements, disk errors and restart.
6. Run real-worker offline crash/restart/concurrency tests, historical source replay and >=10 isolated rollovers, preserving FINAL/EARLY/SCALP outputs, Kalshi target/clock/source age, publication timing and no-order guarantees.
7. Profile MAIN child CPU/RAM before claiming Railway savings.

No production deployments, restarts, Railway config changes, journal mutations, model changes or orders were performed in this assessment.

**Decision: GO for isolated real-worker adapter engineering; NO-GO for production deployment.**
