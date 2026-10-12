BTC15 RECORDING WORKFLOW — LOCAL STAGING ONLY

Start: d38e1efc076d8b1ea8cfec0b6ec4d715cf3ea048. No remote publication.
Target source release: 4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c (control-plane metadata;
running file/dependency attestation unavailable). Capture defaults OFF. Every
capture/research output is signal_only=true, orders=false, production_enabled=false,
actionable=false. LIVE mode is rejected. No source connection is opened here.

ONE OPERATOR ENTRY POINT
python -B -m ops.recording_workflow.operator --help
Subcommands: preflight, status, rehearse, finalize, package, retrieve, restore,
make-target, install, rollback, remote-export (always proposal/BLOCKED).
The caller is Work or a later approved service action, not multi-step user editing.
'rehearse --output NEW_DIRECTORY' performs the entire deterministic local workflow.
No timer starts here. Completion.finish is a prepared, idempotent, off-path callback
for an approved future supervisor; it closes capture, indexes, reports, packages,
and emits a small completion/failure receipt on stderr. It is not scheduled.

INTEGRATION AND ISOLATION
Capture.bind_sources binds already-existing BTC getter (or tick seam, exclusively)
and Delivery owner. It binds the existing HTTP getter only at response decode.
Capture.bind_pool wraps only the existing provider factory; bind_provider retains
that provider's exact ws/decoder/session and original proof_writer. The original
proof cache and safety queue remain intact. After validated cache publication,
proof_writer.evidence_sink mirrors immutable proof bytes to an instance of the
existing OffPathProofWriter class acting as a bounded archive drain. This extra
archive-drain thread is necessary because MAIN's scheduler gates on the original
proof queue: putting raw capture/disk operations in that queue would change safety
scheduling. This is an extension of the existing writer, not a second feed or
independent collector. The original proof queue is never bypassed or resized.

InformationCapture is a separate process role using DurablePublisher's existing
worker; it opens no source worker or connection. Main and information share an
explicit configuration hash/run identity and have separate source/information
archive paths, epochs and sequence/hash chains. bind_native_journal_class captures
after the native commit; bind_admin_class adds one post-commit callback in Admin's
existing worker, retaining original serialized rejected/unavailable attempts too.
install_hooks wires object factories locally; it does not start services. It is
an offline staging bootstrap, not an approved production launcher. The native
release/freeze guards remain unchanged; deployment with an overlay requires a
separately reviewed release manifest and compatibility approval.

Close owners first, then capture. close drains with a deadline and restores local
bindings; an unclosed prior session remains incomplete across restart. No append
behind torn data or silent cross-session continuity. Health reads memory and emits
stderr within a nominal 250ms polling interval plus scheduler delay. Failed archive
storage is never its sole health channel. No claim of identical live scheduling.

EVIDENCE AND RETRIEVAL
The original hashed SOURCE/QUOTE_BYTES/QUOTE_RECEIVE/QUOTE_ACCEPT/VECTOR/proof/input
schemas are reused. NATIVE_RECORD adds post-original-commit raw JSON, hash, original
journal/sequence and honest commit/application-clock provenance. It is not proof
of current production archive authenticity. No retrospective wire timestamps,
fee applicability, fills, research BUYs or manual entries are invented.

evidence.index_run streams original segments into a bounded detached SQLite index;
it verifies record hashes, file hashes and session sequences, and records corruption,
missing STOP and evidence gaps. records_for performs a bounded contract/time query
with transitive raw/vector/snapshot dependencies. Contract-owned rows retain their
identities. Underlying sources are independent of contract. Range receipts explicitly
say they are subsets, not whole-session completeness certificates. The original raw
bytes remain in the full evidence package. Oversized retrieval is rejected, not
truncated. Current report reconstruction is bounded at 32MiB; it cannot certify an
entire long session. That future whole-run verification gate remains BLOCKED.

The independent-history adapter excludes recovered observations and later receipts.
It populates the existing corrected history API only; it installs no model/selector,
fits nothing, calculates no opportunity labels and creates no entries. The retained
incompatible continuation artifact still fails its original provenance gate.

PRIVATE LOCAL DELIVERY
Content-addressed files + immutable manifest; resumable .part copies are verified
against the original prefix before resuming. Retries are duplicate-safe. Corrupt
sources, destinations, manifests and unsafe paths are rejected. Clean-reader restore
requires a new directory and verifies every hash before extraction. No source/spool
reclamation is implemented. Only temporary transfer files belonging to this new run
are removed after an atomic verified object commit. No protected archive is deleted.

The primary demonstration is a PRIVATE LOCAL FILESYSTEM adapter, verified from a
separate reader process. It is not a production-to-review route. The existing
connected Railway actions offer metadata/logs but no approved remote filesystem,
SSH, SQLite snapshot or private file retrieval action. No bucket is present. A
historical FAIR JSONL export is not substituted. ChatGPT artifact attachments are
an available fallback for small Work-produced reports/recovery handoffs, not a live
production bulk-evidence transport. No supported production fallback is verified.

BOUNDS
Original default archive: 256MiB; segment <=8MiB compressed; record <=5MiB raw.
Offline staging policy explicitly supports higher TOTAL caps only through a validated
storage policy; default rehearsal retains 256MiB per archive, no pruning. Required
24h+120s+420s and 50% margin are recorded, but qualified_24h remains false.
Source/quote/native archive drain: 16,384 pending items, 32MiB charged admission,
one active item included in byte charge, observation <=4MiB charge, proof <=2MiB.
Original proof queues/caches retain their existing bounds. Information archive has
its own 256MiB cap and existing worker. Vector-object graph <=32MiB; vectors and
inputs <=3MiB. Oversize valid messages yield explicit gaps, not truncation.
One local index <=128MiB, one range <=32MiB, one decoded segment <=64MiB; Python
object overhead is additional. Reporting/indexing are independent of source/strategy.
The policy accounts archive instances, indexes, packages, outage backlog and reserve;
it does not reserve cloud/production capacity or qualify arbitrary native journal
rates. See CAPACITY_PLANNING.json for all-copy and auxiliary-storage estimates.
Planning incremental native recorder RSS <=128MiB and offline reader <=512MiB need
live qualification; these are NOT enforced process-wide limits on the native bot.
No production storage, quotas, retention or configuration is changed.

GATES
Offline mechanical success is not evidence completeness. Reports separately expose
exact source/decision/metadata/native-origin association gaps. Fee applicability
blocks cost-verified conclusions. Fixture rows never become retained actual/live
observations. Historical archive access, prospective capture mechanics, live delivery,
full-duration capacity, dependencies, model readiness and production approval are
separate. Long test remains NO-GO. Stop after this offline handoff.

20261012 OFFLINE FOLLOW-UP
Whole-run verification is now separate from bounded range retrieval:
  python -B -m ops.recording_workflow.operator verify-run --root RUN --index INDEX --output NEW_OUTPUT
  python -B -m ops.recording_workflow.operator finalize --root RUN --output NEW_FINAL --limits OPTIONAL_LIMITS_JSON
The optional limits JSON may only reduce defaults in whole_run.LIMITS.
No full-run data array is created. A new disposable SQLite work database carries
exact dependencies across deterministic decoded-byte partitions. Input segments
are never changed. Ledgers retain original record references and hashes.
Capacity exhaustion is an explicit incomplete result, never silent sampling.
quality.json keeps complete_evidence=false for actual production. The separate
fixture_complete value is derived from every supplied record, declared nonempty
fixture scope, session boundaries, original journal snapshot, source windows,
and applicable lifecycle associations. Unknown schemas/links block the verdict.
Native decisions do not store a consumed information-input hash/anchor ID or
consumed HTTP-response hash. Exact unique source/official tuples and quote
witnesses are checkable; those missing consumed-record links are not claimed.
Nonempty completed-candle vectors lack original candle receipt evidence in this
profile and block fixture completeness. Admin schemas and external settlement
schemas are reported unsupported instead of being ignored or forced to FINAL.
Reports verify stored FINAL/PASS publications independently of entry/EXIT.
No model, strategy reducer, service, collector, scheduler or campaign is started.

Default bounds: input gzip bytes 512 MiB, decoded bytes 512 MiB, 500000 records,
128 MiB combined detached journals, 4096 input files/partitions, 8 MiB partitions, 5 MiB per record, 3 MiB vectors,
32 MiB object-graph limit, 256 MiB disposable verification database, SQLite cache
4 MiB, 128 MiB immutable index, 4 MiB manifest and 16 MiB ledgers, 180 s verifier
wall-time checks. Individual DBs/objects have finite limits; source reads and
SQLite operations are local and expected to terminate. These are offline bounds,
not a measured live-rate/storage qualification. Snapshot reads are local fixture
only; no production filesystem command is enabled.
Range retrieval remains <=32 MiB with explicit record/dependency count limits.
The private local package has a 512 MiB quota including verification ledgers and
detached fixture journal files; restore retains its explicit 2 GiB total ceiling.
Source archive segments/queues and their existing default lifetime caps unchanged.
A run beyond any supported offline bound is INCOMPLETE; larger batch qualification
requires a separately reviewed capacity policy, not an implicit quota increase.
