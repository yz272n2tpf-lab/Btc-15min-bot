# BTC15 EARLY — Existing reader V81 exact native causal join Stage 5, 2026-10-16

## Release decision

**PASS for narrowly scoped research-stage V81 original INPUT→SCALP causal associations in offline tests and one real, preserved original pre-gap V81 PASS observation. NO-GO for 24-hour authentic EARLY capture, trade accuracy, profitability or production deployment.**

This modifies only the pre-existing research branch's `ops/recording_workflow/evidence.py` bounded reader and optional `ops/live_recording/*_research.py` handoffs, and reuses exactly the existing production `btc15_kalshi_quote_provenance_v1.Book` and `btc15_v81_qualified_inputs_v1.require_qualified`. It does **not** add any collector, EARLY validator, Kalshi poll, model, order path, strategy threshold, fee assumption or source-age relaxation.

## Stage 5 implementation

- `ops/live_recording/quote_window_handoff_research.py`: bounded cache of exact original accepted Kalshi depth state keyed by **original capture session, WS epoch, ticker, market ID, subscription ID, exchange sequence, exchange timestamp**. Strict original QUOTE_RECEIVE/QUOTE_ACCEPT chronology, displayed bid/ask values, official 900s time span and existing six-second quote-source age. No nearest-neighbor quote, no fabricated rebase/snapshot. Maximum 32,768 distinct retained accepted exchange states; maximum 16 duplicate original accepted receipts for one key; evictions counted and missing exact key fails closed. Old epoch requests are retired only on original STREAM_END.
- `ops/live_recording/v81_window_associations_research.py`: exact original `ORIGINAL_RESPONSE` Coinbase BTC-USD ticker SHA/receipt/price/time, `BRTI_READ` original owner SHA/receipt/source epoch and sequence, accepted `V81_INPUT` original immutable raw SHA and exact `attempt_id`, official Kalshi target/15-minute opening and closing and original accepted quote state. It reuses **exact existing** 5s BRTI / 6s Kalshi / 10s BTC source-age qualification at original row and native publication time. A non-unavailable `SCALP_OBSERVATION` must match that same input provenance and native `product.attempt_id`, exact displayed up/down bid/ask and chronological original journal commitment. A source/recording gap disqualifies following events.
- Original accepted inputs, BRTI owner readings and Coinbase responses are retained in capped caches, with evictions reported. They do not borrow nearest timestamps or silently qualify an evicted input.
- `ops/recording_workflow/evidence.py` invokes this as an optional additional handoff inside its **existing** SHA-256/sequence-verified stream; all prior streaming reader callbacks remain unchanged. Writes every fully matched native association to a bounded (64 MiB) append-only reader-side ledger, with fsync at bounded audit-window transitions and final SHA-256; never truncates silently at the 1,024 in-memory example display limit. No original data is written or removed.
- **Still not done**: full native BUY/EXIT lifecycle and realized/fee-checked P&L, ALL source/quote/proof/settlement cross-role linkage, independently certified 24h source completeness, restart-resumable quote/reader state and V81 producer volume/quote-loss fixes.

## Targeted offline proof

GitHub Actions run [38943091719](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38943091719), research branch `research/main-closeout-incremental-20261015`.

**44/44 PASS:** original recorder batching 4; bounded archive continuity 7; original Kalshi book handoff 7; native journal source handoff 6; exact BTC/BRTI/official market/settlement stage 4 10; original native V81 input + quote + BTC/BRTI + product attempt stage 5 10.

Negative cases include absent Coinbase response, missing BRTI, wrong Kalshi strike, quote-state sequence missing, inconsistent exact quoted price, wrong processing attempt, original source older than 5s BRTI limit and original capture gap, all failing closed.

## Authentic original Railway replay (not new capture)

Isolated `btc15-early-capacity-test`, existing `existing-reader-capacity-probe`, existing isolated `early-probe-scratch` 100,000 MB volume. No production interaction, Codespaces processing or full synthetic data rerun for this stage.

- Verified deployment `afe7f98f-af3e-4fc3-a399-045fed04e376` — **SUCCESS**.
- Research source commit `95d1e0cee8a7866cf6b0d61e9aeb574ac1f47e96`.
- Isolated report: `/research-evidence/native_quote_journal_source_v81_audited_20261016/RESULTS.json`.
- Immutable exact matches persisted: `/research-evidence/native_quote_journal_source_v81_audited_20261016/V81/v81_native_original_associations.jsonl`.
- Audit ledger: **1 complete original native V81 causal input match**, 472 bytes, SHA-256 **`409486bacf7ddf8ecf63226140d3a7c319ad603d59f67c5e9fd869b1d4d2c863`**.
- Its native event: **guidance PASS, no BUY, no fill**, not a settled trade or EARLY directional claim. The recorder's original native SHA was `4cbea6ce238dc7223b759b5ad769209a373ca5a1e0eaef17590c873b5c71418a`; accepted original input SHA `4769fef85b75ba3b7f1f0ae1fd11e223a842442a44f469932715e9504812d5e8`; exact Kalshi quote identity SHA `8bd1e2e4b7b6e706753d79eccf4abf9da77f35c0ff371b280c22eb8510a48174`. These are evidence labels, not price forecasts.
- Original MAIN archive: 2,942 original envelopes, **one** EVIDENCE_GAP; no original complete eligible EARLY BUY. Original V81 archive: 26,484 original envelopes, **83** EVIDENCE_GAP envelopes; all quote/native events beyond its first gap quarantined.
- The original October 13 information role did seal successfully for its 20-minute preflight but MAIN and V81 did not. No full 15m contract/24h cohort is qualified.
- Stage 5 full-day authenticity: **NO-GO**; `original_lifecycle_and_settlement_verified=false`, `full_campaign_verified=false` throughout.

## Remaining release gates (do NOT confuse unit test passing with campaign start)

1. Connect the **existing** `CampaignVerifier` full quote proof/native EARLY origin & WATCH/HOLD/PROTECT/EXIT/settlement associations with independent cross-role verified sources. Stage 5 only checks original V81 provenance/quote/input chain and an exact original native observation; it cannot yet certify final lifecycle.
2. Make the entire reader restart-recoverable and disk-bounded for the 24h **real** quote rate. The window hash audit alone does not reconstruct book state after a crash or guarantee all source retention caches suffice.
3. Resolve MAIN's October 13 unidentified `OVERSIZE` and V81 original queue overflow (1,470 original dropped observations), with separately authorized zero-loss native preflight. Existing research batching PASSED isolated tests but is not yet a released producer change.
4. Reconcile V81 production 5GB volume, MAIN production 20GB volume, their original recording quotas, and Railway isolated 100GB processing volume with real sustained quote ingress. Do not oversell the preflight's short-burst 24h extrapolation. Keep ≤5s source freshness and signal-only.
5. Only after exact native release attestation, all role seals gap-free, adequate retention and reader evidence acceptance: request specific controlled production activation authorization; run an **authentic 24-hour (~96-contract) EARLY campaign** then report early 25–35¢ entry price distribution, timing, rescues/management, authoritative outcomes and failure reasons. No orders.

## Production safety

MAIN, V81, BRTI and cockpit never deployed/restarted/modified in this pass. Seven historical production volumes preserved, four previous staged production changes left unapplied. No production secrets or trade orders handled.
