# BTC15 MAIN — Incremental closeout receipt-bound research V2

**Date:** 2026-10-15  
**Repository:** `yz272n2tpf-lab/Btc-15min-bot`  
**Exact reviewed MAIN baseline:** `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`  
**Research branch (created, isolated):** `research/main-closeout-incremental-20261015`  
**Production:** FROZEN. **Deployment decision:** **NO-GO**.

## Executive finding — additional correctness blocker discovered

The existing background copier in `btc15_information_native_offpath_candidate.py`, `_cohort_closeout_worker`, calls `btc15_ladder_product_v1.settlement(ticker, row['brti'])`. That legacy function uses its module-global `_worker`, initialized to `None`, and **silently does nothing if `_worker` is unset**. V2's `btc15_v2_product.runtime.native_main()` calls `btc15_v2_product.directional.start()`, which owns a **different module-global `_worker`**, and `btc15_v2_product.directional.settlement()` is the matching V2 function. Thus, on the inspected pinned V2 route, the copier appears to address the legacy, not the running V2 journal worker. A source-level mismatch is proven; missing historical BRTI_CLOSEOUT receipts in the live journal are *not* proven without a read-only journal inspection.

Relevant exact-source paths at the pinned baseline:
- `btc15_information_native_offpath_candidate.py`, closeout worker (~lines 78-140), calls the legacy settlement function.
- `btc15_ladder_product_v1.py`, `start()`/`settlement()` (~lines 273-298), uses its own `_worker` and silent no-op when absent.
- `btc15_v2_product/runtime.py`, `native_main()`, starts `.directional.start()`.
- `btc15_v2_product/directional.py`, `start()`/`settlement()` (~lines 362-388), owns the V2 `_worker`.
- `btc15_v2_product/journal.py`, `RevisionWorker._offer_closeout()`, drains a queued closeout synchronously before returning success. This V2 facility does not make the legacy wrapper's callback a durable acknowledgement.
- `btc15_ladder_journal_v1.py`, `Journal.commit()`, writes a `BRTI_CLOSEOUT` to the SQLite `events` table transactionally; journal retention is up to 30 days or 300,000 records.

**Do not fix by swapping an import in production.** That is not an isolated no-op: it changes which worker receives historical closeouts, and must pass preserved release-hash checks, migration/reconciliation, duplicate proofs and forward timing acceptance before any deployment.

## Changes developed strictly off-production

The V1 scanner (`btc15_cohort_closeout_incremental_research_v1.py`) remains unmodified. This package adds:

1. `btc15_closeout_receipt_guard_research_v2.py` — **read-only** SQLite receipt inspector requiring correct `deployment`, `build`, `product_revision`, lane `main`, event SHA-256, decompressed journal event `schema`, `kind`, `evidence`, `brti_closeout`, safe signal-only fields, and a unique sequence for a contract. Missing or conflicting receipts are never treated as success. It does **not** write to production SQLite.
2. `btc15_cohort_closeout_incremental_research_v2.py` — isolated receipt-gated scanner. Durable `INTENT` precedes the historical cohort append; **only an exact, verifiable V2 SQLite commit** supports a `COMMITTED` audit. If a crash occurs after the commit but before the audit, a fresh process recognizes the exact durable receipt and adds the audit without re-dispatch. If the receipt is missing or inconsistent, the reader stops/quarantines — it does *not* automatically replay an ambiguous action. It validates new/cohort/receipt/audit identity and refuses duplicate cohort closeouts.
3. `test_btc15_closeout_receipt_guard_research_v2.py` — 19 added offline tests using a synthetic WAL SQLite schema and stubbed callbacks. Combined with the preserved V1 tests: **34 tests passed**.
4. `benchmark_btc15_closeout_receipt_guard_research_v2.py` — synthetic reproducible 70k parity + 70k cohort record benchmark (12 polls); no live data and no network.

### Repeatable local evidence

```
python -m unittest -q test_btc15_cohort_closeout_incremental_research_v1.py test_btc15_closeout_receipt_guard_research_v2.py
```

**Result: 34/34 passed** in the isolated temporary filesystem on Python 3.13.

**70k+70k synthetic fixture / 12 polls:**
- Legacy: 3.6162 CPU-seconds and ~187,105,740 modeled bytes read.
- Receipt-gated V2: 0.4450 CPU-seconds and ~15,592,145 actual file bytes read.
- ~8.1x lower process CPU time for this fixture and 12x less file input. This is *not* a whole-service Railway benchmark or validated monthly-bill projection. Receipt checks are rare in this fixture, because none of its rows qualify.

### Remaining **hard production blockers**

1. **Single owner / append atomicity.** The frozen native `cohort_offer()` and the background copier both append to the *same* cohort JSONL file, with no demonstrated shared lock. V2 checks EOF/inode just before append, but a competing writer can begin a partial row *after* that check. A deterministic test demonstrates corruption is possible without a cooperative lock or single writer. **This is not solved.** Consider putting closeout receipts in a dedicated independently owned file/outbox, or establishing a single serialized append owner (requires reviewed integration), instead of assuming `O_APPEND` is sufficient across multiple writes.
2. **Legacy-to-V2 route.** Demonstrate on production journal **read-only** whether `BRTI_CLOSEOUT` events exist. Route any future dispatcher explicitly through the authorized V2 worker, with positive synchronous durable acknowledgement, and verify exact SQLite commit, never a legacy wrapper's `None` or queue-only success.
3. **Ambiguous crash before commit.** If the evidence row was appended but no V2 SQLite event is found, V2 correctly quarantines. A separate deterministic outbox/transactional handoff protocol and reconciliation workflow are required for guaranteed liveness plus exactly-once delivery.
4. **Migration/retention.** Existing historical `CLOSEOUT_ONLY` cohort rows predate the new audit format. Verify and establish a signed/immutable baseline or explicit reconciliation before any activation; SQLite journal events may expire at 30 days/300,000 records. Do not infer that unverified older records imply committed V2 events.
5. **Actual MAIN profiling.** Railway MAIN aggregates native, dashboard, and information children in one service. The identified O(history) scan is independently expensive, but its fraction of the 2.35 vCPU / 2.83 GB 24h average is not measured. Profile each child without violating clock/source publication constraints.
6. **End-to-end acceptance.** Test production-representative snapshots and 10+ live rollovers on explicitly authorized isolated infrastructure, demonstrate exact quote source clocks, Kalshi ticker/target/15m rollover, EARLY <=50c/25-35c opportunities, FINAL/SCALP guidance, calibration and no-orders. Do not merge or deploy without explicit approval, reviewed hashes, signed receipts, rollback plan and performance/cost proof.

## Safety and status

- No GitHub production branch modified.
- No Railway service deployed, restarted, resized, scaled, or removed in this optimization pass.
- 15-service production inventory last checked; MAIN, V81, primary BRTI and read-only cockpit were online at that checkpoint. All seven storage volumes preserved.
- Outstanding unrelated staged MAIN-shadow patch `ead9997e-b5b7-4668-a612-e8417e197838` remains untouched.
- **GO:** isolated code/design research and archival of test results.
- **NO-GO:** integrating or deploying the V2 prototype as-is, claiming settlement exactly-once in production, or claiming the live bot's monthly expense is now under $20.