BTC15 — PHASE B FINAL VERIFICATION / EARLY LATE ENTRY
2026-10-11 — disposition RESTRICT — no production changes

Scope and identity
------------------
This continuation adds offline diagnostics, acceptance tests and evidence only.
No existing runtime, strategy, model, threshold, dependency or release file is
changed relative to repair c5e2c807343b27aacf04824eca1edb5821ae69d0.
The user-supplied ...ae690 is a transcription error; local/GitHub verification
resolved the existing repair to ...ae69d0. Base Phase B MAIN/cockpit remains
4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c. Actual independent live SCALP source is
6e04aced0f718b29f8ed805abcc0f76b01ed5096, inspected separately in the prior audit.
Branch: audit/btc15-phase-b-final-verification-20261011.

EARLY finding: confirmed missing qualification; incident feasibility unresolved
-------------------------------------------------------------------------------
The 5-cent UP BUY was genuinely issued, not a scan or frontend invention.
Origin: a44143eb2a158a37b1a711006ec2ff45ee273b4a746d30ba6b0e1a45e0a997bf
Contract: KXBTC15M-26OCT111030-30; target 83008.51.
Window: 14:15:00–14:30:00 UTC (10:15–10:30 EDT).
Persisted signal/decision time: 14:29:30.914225 UTC / 10:29:30.914225 EDT.
Time remaining: 29.085775 seconds. Original recorded ASK: 0.05 UP.
Policy: EARLY_CAUSAL_VALUE_V2. Eleven entry qualification flags were true.
MAIN log 14:29:30.933482430: AVAILABLE, sequence 129, event BUY, signal_only=true,
orders=false. At 14:29:32.900888784, sequence 130 is HOLD. Later compact history
is EXPIRED / WATCH / SUPPORT_WEAKENED_OR_MOMENTUM_UNAVAILABLE, with no terminal
EXIT, manual fill or realized profit. The log time is not an independently
recovered journal publication timestamp or quote timestamp.

Exact admission mechanism: btc15_v2_product/early_entry.py assess() compares
seconds_left with the greatest already-observed BTC/BRTI/book source age. This
is a data-delivery check, not evidence that a larger directional move and manual
entry have time to occur. It combines instantaneous spot/BRTI target support,
one-/five-minute trend, FINAL direction, the existing model and cost scenarios.
The value route has no minimum holding horizon. Its model-value calculation
explicitly treats sale at model fair as a scenario, not a predicted future bid.
Yet that scenario plus the other flags is sufficient to issue this entry.

The native frame carries final60 evidence, but assess() ignores accumulated
final60_count/avg/side/complete. The frozen fair-model features include remaining
time, spot distance, momentum/range/volatility, but not this observed settlement
sum. Thus remaining time is not wholly absent from the model; observed-average
conditioning and a supported opportunity horizon are absent from this admission
qualification. The old Tier-1 timer window does not constrain the value route.

New synthetic tests: UP and DOWN both issue BUY at 899, 600, 300, 120, 60, 29.1,
15, 5 and 1.1 seconds remaining with one-second source ages and other qualifying
inputs. At 29.1 seconds, changing the same frame's 30-sample average from 79980
to 80020, around target 80000, leaves BUY and its qualification identical.
These are 18 constructed cases and a paired invariance test, NOT incident/model
replays or evidence that all these conditions occurred together in production.
They establish a repeatable qualification gap across both directions, not a
claim that every late trade is unsuitable or that 29 seconds is always too short.

Settlement-average relevance
----------------------------
For n known one-second observations averaging A and target T, the raw average
required across the other 60-n observations to reach T is (60*T - n*A)/(60-n).
The unobserved set may include delayed past samples as well as future seconds.
It must not be treated as only the wall-clock seconds left. Official rounding,
tie rules, causal sample identity and a future distribution also matter.

Nearby production logs, not the exact BUY frame:
14:29:22: 20/60, average 82991.01 => other 40 need approximately 83017.26.
14:29:53: 52/60, average 83002.06 => other 8 need approximately 83050.44;
latest BRTI was 83013.81, above target but about 36.63 below that hurdle.
14:30:03.291952: complete 60/60 average 83003.59, DOWN.
The preserved official market response is finalized/no with expiration_value
83003.59, matching the local complete average. The nearby logs demonstrate why
latest BRTI above target is inadequate evidence by itself. Their rounded averages
cannot reconstruct the average, forecast or practicality at 14:29:30.914225.
The later DOWN outcome does not retrospectively prove the entry irrational.

Verdict: legitimate larger-directional runway was NOT established by the issued
qualification. A separate EARLY correction is justified. Exact claim that the
incident's UP thesis was impossible or economically invalid remains unproven.

Narrow proposed correction (NOT implemented or deployable)
--------------------------------------------------------
Add an EARLY-only directional-opportunity qualification to admission, preserving
the existing quote, identity, causal, fee, duplicate and lifecycle gates. During
the averaging window, require causal same-contract observed-second evidence and
evaluate the remaining settlement path/hurdle, rather than latest BRTI alone.
Evaluate a meaningful opportunity and execution horizon using validated causal
remaining-path evidence; source age alone cannot certify it. Missing required
evidence must produce WAIT/WATCH with a reason, not an issued BUY. The exact
forecast/qualification needs validation against recovered decision frames before
promotion; the arithmetic helper in this branch is diagnostic only.

Do not veto every final-minute entry, require a completed 60-second window for a
predictive entry, borrow SCALP's existing 120-second new-entry rule, invent a
fixed time/move/probability cutoff, or feed a replacement strike into the frozen
model without validation. Preserve broad EARLY coverage and multiple genuinely
distinct BUY opportunities; BUY -> WATCH (could flip) -> EXIT remains intact.
Do not reclassify this EARLY record as a SCALP trade. FINAL gates remain separate.

Acceptance for a future EARLY patch: test supportive and opposing partial sums,
feasible and unsupported late paths on both sides, missing/out-of-order/duplicate
seconds, exact [close-60, close) alignment, official rounding, delayed evidence,
source freshness, fees, rollover, distinct re-entry and historical identities.
Demonstrate retention of legitimate late opportunities; do not optimize broad
strategy parameters or claim calibrated accuracy from the current diagnostics.

SCALP and price provenance
-------------------------
Origin: 04c02740ab1490770137fc9a53868a5e31b71c56cce6f377b1ef248af4e124c7
Contract KXBTC15M-26OCT111045-45; target 83003.59; 14:30–14:45 UTC.
Recorded BUY: 14:30:45.1683967 UTC; UP ASK 0.60, same-side BID 0.59, spread 0.01.
59 cents is the recorded bid, not a second independently proved entry ask.
Entry features record BTC30 +15.11 and same-side bid30 +0.06; qualification flags
are true. These facts come from preserved compact issued history. They establish
an issued signal and stored inputs, not historical executable depth or a fill.

Actual live-source PROTECT requires a latched observed-bid protective condition:
entry +5 cents arms (65 cents here), and a 4-cent giveback can trigger EXIT.
Merely imagining profitable liquidation does not arm it. HOLD attention, WATCH
pullback and no EXIT can coexist before the giveback threshold is reached.
Recorded terminal: 14:32:12.196363 UTC, observed BID 0.79, ARM5_GIVEBACK4,
CLOSED_RECOMMENDATION. Net one-contract liquidation scenario: gross 19 cents,
entry fee 2, exit fee 2 = 15 cents; after 1-cent reserve = 14 cents.
For a hypothetical 70-cent exit bid: gross 10, fees 4 = 6 cents; reserve leaves 5.
The reported intermediate 70-cent quote and exact PROTECT transition time were
not recovered. Neither calculation proves an available exit, fill or realized
profit; realized_profit remains null, manual_exit_confirmed=false.

New bounded read-only log retrieval covers 14:28–14:33 UTC for both deployments.
MAIN's capped request was supplemented by an overlapping first-44-second query.
SCALP returned 135 rows. These are Railway application logs, NOT full journal
rows. Useful corroboration:
- 14:29:31.289: SCALP old-contract source QUALIFIED, 28.9 seconds left; its own
  existing routes reject new entry with NEW_ENTRY_REQUIRES_120S. This threshold
  is not proposed for EARLY and does not prove EARLY's trade belonged to SCALP.
- 14:30:06.167: SCALP SOURCE_RECOVERED on the 10:45 contract and new target;
  history warms after rollover. No evidence of the 5-cent BUY being relabeled.
- 14:30:53.219: UP qualified near the SCALP entry, not its exact issuing book.
- 14:31:24 and 14:32:10: TIMESTAMPED_QUOTES_UNAVAILABLE, followed by recovery.
- 14:32:12.198375666: qualified live worker near recorded EXIT; this corroborates
  activity, not the entire peak/giveback series or executable 79-cent depth.

Bid/ask code uses UP/YES ask = 1 - DOWN/NO bid, and same-side bid for liquidation.
No proven price inversion or contract swap was found. Complete source epoch,
sid/sequence, exchange/receipt age, decision frame and original publication
timestamp remain missing for the incident entries and intermediate PROTECT.
The nearby EARLY BRTI log has source 14:29:30.000, decision 14:29:30.826327,
age 0.826327 seconds; it is not an exact join to the BUY's quote/feature frame.

Access limitation and next evidence step
---------------------------------------
Connected Railway capabilities expose metadata/logs but not a journal SQL/SSH
reader. Available public endpoints expose compact history/current publications,
not the requested full historical book/journal bodies. No existing authenticated
Codespaces/CLI reader was available. No GitHub browser-authentication loop,
credential extraction, new production endpoint or production restart was used.
Therefore signal-price verification is PARTIAL, not complete.

Next obtain an authorized SELECT-only export of events in [14:28,14:33) UTC
from the two exact deployment journals, restricted to the 10:30/10:45 tickers
plus relevant source-failure records. Verify each compressed body's SHA256 and
join origin, source proof, decision, PROTECT/EXIT and publication timestamps.
read_incident_journal.py supplies a bounded offline extractor (1200-row cap,
262144-byte decompressed-body cap, lane/time/contract guards, hash verification).
It was run only on temporary test databases. Use an already consistent offline
snapshot; mode=ro can still update SQLite shared-memory locking metadata, so it
is not permission to open a live volume under the no-volume-write boundary.
No historical backup campaign or production journal/volume mutation occurred.

Dashboard acceptance
--------------------
Prior repair root causes remain as established: current-only rendering blanked
retained values as short leases changed; chart SVG was rebuilt on updates;
publication floors could be lost across unavailable/invalidate transitions;
explicit EXPIRED records could be projected as current; visibility invalidation
cleared display identity. Existing source outages also occur and remain visible.
The c5e2c8 repair retains timestamped display history without extending authority,
preserves chart nodes and ordering floors, and separates expired/history records.

This continuation tested those SAME runtime bytes in real Chromium 138.0.7204.0:
- Controlled schema-valid stream, 8 scenario groups: normal updates, partial
  replies, expired unchanged replies, visible outage, older reply after outage,
  delayed pre-resume reply, confirmed rollover/history, narrow phone layout.
- 390 rendered normal-refresh frames: zero blank numeric fields, zero SVG root
  or existing path replacements; prices changed 61 -> 62 -> 63 cents.
- Partial/expired/outage replies remove authority while preserving timestamped
  values. Outage reason remains visible. Older/delayed quote responses rejected.
- Historical 5-cent BUY remains labeled historical with no active EARLY marker.
- Width 390 viewport / 390 document, no horizontal overflow; no browser errors.

Live read-only smoke: exact candidate assets on a local host, 40 observations
from 15:34:57.142 to 15:35:16.763 UTC. MAIN, SCALP and quote were eligible in
2, 6 and 17 samples respectively. All captured HTTP responses were 200, while
backend-reported quote/freshness failures correctly removed action authority.
After the first valid value, UP/DOWN price, FINAL probability, BTC and BRTI had
zero blank samples. No browser errors and no non-GET requests.
The original candidate host's direct HTTPS cannot use this workspace's required
outbound proxy; its first local run returned relay failures. A test-only urllib
proxy-aware host enabled the live smoke without altering producer data, clocks,
candidate assets or freshness guards. This transport adjustment is not shipped
as a runtime repair and is not evidence of a production network defect.

Verdict: PASS for controlled Chromium acceptance and limited live smoke.
Not a physical iPad/Safari test or a long-duration uptime claim. Dynamic status
labels can legitimately change as freshness expires; retained values are never
presented as currently executable. Upstream availability was not repaired.

Focused validation and invariant protection
-------------------------------------------
6 new Python tests PASS: admission sweep, average invariance, arithmetic/invalid
inputs, bounded/hash-safe reader, missing/wrong-lane/corrupt failure, committed
WAL visibility. SQLite main/WAL data bytes unchanged in the reader test; shared
memory locks are deliberately not claimed immutable.
6 existing Node suites rerun PASS (including seven named refresh/order tests,
plus history, expiry, re-entry, cold start, source display and rollover checks).
8 real-browser scenario groups PASS. Live smoke as qualified above.
An initial missing NODE_PATH and a checksum invocation from the repository root
were harness invocation errors, corrected without code changes. An early browser
assertion raced an in-flight valid reply; it now compares against the final
accepted observation. Final results above are from the corrected test runs.

46 MAIN release files, 9 MAIN protected files, original frozen identity and all
16 cockpit runtime manifest entries verify. Release manifest SHA256 unchanged:
e8d8a1b54ff9ea3850296567ee8921149e5ea07697144b7bbeb41ea382045949
No runtime diff from c5e2c8; signal_only=true, orders=false. New tests do not
change the existing acceptance of EARLY entries; they document the unresolved
gap. Historical BUY/EXIT projection, multiple distinct EARLY entries, FINAL
thresholds, source freshness and independent SCALP remain unchanged.

Production boundary / disposition
---------------------------------
Read-only environment recheck: unchanged MAIN d6f84479-d722-4139-a96d-6aa155a17dc6,
SCALP 49b01605-2a56-4ff5-b55e-332adf4b5b11,
cockpit 5b326cf3-8998-4fba-854f-8aaad7c60c61. Original MAIN volume remains mounted
at /data. Shadow patch ead9997e-b5b7-4668-a612-e8417e197838 remains STAGED with four
changes and updatedAt 2026-10-08T22:32:38.147Z.
No merges, deployments, restarts, variables/config changes, orders, journal or
volume modifications, or application of unrelated staged changes.

FINAL's reported 83% does not pass its unchanged 90% lock gate; the reported
31.40-dollar spot gap also fails its 50-dollar distance gate. Model settlement
belief, exchange ask and positive entry value remain separate. Exact 83% replay
and live calibration accuracy are still unverified. No lock threshold changed.

Overall: RESTRICT. Recommend restricting reliance on EARLY new-entry guidance
until settlement-aware/horizon qualification is validated. Do not treat the
incident asks or PROTECT/70-cent sample as independently execution-verified.
Cockpit-only presentation repair passes the tested acceptance scope, but this
is not permission to deploy or promote a MAIN/SCALP strategy change. Obtain the
bounded journal evidence, validate the separate EARLY qualification proposal,
then present the exact candidate and test results for production approval.

Evidence index
--------------
verification_results.json: machine-readable tests, synthetic inputs, smoke scope.
CHECKSUMS.sha256: every added source/evidence file except the checksum file itself.
The accompanying external evidence archive contains bounded Railway logs,
before/after metadata, browser screenshots and observations, preserved compact
event/official-market captures and exact changed-file checksums.
Prior audit: audit/phase_b_20261011/evidence.json and test-results.txt.
Official context: https://help.kalshi.com/en/articles/13823838-crypto-markets
https://docs.kalshi.com/getting_started/orderbook_responses
These explain settlement/order-book semantics, not the unavailable incident book.
