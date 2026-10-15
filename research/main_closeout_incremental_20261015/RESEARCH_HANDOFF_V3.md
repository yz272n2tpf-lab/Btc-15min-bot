# BTC15 MAIN — Isolated crash-recoverable closeout outbox, Research V3

**Date:** October 15, 2026  
**Repository:** `yz272n2tpf-lab/Btc-15min-bot`  
**Exact frozen MAIN reference:** `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`  
**Destination:** `research/main-closeout-incremental-20261015` (research only)  
**Decision:** **GO for isolated design evaluation; NO-GO for merging or deployment**.

## What was accomplished

V1/V2 demonstrate that the deployed `_cohort_closeout_worker` repeatedly scans a growing parity CSV and deployment-specific cohort JSONL. V2 proves a read-only V2 journal receipt can resolve *some* ambiguous crashes, but cannot safely append concurrently with the frozen native producer, and the legacy settlement callback targets a different worker from the active V2 one.

**V3 eliminates the two-writer collision within the research design** by replacing the copier's write to `native-cohort.jsonl` with an independent, SQLite-backed **closeout outbox**. Native's cohort file is never opened for writing by this candidate. An exact legacy-format closeout projection is available for read-only inspection, but *is not integrated* into any live scorer. This is a proposed interface change requiring explicit consumer migration and parity acceptance.

It implements a demonstration of crash-recoverable exactly-once *test-journal* closeout insertion:

1. One **explicit historical cutover**, which records the source inode and fingerprint and indexes preexisting qualifying contract identities. Prior closeouts cannot be silently replayed, including if duplicate source rows arrive after cutover. No production historical reconciliation is claimed.
2. **Incremental parity consumption** of only appended complete CSV rows (bounded per poll), with a durable cursor and unique-contract outbox insert committed **in one SQLite transaction**.
3. **Single outbox poller** enforced by a nonblocking advisory process lock, with per-contract unique constraints and payload conflict checks.
4. **Idempotent offline journal test double**, using a V2-shaped SQLite `events` row, `PRAGMA synchronous=FULL`, `BEGIN IMMEDIATE`, and a unique `BRTI_CLOSEOUT(contract)` index. On replay after crash, it returns the **same committed sequence** rather than inserting again; exact conflicting payloads fail closed.
5. **Receipt verification** against the preserved V2 `DurableReceiptInspector` before acknowledging the outbox. Crash boundaries before outbox commit, after outbox commit, before journal commit, after journal commit, and after outbox acknowledgement are covered in tests.
6. **No concurrent cohort writes**: historical `CLOSEOUT_ONLY` payloads are projected from acknowledged outbox rows read-only, with re-verification of the current journal receipt. No Kalshi calls, model inference, trading orders, source-clock changes, or production writes.

## Files in the isolated research package

- `btc15_closeout_outbox_research_v3.py` — research-only outbox and journal double; explicit runtime guards prevent Railway and `/data` usage.
- `test_btc15_closeout_outbox_research_v3.py` — deterministic V3 unit tests.
- `benchmark_btc15_closeout_outbox_research_v3.py` — synthetic benchmark with an explicit one-time cutover and new eligible events; standalone, temporary files only.
- `VALIDATION_RESULTS_V3.json` — exact local test results, benchmark results and restrictions.
- Earlier V1/V2 research files and reports remain unmodified.

## Offline verification

Run from the research directory:

```bash
python -m unittest -q \
  test_btc15_cohort_closeout_incremental_research_v1.py \
  test_btc15_closeout_receipt_guard_research_v2.py \
  test_btc15_closeout_outbox_research_v3.py
python benchmark_btc15_closeout_outbox_research_v3.py
```

**68 / 68 total tests passed** (15 V1 + 19 V2 + 34 V3). V3 tests independently passed with ResourceWarnings treated as errors; some preexisting V2 tests open SQLite connections without explicit `.close()`, so their combined run can emit warnings but all tests pass. No external feeds or production services were used.

Synthetic benchmark at 70,000 historical parity rows + 70,000 native cohort records, 12 polls:

- Legacy whole-file scan reference: about **3.67 process CPU-seconds** over 12 repeated passes, modeled **187 MB of input read**.
- V3 research outbox: **0.236 s one-time cutover CPU** plus **0.0077 s of steady CPU** over 12 polls, containing two appended eligible closeout test rows (228 bytes consumed) and one noneligible test row.
- V3 left the original synthetic native cohort file unchanged.

**These measurements are workload demonstrations, not an apples-to-apples end-to-end integration benchmark.** The old baseline reprocesses all history while V3 cuts over explicitly. The speedup is *not* a measured live MAIN CPU reduction or Railway invoice saving.

## Production blockers that remain

1. **Active V2 integration is unimplemented.** V3's idempotent journal is an **offline test double**. The real V2 worker (`btc15_v2_product.directional.start()` + `btc15_v2_product.journal.RevisionWorker`) has not been modified; there is no authorized dispatcher route or deployed unique constraint. The legacy callback mismatch remains in production. A read-only inspection of production's actual journal for BRTI_CLOSEOUT events is outstanding.
2. **Native cohort consumer migration is unproven.** A separate closeout outbox avoids competing writes, but any existing consumer relying on `CLOSEOUT_ONLY` rows inside native-cohort JSONL must be inventoried and adapted or given a safe, audited combined view. Do not silently remove historical semantics.
3. **Historical reconciliation and retention.** Pre-cutover records are marked historical, not automatically replayed. The real journal has a 30-day or 300k-event retention policy; retained receipts, duplicates and historically missing closeouts require explicit read-only audit. Do not introduce old receipts into current scoring without approval.
4. **Crash and concurrency validation on the authentic frozen V2 code.** The tests exercise equivalent event schema/receipt checks, but not the native Worker thread, its queue, current authoritative state, concurrent subscribers, or actual Railway volumes. `BEGIN IMMEDIATE` on a test double does not prove the real worker's ordering behavior.
5. **Real feed and model equivalence.** Before any integration, verify official Kalshi ticker/15-minute open-close/target, immutable source timestamps and receipt ages, BRTI/quote freshness, publication-qualified 10+ rollovers, FINAL/EARLY/SCALP parity, timely <=50c and 25–35c entries, exit guidance and strict signal-only behavior. Do not change model thresholds or use offline headline accuracy as production proof.
6. **Measured Railway cost.** No real MAIN per-process CPU attribution, live resource savings, storage archival, or monthly budget compliance is established. Production freeze and existing staged MAIN-shadow change remain untouched.

## Final decision

**Research V3: offline protocol PASS. Production integration: NO-GO.** Preserve the validated research branch; next integration stage requires controlled, reviewed V2 worker idempotence and a native-cohort migration plan, followed by real read-only journal evidence and full acceptance before any production change.
