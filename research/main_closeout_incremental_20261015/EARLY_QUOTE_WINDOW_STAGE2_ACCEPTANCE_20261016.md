# BTC15 EARLY — Existing reader quote-window handoff Stage 2 acceptance (2026-10-16)

**Decision: STAGE 2 PASS for finite, original Kalshi quote replay up to first evidence gap. Authentic 24h campaign remains NO-GO.**

This is engineering the existing `ops/recording_workflow/evidence.py` streaming reader for a bounded `ops/live_recording/reader.py` replacement. It is **not** a new EARLY validator, signal source, strategy, backtest, or campaign. No source freshness, BRTI, target price, or order logic was changed.

## Research-only change and offline results

- `ops/live_recording/quote_window_handoff_research.py`: `QuoteWindowHandoff` retains a bounded cache of original `QUOTE_BYTES` (16 MiB by default), pending exact `QUOTE_RECEIVE` identities, and the pre-existing `btc15_kalshi_quote_provenance_v1.Book` book state. No clock interpolation, fabricated websocket sequence, or synthetic book snapshot. Original request correlation required for snapshot rebases/acknowledgements. Hard fails on raw SHA mismatches, missing original receipt, invalid quote sequence or resource budget exceeded.
- `ops/recording_workflow/evidence.py` now optionally drives this exact quote handoff on original records **after** structural verification and freezes audit hashes on each bounded window transition. No per-record SQLite index is created for this step.
- A checkpoint is an **audit fingerprint**, not a durable restart-resumable book snapshot, verified official contract quote or full native decision association. `checkpoint_is_recoverable=false`; `native_early_qualified=false`.
- Fail-closed: an original `EVIDENCE_GAP` quarantines all following quote-state replay for that campaign, so missing downstream websocket bytes can never acquire valid book state by guesswork.
- GitHub Actions run [38932006886](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38932006886): **18/18 PASS** (4 capture burst and failclosed, 7 bounded archive structure, 7 exact quote handoff). The quote tests exercise exact signed original book state after cross-window acceptance, missing receives, corrupt raw association, invalid exchange sequence, empty/duplicate streams, budget rejection and gaps.
- The first audit test failed solely because it compared a state hash after a stream-end checkpoint (book already intentionally closed); correcting the fixture to force a checkpoint **before** stream closure passed. No safety rule or book parser was relaxed.

## Actual immutable original V81/MAIN research replay on Railway

- Isolated Railway project `btc15-early-capacity-test`, service `existing-reader-capacity-probe`, already resized 100,000 MB volume `early-probe-scratch`.
- Read-only from previously copied original October 13 `main/source.segments` and `v81/source.segments`. Neither production component was queried, changed, restarted or asked to stop in this run.
- Deployment **`f3178b87-2e1a-4646-b162-666a9a316048` status SUCCESS**. Preserved `/research-evidence/native_quote_window_handoff_20261016/RESULTS.json`.

| Verifiable measurement | MAIN | V81 |
|---|---:|---:|
| Original authenticated records structurally scanned | 2,942 | 26,484 |
| Contiguous original Kalshi book events replayed **before first gap** | **165** | **1,091** |
| Exactly verified initial snapshots | 1 | 1 |
| Exactly verified deltas before first gap | 164 | 1,090 |
| Exact original quote receives before first gap | 166 | 1,092 |
| Original `EVIDENCE_GAP` envelopes | **1** | **83** |
| Original downstream quote envelopes quarantined after first gap | 2,134 | 23,022 |
| Window audit checkpoint count | 3 | 4 |
| Window manifests | 4,292 bytes | 6,058 bytes |
| Runtime wall-time | 0.288 sec | 1.717 sec |
| Process max RSS | 22,272 KiB | 22,880 KiB |
| Raw quote cache peak | 53,163 bytes | 319,284 bytes |

- Both sample sessions contained an open quote stream at soft recorder stop; this alone is not an invented market disconnect. The stronger blocker is actual missing original data.
- `original_quote_state_replay='INCOMPLETE_GAP'` for **both**. No complete 15-minute contract or settlement accuracy claim is authorized from these partial sessions.
- Full source time, native FINAL/EARLY/SCALP decision lifecycle, and settlement links are **NOT independently qualified by this stage**.

## Remaining engineering gates

1. Incorporate the original `NATIVE_RECORD` journal/decision, original origin, WATCH/HOLD/PROTECT/EXIT, actual quote receipt, official contract boundaries and outcome acceptance in a bounded, handoff-compatible version of the pre-existing `CampaignVerifier`. Require original foreign-key and chronology joins through recording boundaries; never allow missing receipt to count as strategy evidence. The compact quote windows are not drop-in substitutes for its full SQLite audit.
2. Prove physically bounded growth and resumability of the read/association worker across full 24h quote volumes without dropping any original evidence or fabricating a replay state.
3. Correct original producer-side MAIN `OVERSIZE` and V81 `QUEUE_BYTES` fail-closed admission problems in a **separately authorized** native preflight. Existing research fsync batching is not deployed.
4. Reassess the 5 GB V81 production volume, 20 GB MAIN volume, and the 1.5 million-record/512 MiB day-role quotas for sustained genuine rates, while preserving all historical evidence. A 100 GB detached Railway reader volume does not fix production volumes.
5. After verifying all original roles end gap-free and `SEALED`, obtain production release authorization, activate an authentic ~24h `day` campaign on Railway, and score approximately 96 15-minute contracts for early 25–35c entry opportunities, decision timing, management exits and outcomes. No orders.

**Production freeze respected.** No MAIN, V81, BRTI or cockpit changes; pre-existing four staged changes remain untouched. No Codespaces processing.
