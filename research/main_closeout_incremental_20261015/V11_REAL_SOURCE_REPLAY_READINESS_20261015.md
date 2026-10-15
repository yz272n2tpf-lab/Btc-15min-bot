# BTC15 V11 real-source replay readiness — 2026-10-15

**Decision: NO-GO for production and for claiming real-source equivalence.**

## Verified available evidence
- Research branch `research/main-closeout-incremental-20261015` has V11 outbox/worker tests and historical V3 replay/cutover fixtures.
- GitHub Actions run `38809884834` passed two offline suites: 26/26 synthetic worker and rollover tests, 34/34 V3 historical outbox tests.
- The GitHub Actions runs `38809884834` and `38800651847` have **no downloadable artifacts**.
- GitHub repository contains `fresh_oos_market_manifest.csv` with August 30–31 Kalshi contracts and `completion_audit/fair_candidate_replay_manifest.json` with August research cohort assignments; these are not synchronized October production captures.
- The repository also contains `kalshi_direct_brti_parity_v1.csv` (Git tree reports ~3 MB) and other historical research CSVs. No proof they correspond to the current MAIN deployment's source feed, quote state, and journal identities.
- Railway production environment currently reports 15 services, seven volumes and a pending staged configuration patch. Core MAIN/V81/BRTI/cockpit latest deployment statuses SUCCESS.
- Read-only MAIN delivery logs provide observational source freshness and decision timing, but not a complete synchronized journal+quote+signal replay.

## Required immutable, same-window replay inputs
1. Copy MAIN's *actual* journal SQLite database, plus any WAL/SHM files needed for a transactionally consistent snapshot, without stopping or mutating production.
2. Preserve contract identity, official open/close and target, BRTI source/receipt timestamps, BTC prices, Kalshi quote ticks and quote freshness, native events, FINAL/EARLY/SCALP publications, and durable settlement receipts for the **same 10+ complete consecutive contracts**.
3. Record exact deployment SHA, build, source epochs, capture window, clock timezone, schemas, file SHA256, row counts, gaps and redaction policy. No credentials or private keys in the package.
4. Verify coverage: complete 15-minute windows, 10 consecutive handoffs, clock/target agreement, no missing quote/price/source periods. Treat missing evidence as MISSING, never zero or PASS.
5. Run frozen baseline and V11 optimized replay against identical immutable inputs; compare per-contract event identities, ladder decisions, timestamps, source age, publication lag, error paths and no-orders invariant. Any mismatch is NO-GO pending explanation.
6. Benchmark child CPU/RAM and source-to-publication latency on comparable conditions before claiming savings.

## Access limitation
Current connected Railway actions can inspect service inventory, metrics and logs, but do not expose the bytes of the mounted production volumes or a transactionally consistent journal snapshot. Do not infer an export from service logs or create a fake replay package.

## Allowed next step
Prepare an isolated read-only export/replay workflow, or obtain an authorized consistent snapshot through an appropriate environment. **Do not deploy, restart, modify volumes, change Railway configuration, tune ladders or place orders.**

No production changes performed during this assessment.
