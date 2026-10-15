# BTC15 EARLY — FINAL bounded prospective evidence (Work handoff)

MISSION: Collect only the NEW postdecision price evidence missing from previous EARLY journal research. One bounded attempt. No full recorder, no repeat of historical analysis, no live code changes.

LIVE FEASIBILITY GATE ALREADY PASSED:
https://github.com/yz272n2tpf-lab/Btc-15min-bot/actions/runs/38679974482
12 offline tests passed; live probes matched 2/3 same-contract EARLY decision/quote pairs and 1 native source+accepted quote strictly later than original decision publication. These tests do NOT establish continuous coverage, fills, net returns, or strategy accuracy.

REUSE THIS BRANCH AND TESTS:
research/early-native-journal-feasibility-20261014
candidates/early_feasibility_20261014/public_probe.py
candidates/early_feasibility_20261014/pair_probe.py
test_btc15_early_native_feasibility.py
test_btc15_early_quote_pair_feasibility.py

EXISTING HTTPS INPUTS — GET ONLY:
https://btc-15min-bot-production.up.railway.app/ladders
    Existing MAIN native EARLY decision view: contract, native decision sequence,
    original decision publication time, observed bid/ask, EARLY side, gate
    decisions and guidance, FINAL context, origin and management.
https://btc-15min-bot-production.up.railway.app/ladders/quotes
    Existing detached same-provider Kalshi price projection: ticker, official
    identity, quote epoch/sid/seq, exchange_ts, accepted_ts, published_ts,
    expires_at and four paired BID/ASK prices. NOT a guaranteed executable fill.
https://btc-15min-bot-production.up.railway.app/ladders/coverage
    Existing source coverage and authoritative official outcomes or PENDING.

PRE-FLIGHT:
Read pinned deployed MAIN release and existing research tests. Do not rebuild
or test the failed 24h recorder, repeat old SQLite extractions, or invent
different evidence. No new market subscriptions, trading API authentication,
source callbacks, hooks, market polling within MAIN, production deployments
or database writes. All recording is on the external Work computer only.

BOUNDED CAPTURE:
- One external GET-only process, no new paid service or background automation.
- Hard total cap 20 minutes, at most one naturally selected full 15-minute
  contract. At most one read per 2 seconds for each of /ladders and
  /ladders/quotes. Request /ladders/coverage only once near finish.
- Save response body with local UTC receipt, HTTP metadata, exact source/
  exchange/accepted/native publication clocks, contract/epoch/sequence and
  SHA256. Hard output cap 20 MiB; no pruning and no overwrite.
- Run 60 seconds first. STOP if NO original EARLY observation plus SAME-contract
  future Kalshi quote with BOTH exchange_ts and accepted_ts strictly later than
  original decision publication. Do not merely compare GET times.
- If smoke passes, continue only within remaining 20-minute cap. Record both
  BUY and PASS; original ASK; gate reasons; following bid/ask observations;
  HOLD/WATCH/PROTECT/EXIT if emitted; contract rollover and all observed gaps;
  FINAL confirmation and authoritative settlement when actually available.
  Do not require a BUY, and mark unmatched or pending outcomes unavailable.
- Detect missing/changed provider epoch, sid/seq gaps, unavailable receipts,
  stale quote leases, duplicated native decision and unmatched ticker.
  A 2-second sampling cadence does not prove every market tick was captured.
- Stop if requests become slow, source becomes unhealthy, or MAIN timing could
  be affected. Do not infer market depth, fills, slippage, fees or profitable
  trades from a displayed ASK/BID.

OUTPUT:
One tested, bounded external observer Python file in isolated research branch;
immutable raw JSONL + SHA256 manifest as Work artifact; concise evidence report
showing decision-to-postdecision-quote joins, availability and coverage, genuine
observed price movements and any verified final settlement. Mark all missing
inputs and exits; a one-contract sample cannot validate changes to EARLY.

VERDICT:
GO to analyze only if actual NEW correct-time same-contract quote trajectories
exist and preserve their original EARLY decisions. Otherwise report exact NO-GO
blocker and STOP — no second framework, collector or unapproved production test.

Production freeze is absolute: no merge, deploy, restart, Railway env change,
volume change, orders, strategy or model tuning, or deletion of existing evidence.
If Work cannot run a controlled external observer or reach the public sources,
stop immediately and report the blocker without asking the user for long
terminal commands.
