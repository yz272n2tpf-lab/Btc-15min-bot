# BTC15 EARLY — Bounded reader Stage 3 original native journal handoff (2026-10-16)

**Decision: PASS for structural quote+native journal continuity on the *available prefix* of preserved original captures; 24-hour EARLY production campaign still NO-GO.**

No new EARLY validator, quote provider, model, trading signal, or order path was built. Changes were made only on the research branch and isolated Railway research service.

## Engineering completed

- Existing `ops/recording_workflow/evidence.py` `streaming_window_inventory` now accepts optional `quote_handoff` and `native_handoff` readers in one original-record scan.
- `ops/live_recording/quote_window_handoff_research.py` validates exact original Kalshi `QUOTE_BYTES` / `QUOTE_RECEIVE` / `QUOTE_ACCEPT`, ordered exchange snapshot/deltas using the **existing** `btc15_kalshi_quote_provenance_v1.Book`, and preserves book-state fingerprints across bounded windows. No per-record SQLite index or fabricated timestamps.
- `ops/live_recording/native_window_handoff_research.py` validates `NATIVE_RECORD` exact raw SHA-256, original journal ID and contiguous committed sequence, release's emitted native origin/publication identities and literally emitted BUY/HOLD/WATCH/EXIT/SCALP labels across windows. It does not reconstruct missing original orders or trade outcomes.
- An original `EVIDENCE_GAP` quarantines all subsequent quote/native handoff assertions. Full source, official quote, BRTI, external HTTP, terminal settlement, publication/fee and native strategy associations are **not** asserted. `native_early_qualified=false`, `outcome_receipts_verified=false`, `full_early_validation_complete=false` explicitly.
- Audit-only checkpoints carry compact identities and last hashes; **they cannot yet recover worker state after restart**. This still requires the existing `CampaignVerifier` final integration.

## Focused offline CI

- GitHub Actions run [38933400724](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38933400724): **24/24 PASS**.
- Four original recorder burst/hash/seal failures, seven bounded archive/hash/source corruption tests, seven original quote-book state/receipt continuity tests, and six original native journal/identity/literal-label tests.
- Any missing original journal commit, wrong original raw SHA, mutated BUY-origin hash, or original evidence gap fails closed or explicitly marks unqualified.

## Combined immutable Railway evidence run

- Isolated `btc15-early-capacity-test`, service `existing-reader-capacity-probe`, volume `early-probe-scratch` 100,000 MB.
- Deployment `5f25aae2-38a4-4f7d-8bea-733c1c90e6f2` status **SUCCESS**.
- Report persisted on isolated volume:
  `/research-evidence/native_quote_journal_handoff_20261016/RESULTS.json`
- Files source: immutable, copied October 13 original `main`/ `v81` gzip evidence, not a new live recording; no repeat capture or synthetic 600,000 validation.

| Bounded real-sample measurement | MAIN | V81 |
|---|---:|---:|
| Original records structurally scanned | 2,942 | 26,484 |
| Contiguous Kalshi book events before first gap | 165 | 1,091 |
| Original native journal records before first gap | 4 | 8 |
| Native journal IDs represented | 2 | 2 |
| Native records *after first gap* disqualified | 4 | 32 |
| Existing `EVIDENCE_GAP` envelopes | 1 | 83 |
| Explicit V81 SCALP_OBSERVATION prefix records | n/a | 2 |
| Literal native label observed before first V81 gap | none | PASS (1) |
| Authentic BUY origin proven before gap | none | none |
| Audit windows | 3 | 4 |
| Original quote+native audit bytes | 7,316 | 10,335 |
| Runtime wall time | 0.36s | 1.85s |
| Peak process RSS | ~20.4 MiB | ~20.8 MiB |

**Important:** These do not measure an executed 15-minute EARLY contract, valid 24-hour call coverage, accuracy, profitable entry or complete settlement. The original preflight was terminated by producer evidence losses. Even a valid original native journal record is not an independently verified actionable BUY without its original source/quote/metadata/settlement associations.

## Exact next steps

1. Connect original `CampaignVerifier` source/quote/native/outcome *foreign-key* associations to bounded states, with official Kalshi contract interval rather than observed-clock buckets; require all roles, all exact journal ranges and published/settled times. Missing original evidence never passes.
2. Demonstrate persistent bounded quote/native handoff that can resume safely after reader restarts and prove source completeness across time windows. Avoid materializing the 150+ million-record conditional V81 day quote sequence into one SQLite index.
3. Correct MAIN producer `OVERSIZE` and V81 evidence queue overflow in a separately **authorized** finite native preflight; do not loosen original `<=5s` BRTI freshness and no signal model tuning.
4. Recalculate MAIN/V81 producer volume and quote-rate budgets from actual zero-loss capture; 100 GB isolated reader volume cannot compensate for V81 5GB producer volume.
5. Only after all source roles SEALED and the complete reader passes, seek release authorization, activate ~24h authentic day capture and score ~96 Kalshi 15-minute EARLY contracts. No orders.

**Production remains frozen:** no MAIN, V81, BRTI, cockpit deploy/restart or variable changes, existing four staged production changes untouched, seven original production volumes preserved. No Codespaces processing.
