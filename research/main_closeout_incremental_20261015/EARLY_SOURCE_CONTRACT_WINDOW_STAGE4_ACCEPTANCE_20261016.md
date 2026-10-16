# BTC15 EARLY — bounded reader Stage 4 causal source/contract/settlement handoff (2026-10-16)

**Decision: PASS as a bounded research-stage prerequisite on authentic preserved October 13 evidence; NOT A PASS for any entire 15-minute EARLY contract or the requested 24-hour live campaign. Production release remains NO-GO.**

## What changed (research branch only)

- `ops/live_recording/source_contract_window_handoff_research.py` adds an **optional causal handoff inside the existing `ops/recording_workflow/evidence.py` streaming reader**. No quote provider, new input polling, strategy reducer, forecast, backtest, order path or fresh source is created.
- It verifies original `SOURCE` and `SOURCE_REPEAT` SHA-256 fields, basis, owner acceptance, exact original source/receipt/availability clocks, original publication IDs and the source-repeat's first original receipt. Indexed exact source lookups are key-based and never search for a nearest neighbor timestamp.
- It checks `HTTP_BYTES` SHA-256, the original `HTTP_RESPONSE` official market projection, exact `ticker`, `open_time`, `close_time`, `floor_strike` and receipt prior to a native decision's feature cutoff. The exact **900-second official interval** is required; observed quote clock buckets are never substituted as contract identity.
- For a recorded non-unavailable MAIN `NATIVE_DECISION`, it matches exact accepted original BTC and BRTI source receipts plus official target tuple at the original native feature cutoff. These local exact matches are **not** full `frame_links`: independent quote proof, V81 qualified input, information and complete native lifecycle still require original `CampaignVerifier`.
- For official `SETTLEMENT`, it verifies original `OUTCOME_ACCEPTANCE` SHA and chronologically accepted `ORIGINAL_RESPONSE` SHA and calls existing `btc15_ladder_settlement_v2.receipt` to reproduce the official outcome; pending/unavailable never becomes an authoritative result. The original `CLOSEOUT_ACCEPTANCE` causality and 60-second BRTI guard are retained without inference.
- Any input SHA mismatch, original market mismatch, unseen source, future HTTP response, bad source chronology, missing source repeat identity, cache-cap exhaustion or original source/evidence gap fails closed (or quarantines downstream evidence).
- Bounded source/HTTP/metadata maps enforce resource ceilings; **these are not yet an independently qualified 24-hour memory budget**. Checkpoint hashes do not make the quote/native state restart-recoverable.
- `ops/recording_workflow/evidence.py` now accepts `source_handoff` in the same original-record structural scan, in addition to the existing quote/native state handoffs. The original full reader remains the required final authority.

## Verified offline regression

- GitHub Actions run [38938778633](https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38938778633), research commit `67b887dc71cb584b49b0d92b9ea91649f0f0fef3`, **34/34 PASS**.
- Subgroups: recorder batching/strict gaps 4; bounded structural inventory 7; original quote handoff 7; original native journal handoff 6; exact source/market/settlement handoff 10.
- Negative tests include missing BRTI, future BTC receipt, wrong Kalshi target, future official settlement HTTP receipt, altered original raw bytes, missing original source sequence and input retention exhaustion.
- One early test expected a different strict cache-cap error; it was corrected to accept either of the two valid fail-closed source-cap reasons. Limits were **not** weakened.

## Verified authentic October 13 artifacts on isolated Railway

- Project `btc15-early-capacity-test`, existing service `existing-reader-capacity-probe`, existing volume `early-probe-scratch` (100,000 MB).
- Deployment **`923913cd-5dc4-496a-ba89-1a23cf592782` SUCCESS**, using `research/main_closeout_incremental_20261015/run_native_source_contract_handoff_on_railway.py`.
- Results persisted **only on isolated research volume**: `/research-evidence/native_quote_journal_source_handoff_20261016/RESULTS.json`.
- Inputs: previously copied, hash-verified, incomplete original October 13 `MAIN` and `V81` evidence. No production SSH, live data fetch, recorder start/stop or dataset reproduction was executed for this stage.

| Metric (only before first recording gap can be checked causally) | MAIN | V81 |
|---|---:|---:|
| Original archive envelopes scanned structurally | 2,942 | 26,484 |
| Verified exact original SOURCE receipts | 3 reported SOURCE, **2 accepted-original tuples** | **0 accepted-original tuples** |
| Official market receipts located | **0** | **1** |
| Complete independently linked MAIN BUYs and outcomes | **0** | n/a |
| Authoritative settlement joins | **0** | **0** |
| Original Kalshi book events before gap | 165 | 1,091 |
| Original native journal records before gap | 4 | 8 |
| Original EVIDENCE_GAP envelopes | **1** | **83** |
| Bounded reader output bytes | 9,360 | 13,066 |
| Worker wall time | 0.283s | 1.885s |
| Maximum process RSS observed across roles | ~24 MiB | ~24 MiB |

- All three handoffs ran without structural failure and did **not** synthesize accepted BTC/BRTI sources or market receipts that were absent.
- MAIN's October 13 source-prefix contained **no complete official market receipt** before its original gap. V81's pre-gap sample contained one official target but no accepted SOURCE tuple. These short records cannot prove an actionable EARLY decision.
- Both sessions remain **quarantined after their first original EVIDENCE_GAP**, and no entire real 15-minute contract was verified. 34 offline passing fixtures do not compensate for actual producer-side missing data.
- No claim of 24-hour EARLY coverage, 25–35c entry viability, settled profitability, ≥85% executed trade accuracy or 93–95% final outcome accuracy is supported.

## Remaining release-blocking work

1. Exact link of the existing verified quote-state and source/metadata handoffs to every `CampaignVerifier` native frame and V81 input; prove cross-contract state, after-window publication and all authoritative outcome associations with whole-session continuity.
2. Durable and bounded independent reader checkpoint/restart semantics and predictable day-wide resource use; the current compact audit hashes are **not resumable state** and cannot replace entire per-record dependency joins.
3. On producer: resolve MAIN unknown `OVERSIZE` observation; resolve V81 queue/throughput evidence loss with the already tested research batching and a separately authorized zero-loss native preflight. Retain unchanged ≤5s source-age discipline.
4. Producer volumes: MAIN 20GB and V81 5GB cannot be presumed sufficient. The separate 100GB reader volume does not increase producer storage; no producer resize/deploy/restart is authorized in this checkpoint.
5. Only after all roles SEALED with zero gaps and end-to-end reader authority proven, explicitly authorize new day campaign, run 24 hours and evaluate approximately 96 Kalshi BTC15 contracts using original entry prices, call timing, exit management and authoritative outcomes.

**Production invariant:** MAIN, V81, BRTI and cockpit remain online and frozen; all seven producer historical volumes preserved; the pre-existing four staged production changes remain untouched. No orders, no model thresholds altered, no Codespaces processing.
