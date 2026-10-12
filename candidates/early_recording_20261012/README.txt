BTC15 EARLY EVIDENCE RECORDING - ISOLATED OFFLINE CANDIDATE

Authority: bounded archive verification, isolated recorder development and offline tests only.
Production frozen. signal_only=true; orders=false; production_enabled=false; actionable=false.
No installation/startup entrypoint is supplied. Imports do not start workers or network clients.

SOURCE AND STORAGE FLOW
BTC get_btc_spot (or alternative pre-gate _ec_append_btc_tick) -> Observer -> immutable scalar observation.
Delivery.accept/fail/remember -> same Observer -> original receipt / failure / recovered-availability events.
Existing PreparedProvider.session, same ws.recv and Evidence.accept -> immutable received bytes and acceptance
receipts -> same existing OffPathProofWriter queue. The original decoder, refresh/subscription calls,
accepted-clock publication and native witness construction survive unchanged.
Existing DurablePublisher.offer -> same immutable input bytes and publication result -> Archive on its existing information worker.
Existing kalshi_get JSON decode -> whitelisted original public market/series response bytes and local receipt.
OffPathProofWriter archive mode -> Archive codec -> existing CompressedJournal -> exclusive bounded gzip segments.
Offline read_archive/reconstruct/quote_chain/source_association/associate -> mechanical evidence and associations.
Nothing reads capture results back into a strategy. There is no order, polling, subscription, scoring or model API.

EXPLICIT FUTURE BINDING CONTRACT (NOT EXECUTED OR AUTHORIZED HERE)
A separately reviewed integration may construct ONE extended existing OffPathProofWriter with an Archive
outside protected storage, explicit evidence_class and verified source_binding. Use a pure replay validator;
PreparedProvider._validate_proof also writes a legacy file and is NOT suitable as this archive's validator.
Bind the existing source objects via Observer only after feed/epoch identities are verified. Select bind_btc
OR bind_btc_tick. Bind the already-existing provider, not a new Provider constructor or connection. Its proof
submissions and receive observations use that same writer. Bind the existing HTTP getter before Preparation
and FeeCache retain it. Supply evidence_archive to the existing DurablePublisher; it writes from its already
separate information worker and creates no additional recorder thread. No extra HTTP invocation is introduced.
This package does not modify runtime.py, release manifests, launchers, configuration or protected source files.
Live source/information producers run in different processes today. Their archive instances require distinct
paths/locks and explicit source binding. This offline candidate does NOT implement a cross-process installer
or claim one shared in-memory queue spans those processes. Each existing worker owns its own archive.

EVIDENCE SCHEMA
Each envelope: BTC15_OBSERVATION_EVIDENCE_V1, evidence_class FIXTURE or NATIVE_CAPTURE, session, sequence,
previous_sha256, kind, payload, sha256, and the four frozen safety flags. sha256 commits canonical JSON without
its own sha256 field. Sequence/hash chaining is per session; no continuity is presumed across sessions.
START records source binding and limits; STOP marks orderly closure. Every restart starts new segments.

SOURCE: asset, feed, epoch, epoch_basis, value, source_ts, receipt_ts, original_receipt_ts, available_at,
basis ORIGINAL/RECOVERED, accepted_by_owner, publication_id, observation_id and receipt_basis.
Identifiers are derived content hashes, not invented exchange-issued IDs. BTC epoch is explicitly a capture
process epoch, not an upstream exchange epoch. BRTI epoch is the original Delivery owner epoch. A source value
has no contract owner; history crosses rollover without transferring quote/target/origin ownership.
SOURCE_REPEAT compactly retains additional receipt times by reference to the original observation; it does
not refresh the publication's first receipt. source_events expands repeats losslessly. Exact duplicate records
are deduplicated within a bounded 4096-key cache; later eviction may repeat a record but never deletes evidence.
RECOVERED records retain first recovery availability and original_receipt_ts=null. They are never original
receipts and are excluded from available_sources by default. Native source joins use exact value/source/receipt,
BRTI epoch and original decision cutoff. Missing/ambiguous joins remain missing; later BRTI cannot be borrowed.
SOURCE_GAP reports start/epoch boundaries, clock regression, conflict, invalid chronology, >15s source gaps,
primary failures and capture problems. These are evidence diagnostics, not new strategy gates.

QUOTE_BYTES retains exact ws.recv-return bytes (base64 + SHA256), without headers/credentials.
QUOTE_RECEIVE binds bytes to ticker/epoch, application recv-return wall time and monotonic clock. Kernel/wire
receipt is explicitly unknown. QUOTE_ACCEPT is after the unchanged Evidence.accept, with the same raw hash.
Snapshot/delta/ack stream IDs, sequence numbers, prices and fixed-point quantities remain in the original bytes.
Offline replay uses the existing Book decoder, reports missing snapshots/updates and disconnects, and derives
same-side bid/ask depth with USD-per-contract prices and contract quantities. Displayed depth is never a fill.
QUOTE_PROOF links the full original native witness to the original legacy proof byte hash. Exact event JSON
member order is retained, so reconstructed proof bytes must hash identically. proof_receipts additionally
requires every proof event to equal an original received/accepted event, and acceptance must precede consumption.
Consumer consumed_ms/source_time never becomes an original receive timestamp.

VECTOR stores bounded trim/append changes to overlapping BTC ticks, completed bars and quote-event arrays.
INFORMATION_INPUT stores the remaining skeleton, input hash, decision cutoff, later information capture cutoff,
publication result and frame_id. Reassembly must reproduce canonical input bytes exactly. Input-copied history
is labeled as an input copy, never promoted to original source-event receipts. Failure records preserve failed
publication attempts; malformed/unreplayable inputs retain their raw hash/bytes and an explicit failure.

HTTP_BYTES retains exact existing public response body; HTTP_RESPONSE links endpoint, local receipt after JSON
decode, raw hash, official ticker/open/close/floor-strike/rules fields or observed series fee fields. Endpoint
whitelist excludes account/portfolio/order data. No credential values are read or retained. Missing formula,
rounding, effective periods and applicable scope stay null. Native target/window validation remains separate.

The offline continuation association ledger retains every supplied SETUP/CONFIRMATION/TICKET/CANCELLATION/
EXPIRY event, including unmatched events, with explicit fixture/native-research class and content hash. FINAL,
MANAGEMENT and EXIT associations require original contract/window/target/side/origin plus original event-time
and detached snapshot/journal/sequence/hash references. It does not itself authenticate an archive or calculate
performance. No current origin-to-FINAL chain was verified. Hypothetical size/contracts, reaction seconds,
reserve and assumption identity are explicit. No fee applicability, confirmation, fill or realized profit is inferred.

RESOURCE AND FAILURE CONTRACT
Suggested isolated instance: queue 64 pending items plus one active item, 8 MiB charged capacity (including active work), 4 MiB maximum
admitted observation charge, maximum 32 fields and 1024-character non-raw string fields. Proof admissions charge
the pre-existing 2 MiB proof ceiling. Strings conservatively charge four bytes/character, so large messages can
be rejected before the nominal websocket maximum; that is an explicit evidence gap, not truncated evidence.
Vectors: <=8192 rows, <=3 MiB serialized each; retained vector graph <=32 MiB (sys.getsizeof traversal).
Each journal record <=5 MiB raw; gzip segment <=8 MiB; total archive <=256 MiB. At quota or failure, capture
fails closed and stops; NO automatic deletion, age pruning, rotation-overwrite, production retention change,
source backpressure or strategy veto. A single pre-existing worker performs serialization, hashing, replay,
compression, fsync and all archive I/O. Nonblocking admission drops on capacity/lock contention.
Incremental recorder RSS planning gate: 128 MiB/active instance. This is NOT an OS-enforced memory limit or live
qualification; queue/cache/record budgets are enforced and small synthetic allocations were measured.
A hung worker exhausts its bounded queue; shutdown timeout reports incomplete closure. Startup is exclusive.
Overflow summaries are flushed by the worker even when idle, with thread-safe counters. Disk-full/fsync/short-
write failures produce worker status/diagnostic and an unclosed session; a broken disk cannot guarantee its own
durable gap marker. Restart always creates new segments and declares a boundary. Corrupt segments are reported
and excluded; original bytes are never repaired, skipped as complete coverage, pruned or overwritten.
read_archive caps compressed input at 256 MiB and decoded bytes at 256 MiB (override downward for narrow reads);
it is an offline reader, not a decision component. No live CPU, filesystem contention or latency SLA is claimed.

REPRODUCTION
From the independently recovered repository:
  PYTHONDONTWRITEBYTECODE=1 python3 audit/early_recording_20261012/run_tests.py
  PYTHONDONTWRITEBYTECODE=1 python3 audit/early_recording_20261012/resource_probe.py
The test gate blocks sockets and candidate fitting/calibration. All new stream fixtures are synthetic.
Never run legacy studies, model fitting, service launchers or installation commands as part of this handoff.
Historical index incident and all prior negative findings remain preserved and unresolved.
