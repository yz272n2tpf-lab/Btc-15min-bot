# BTC15 MAIN — Incremental Cohort Closeout Research V1

**Date:** October 15, 2026  
**Baseline:** `yz272n2tpf-lab/Btc-15min-bot` at `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72`  
**Status:** **ISOLATED OFFLINE PROTOTYPE / NO-GO PRODUCTION**

## Scope and safety

- This candidate does **not** modify `btc15_information_native_offpath_candidate.py`, production release manifests, pinned model data, Kalshi sources, quotes, clocks, trading ladders, or strategy thresholds.
- No Railway service was created, deployed, restarted, retuned, or scaled; no orders are placed. Existing service and volume data are untouched.
- The new Python module is research-only and is **not imported by the production launcher**. It is intended to replace a separate, expensive evidence closeout loop only after a rigorous future acceptance phase.
- Existing MAIN shadow staged config patch `ead9997e-b5b7-4668-a612-e8417e197838` is unrelated and must not be applied.

## Root cause confirmed in pinned source

`btc15_information_native_offpath_candidate._cohort_closeout_worker` rereads the **whole** `/data/kalshi_direct_brti_parity_v1.csv` (roughly 126.8 MB in the investigation) into a Python list, reparses the active deployment's `native-cohort.jsonl` to rebuild its existing `CLOSEOUT_ONLY` set, scans all parity rows, and repeats after **one second**. This is a confirmed algorithmic inefficiency; its specific contribution to aggregate Railway CPU is unmeasured without per-process profiling.

The root `/data/btc15_cohort_native_v1.jsonl` archive is **not** the current deployment's cohort path. `btc15_v2_product.release.verify_environment` configures a deployment-specific JSONL path. Do not confuse the two.

## Candidate implementation

`btc15_cohort_closeout_incremental_research_v1.py` implements:

1. One bounded-memory streaming bootstrap pass over parity CSV and cohort JSONL.
2. Incremental reads of **only newly appended complete records** on subsequent polls, with fixed header validation, `st_dev/st_ino` checks, prefix fingerprint and truncation detection.
3. Exactly the same `CLOSEOUT_ONLY` JSONL keys, values, sorted-key serialization, eligibility, and callback arguments as the original for eligible, well-formed evidence.
4. A separate experimental `INTENT` / `ENQUEUED` audit file to detect ambiguous crash windows and fail closed instead of automatically issuing a potentially duplicate settlement.
5. No HTTP, no model inference, no orders, no cadence/clock substitutions, no deletion and no imported production code.

### Important limitation: no exactly-once downstream settlement guarantee

The original implementation appends/fsyncs a cohort row, and then separately calls `btc15_ladder_product_v1.settlement()`, which offers an asynchronous event to a downstream worker. There is **no atomic transaction** between the append and the eventual durable settlement. The new audit file identifies an ambiguous restart window but **cannot prove** whether a callback was durably committed. It deliberately quarantines such a restart. Production integration is **NO-GO** until downstream durable acknowledgement/idempotency and concurrent-writer semantics are accepted.

In-place parity truncation or rotation is also deliberately fail-closed; automatic recovery could skip qualifying evidence. Explicit verified reconciliation is required before promotion.

## Validation executed locally (not in Railway)

Executed in a fresh temporary directory on Python 3.13:

```bash
python -m unittest -v test_btc15_cohort_closeout_incremental_research_v1.py
```

**15/15 tests passed.** Coverage includes healthy-event differential bytes and callback equivalence, `final60_complete`/count/side validation, late completion, rollover, duplicates, restart reconstruction, partial parity and cohort records, native non-closeout tailing, file overwrite/replacement/truncation, audit partial trailer, and crashes before cohort append, after append before settlement and after callback before audit acknowledgement. Unsafe crash boundaries are detected and quarantined, not claimed to be solved.

### Two synthetic-fixture benchmarks (12 polls each)

| Fixture (parity + cohort) | Old scan CPU | Incremental CPU | Old total bytes read | Incremental bytes read | Old peak RSS | New peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| 70k + 70k rows, 15.6 MB | 3.6386 s | 0.4259 s | 187.1 MB | 15.6 MB | 219 MB | 99 MB |
| 150k + 150k rows, 33.5 MB | 7.7709 s | 0.9068 s | 401.7 MB | 33.5 MB | 357 MB | 99 MB |

This establishes ~8.5x lower **offline per-process CPU time** over 12 scans and ~12x lower bytes read. Peak RSS includes fixture creation and Python runtime in both modes; it does not isolate the production process RAM. The number of polls controls the ratio, and neither benchmark is an estimate of overall Railway CPU savings.

## Remaining before any production consideration

- Verify downstream settlement **durable** acknowledgement and idempotence without changing protected journal format, and correctly reconcile ambiguous audits.
- Run deterministic simultaneous native JSONL writer and closeout writer tests; prove no partial/overlapping lines, data loss, or duplicate events.
- Test real representative parity/cohort snapshots without altering the originals; verify historical fully qualified rows, original settlement receipts and exact closeout emission order.
- CPU profile actual MAIN child processes (native vs dashboard vs information) without adding production load or reducing native freshness/1Hz scheduling.
- Validate full frozen replay equivalence across MAIN/V81/FINAL/EARLY/SCALP and published UI; source ages, official contract target/clock, quote freshness, publication latency and no-order behavior must remain unchanged.
- Keep Railway production freeze. A separate explicit deployment authorization, reviewed release hashes, rollback plan and at least ten live 15-minute rollovers would be required for production GO.

**Decision: GO for isolated research work and code review; NO-GO for production deployment or affordability claims.**
