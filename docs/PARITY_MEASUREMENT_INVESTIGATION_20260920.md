# BTC15 dashboard-canary parity investigation — 2026-09-20

**Recommendation: PARITY VALIDATOR NEEDS CORRECTION.**

The validator has reproducible measurement defects. The retrieved FAIL lines do not demonstrate a BRTI transport or same-contract Kalshi clock/target defect. They also cannot certify that every individual historical FAIL was harmless: the source CSV records and historical gateway ticks required to reconstruct each comparison were not available through the exposed read-only Railway tools.

The correction described below is a local, unpushed candidate. No deployment, merge, main change, credential retrieval, trading action, strategy/model/probability/threshold retuning, or bot data-path change was performed.

## Repository and evidence boundary

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Branch only: `brti-websocket-dashboard-canary-20260919`.
- Audited remote/deployed base: `a4ff2b6e47971cb33ea9dc4a8ad317cf257a2bec`.
- Railway service: `brti-websocket-dashboard-canary-temp`.
- Deployment: `45535442-76fa-4f5e-8e3e-ee47eb0d165b`, reported `SUCCESS`; created 2026-09-20 06:29:24 UTC.
- A separate checkout of this exact remote base was used. The previous `be54dd3...` commit and original data-isolation patch were not changed.
- Runtime logs were retrieved read-only, filtered to parity, DIRECT BRTI heartbeats and FINALIZED messages. No Railway variables or credentials were fetched.
- Supplied earlier observations (zero tracebacks/file errors/real HTTP 429s) were not treated as a fresh, exhaustive audit of every runtime log.

The larger retrieved parity window spans **10:50:34.397751107–12:56:29.208666044 UTC**, with 501 observations:

| Result | Count |
| --- | ---: |
| PASS | 328 |
| FAIL: BRTI only | 104 |
| FAIL: QUOTES only | 43 |
| FAIL: QUOTES and BRTI | 13 |
| WAIT | 13 |

Thus there are 160 FAILs, including 117 BRTI-tagged and 56 QUOTES-tagged cases. This expands the user's smaller 109 PASS / 46 FAIL window; it is not a contradiction or a full deployment-wide failure rate.

All 488 PASS/FAIL rows display **clock Δ0.0s and target Δ$0.00**; none has a CLOCK/TARGET failure tag. Values are rounded in console output. Six WAIT rows show a cross-contract rollover comparison, often clock Δ900s; seven other WAIT lines report no active contract. These WAITs do not establish a same-contract clock error.

Five BRTI-tagged FAILs have a displayed dollar delta at or below $2. Their printed timing is below 6s; side disagreement is therefore implicated by the code, but the exact underlying side values are not in stdout. Two QUOTES-tagged FAILs print 6.0c: console rounding and binary floating-point boundary effects can hide an underlying value slightly above 0.06. Raw CSV values are needed to distinguish these cases.

Largest displayed differences in the scored sample: BRTI $39.04 and quotes 56.1c. The printed BRTI `@` range is 0.0–0.9s. These are measurements with the flawed synchronization described below, not established same-publication errors.

Additional retrieved evidence: 101 DIRECT BRTI heartbeats (12:09:22–13:01:13 UTC) all report ready True, with displayed age 0.9–1.7s; 22 FINALIZED messages (07:00:10–13:00:02 UTC) report 60/60 and complete True. The filtered PARITY WARNING request returned no entries. These observations support continuity, but do not independently qualify the upstream feed or reconstruct every FAIL.

## End-to-end selection and timing at the audited base

| Stage | Actual selection | Timestamp meaning |
| --- | --- | --- |
| Main bot market selection | REST GET `/trade-api/v2/markets`, open `KXBTC15M`; require `open_time <= now < close_time`, choose earliest close | Evaluated after the response |
| Main bot quotes | `yes_bid_dollars`, `yes_ask_dollars`, `no_bid_dollars`, `no_ask_dollars` from that market response | Unified `timestamp_utc` is the local collector timestamp assigned after market retrieval; no exchange quote event time/sequence is logged |
| Main bot target | `floor_strike`, then `functional_strike`, textual exact-target patterns, then exact-market fallback | Fixed contract target; not a rolling BTC reference |
| Main bot BRTI | Poll shared WebSocket gateway state every second; retain `(true publication timestamp, value)` in the thread's buffer | Adapter preserves `source_ts_ms`; `/state` validates readiness/connection/index/safety metadata and source age 0–5s |
| Main bot snapshot | Market response, local `now`, then BTC request and other work, then latest buffered BRTI | The attached BRTI can be from a different publication time than local `now`; its actual age is checked when read |
| Main bot logs | Direct-BRTI CSV includes `timestamp_utc`, `contract`, `target`, `direct_brti`, **`brti_timestamp_utc`**, `brti_age_seconds`, `direct_brti_ready`, `brti_side`, `brti_gap_to_target` | Collector and publication clocks are both available |
| Unified rows | UP and DOWN rows share the exact collector timestamp, contract and snapshot BRTI; quote fields are side-specific | No independent exchange quote timestamp/sequence; BRTI source time must be joined from direct-BRTI CSV |
| Parity market request | Separate REST request at each audit, same open-contract selection, target lookup from numeric fields | A different observation from the bot's earlier market response |
| Parity unified selection | Latest collector timestamp; reconstruct quote sides from same-contract rows within ±2s | It can accept a partial newest frame or borrow a nearby side |
| Parity reference BRTI | Gateway `/ticks`; choose publication **nearest the unified collector timestamp** | Not necessarily the publication actually consumed by the bot |
| Parity bot BRTI | Direct-BRTI log record nearest that collector timestamp | Ignores `brti_timestamp_utc`; does not filter contract or require ready/fresh |
| Parity comparison | Maximum quote difference, BRTI price difference, raw side equality; contract/clock/target checks | Several different notions of time are combined as if they identified one observation |

The main loop runs approximately every 5s and the parity process sleeps 15s **after** each audit. Network and processing time add to those intervals; the loops are not synchronized.

At base, parity's `age` is calculated before the gateway history fetch. It is the age of the CSV's collector timestamp, not the age of the reference quote, not BRTI source freshness, and not a quote-to-quote sampling gap.

Base source locations: main bot `get_active_market` around line 1989; BRTI poller/snapshot/logger around 2143–2276; main loop acquisition and logging around 3783–3915. Parity snapshot selection and joins around 235–293, and audit arithmetic around 305–393. These line references refer to the audited base, not the candidate.

## BRTI FAIL root causes

### Proven timestamp mismatch

The base validator chooses gateway tick `R` nearest collector time `T`. It chooses bot log row `L` nearest `T`, then compares the row's BRTI value from true publication `B`. It never uses `B` to select the reference tick.

Its printed time difference is:

`max(abs(R - T), abs(L.collector_time - T))`

It is **not** `abs(R - B)` and is **not** BRTI freshness. The bot log normally shares `T`, making its contribution zero. A small displayed `@ 0.4s` can coexist with a multi-second difference between the two actual BRTI publications.

Deterministic reproduction using the exact baseline functions, with synthetic values:

| Item | Timestamp | BRTI |
| --- | --- | ---: |
| Bot's actual publication | 12:00:03.000 UTC | $100,000 |
| Bot collector timestamp | 12:00:05.400 UTC | — |
| Reference selected by old parity | 12:00:05.000 UTC | $100,008 |

The old validator reports **FAIL, BRTI Δ$8.00 @ 0.4s**, even though the reference history also contains the bot's exact 12:00:03 publication at $100,000. The true tick separation is 2s. The correction selects that same publication and reports BRTI delta $0.

A live $3–$8 difference can therefore reflect market movement between distinct publications. The console alone does not prove the actual lag or distinguish movement from a genuine value discrepancy in that individual observation. The correct test is the same-publication comparison.

### Side comparisons and extra join defects

- Even a price delta below $2 fails if raw sides differ. A synthetic move from $100,000.10 to $99,999.90 across a $100,000 target produces a 20-cent BRTI difference and old FAIL. This is unrelated to the bot's ±$11 WAIT action rule, which is unchanged.
- `nearest_logged_brti` does not filter the contract. During rollover, the main bot can append a finalized old-contract record and the new-contract record with the same collector timestamp. The old function picks the first nearest record; its side/target may belong to the old contract. This is a validator join defect, not a Kalshi selection change. The scenario was reproduced; attribution to individual live lines is unavailable.
- The real log field is `brti_gap_to_target`; the old gap alias list omits it and reconstructs the gap from the reference target. This obscures which target the logged side used.
- Raw `FLAT` is valid in the main bot at exact equality. The old validator strips FLAT and maps reference equality to UP, guaranteeing a validator failure for an exactly equal price/target.

### Proven blind spots (not claims of observed transport failures)

The old validator ignores the logged `brti_age_seconds` and `direct_brti_ready`. A synthetic 5.5s-old/not-ready point receives old PASS when the reference matches and other values agree. The bot's actual 5s guard still exists; the validator is failing to measure it.

A nonempty gateway `/ticks` history bypasses parity's `read_shared_brti` qualification check. `/ticks` checks response/safety metadata but does not establish current connection/PRIMARY_OK/freshness. Historical ticks are legitimate for historical comparison, but must not be used as proof that the current gateway is healthy.

## QUOTES FAIL root cause

The validator compares four bot quote fields from an earlier market response against the four fields in a separate, later parity REST response. It computes the maximum finite absolute difference and fails above 0.06, while merely requiring the collector timestamp to be no older than 6s and at least two quote fields to be comparable.

A 10c delta means at least one corresponding bid/ask moved by $0.10 per contract between the values read. It does not mean BTC moved $10, and it does not by itself prove a quote-feed defect. Neither quote input is associated with a shared exchange observation timestamp/sequence in the current CSV schema. There is no implemented guarantee that prices cannot move more than 6c between those requests.

The exact baseline functions reproduce a QUOTES FAIL for otherwise coherent quote sets separated by 10c. This proves the test conflates asynchronous movement with correctness; it does not prove the cause of each historical 10c/11c/56.1c observation.

The 2s UP/DOWN reconstruction window and acceptance of only two finite fields are additional measurement weaknesses. UP/DOWN already share an exact collector timestamp at the producer, so the validator should use that exact frame and never fall back to a previous side while the newest frame is being appended.

## Exact base thresholds and appropriateness

All numerical constants below are retained in the local candidate; none was widened or retuned.

| Check at current deployed base | Exact rule | Technical assessment |
| --- | --- | --- |
| Source age | `age <= 12.0s`; no lower bound | Useful collector-liveness limit, not a synchronization guarantee. Future timestamps were not rejected. |
| Quote eligibility | `age <= 6.0s` and at least 2 finite quote differences | Not sufficient to identify one quote observation. It also limits overall PASS/FAIL age to 6s despite the nominal 12s source limit. |
| Contract | Unified ticker equals currently active API ticker | Genuine identity prerequisite. Rollover disagreement should be WAIT, not a cross-contract price comparison. |
| Clock | `abs(logged_seconds_left - (API_close - collector_timestamp)) <= 10.0s` | Genuine fixed-contract time invariant; 10s is a broad existing allowance, not evidence of 10s actual drift. Normal logged rounding should be much smaller. |
| Target | `abs((btc_price - btc_gap) - API_target) <= $1.00` | Genuine fixed-target invariant. Exact matching target data should agree nearly exactly; $1 is a permissive existing allowance. |
| Quotes | Maximum finite bid/ask difference `<= 0.06` (6c) | Invalid as a strict correctness test on unmatched requests. Retain as descriptive drift threshold, not evidence of failure. |
| BRTI time | Maximum of reference-publication-to-collector offset and bot-log-collector-to-collector offset `<= 6.0s` | Wrong quantity for same-publication parity; it does not measure the gap between BRTI values. Exact publication matching supersedes it. |
| BRTI value | Absolute difference `<= $2.00` | Cannot establish correctness on different ticks. On an exact publication it becomes a real discrepancy check, though this same-feed path should normally agree to representation precision. Existing $2 allowance retained, not newly endorsed as a source accuracy guarantee. |
| BRTI side | Bot side is UP/DOWN and exactly equals reference side; reference equality maps UP | Invalid for distinct ticks near the target; also inconsistent with producer FLAT. Compare the same publication against one target. |
| Unified side join | Same contract and timestamp within ±2.0s of newest | Too permissive for a producer that uses the exact same timestamp for both sides. Exact-frame join supersedes it. |
| Bot source freshness | Gateway `/state` rejects negative or >5000ms source age; bot readiness max 5.0s | Genuine fail-closed invariant. Preserved; parity now checks readiness rather than inferring it from comparison timing. |
| Parity readiness at base | PRIMARY_OK and age <=5 only on point/fallback paths; nonempty `/ticks` skips this check | Incomplete measurement of live gateway health. Candidate qualifies current state before using historical ticks. |

Base overall status is PASS only if its scorable prerequisites and every clock/target/quote/BRTI test pass; otherwise it is FAIL when scorable, WAIT when not. A small BRTI dollar delta can still FAIL because side equality is separate. A FAIL frequency from these rules is not a transport error rate.

## Should time matching be corrected?

**BRTI: yes, and the needed metadata already exists.** Join direct-BRTI and unified records by exact collector timestamp plus contract, then match the gateway history at the logged `brti_timestamp_utc`. Missing or ambiguous history is unknown, not permission to use a nearby tick. Require freshness/readiness when the bot used that point and independently require qualified current gateway state. A historical matched point may be more than 5s old by the later audit; that does not retroactively make it stale when consumed.

**Quotes: proper matching requires additional provenance.** Existing stdout/CSV data cannot reconstruct two requests' exchange observation identities. Record both request start/end times and, where actually available and semantically suitable, a quote event timestamp/sequence. An identity/sequence shared by both observations would support a correctness comparison. Merely narrowing the collector-age limit or assuming overlapping request intervals proves equality would still be incorrect. If exact independent matching is unavailable, report quote drift and quote parity as unverified. Do not substitute comparison of the bot's own copied CSVs as independent Kalshi parity.

No additional quote-source fields were invented, and no bot logging/strategy/schema changes were made in this candidate. Consequently it is a correction to measurement honesty and BRTI matching, **not a completed new quote-qualification system**.

## Local candidate and exact files

| File | Change |
| --- | --- |
| `btc15_kalshi_parity_shadow_v1.py` | Exact contract/frame BRTI join; true-publication reference matching; actual gap field and FLAT semantics; current gateway qualification before historical tick use; recorded freshness/readiness checks; reject future collector/publication timestamps; exact UP/DOWN frame reconstruction; record quote-request times and BRTI publication times in existing notes; separate quote drift from correctness; preserve existing CSV columns/paths and all numeric thresholds. |
| `test_btc15_dashboard_parity_ws_static.py` | Extend existing preflight gate to require publication/frame/contract matching, live qualification before tick history, freshness checks and explicit unverified quote classification. |
| `test_btc15_parity_measurement_regressions.py` | 22 focused offline regression tests using actual parity source functions with deterministic I/O fixtures. |
| `docs/PARITY_MEASUREMENT_INVESTIGATION_20260920.md` | This investigation, evidence scope, thresholds, correction limits and recommendation. |

Operational consequences of the candidate, deliberately explicit:

- It does **not** produce full overall PASS with the current quote schema. If checked components agree but quote provenance is missing, overall status is WAIT and notes include `QUOTES_ASYNC_UNVERIFIED` and, where applicable, `BRTI_PUBLICATION_MATCH`.
- A proven same-publication BRTI value/side discrepancy or checked clock/target mismatch stays FAIL even when quote parity is unknown. `row_scorable=False` describes incomplete full-parity coverage; inspect component flags and notes for the reason for FAIL.
- Quote deltas remain in the existing output columns and stdout. A recent >6c difference is labeled `QUOTE_ASYNC_DRIFT`; even a zero delta is not promoted into matched quote proof.
- Unknown quote/BRTI matches are blank in CSV, rather than falsely claiming a mismatch or match. BRTI publication/timing evidence is added to the existing notes column, so no old CSV header or data file needs migration.
- Current gateway qualification adds one existing-adapter `/state` GET per shared-mode audit before `/ticks`; it does not add a direct Kalshi BRTI HTTP request or alter the WebSocket gateway/client/adapter.
- The 6s nearest-time and 2s side-join constants remain for audit history but no longer authorize mixing distinct observations. Exact identity is used instead.
- A local candidate does not change the running canary. This candidate has not been tested against newly captured live source records.

## Verification

All requested existing gates passed:

1. `test_btc15_dashboard_ws_canary_static.py`
2. `test_btc15_dashboard_ws_runner_static.py`
3. `test_btc15_dashboard_parity_ws_static.py`
4. `test_btc15_brti_ws_gateway_client_v1_static.py`
5. `test_btc15_brti_ws_adapter_compat_static.py`
6. `test_brti_main_cutover_static_gate_v1.py`
7. `test_btc15_canary_data_path_static.py`

Also passed:

- 22 new parity regression tests: false $8 cross-tick failure removed; actual same-tick $8 failure retained; $2 boundary unchanged; cross-target asynchronous sides; FLAT; wrong-contract/finalization joins; missing/duplicate frames; stale, future and invalid ages; no nearest-tick substitution; ambiguous reference publications; incomplete quote sides; zero/10c quote differences remain unverified; genuine clock/target discrepancies remain visible; qualified history versus current readiness; no shared-mode direct HTTP fallback; output schema compatibility and timing evidence.
- Existing 11 data-path regression tests.
- Syntax compilation for every modified/new Python file (3).
- AST comparisons confirm unchanged numeric tolerances, polling interval, CSV field list, data-root bindings, Kalshi market selection, target lookup, quote fetching, authentication and CSV writer.
- Final diff restricted to the four files listed above; main bot, shared BRTI consumer, gateway client, rescue/protection, runners, data-path helper and V13/V8.1 installer/presentation remain untouched.
- `git diff --check`.

Tests run without network, credentials, live bot startup or order access. The local interpreter lacked `requests`, so focused tests compile the actual source function/constant AST and explicitly replace I/O boundaries; they do not import the live runtime module. This validates measurement behavior, not a full dependency-installed production boot. The existing static gates do not require that dependency. There is no claim of a new live gateway qualification or deployment.

## Recommendation

**PARITY VALIDATOR NEEDS CORRECTION.** The existing FAIL labels are not sufficient evidence of real BRTI transport or same-contract Kalshi alignment failure. The concrete timestamp/join/readiness defects are proven and reproduced; asynchronous market movement is a plausible cause of individual value/quote deltas, not an assertion that every historical line has been exonerated.

Do not freeze the entire infrastructure solely from uptime, matching rounded clock/target output, or this corrected offline test suite. Preserve the previously qualified WebSocket architecture, review the local measurement candidate, and use a separately authorized isolated canary run to capture exact BRTI publication matches and explicit quote-provenance gaps. No strategy changes or wider tolerances are warranted by this investigation.
