# Existing reader: bounded windows and restart continuation

Research only, based on `0cf60fddd910da894d089108d697479306d9e9f5`.
No production configuration, strategy, order, capture activation or 24-hour run.

`ops.recording_workflow.evidence.streaming_window_inventory` remains the archive
iterator. Its optional `WindowedCampaignVerifier` calls the existing
`CampaignVerifier.record`, `native_lifecycle`, `scalp`, `outcome`, information
and proof methods. The original V81 causal consumer and `require_qualified`
are reused with exact SQL-backed maps. The legacy partial handoffs still work.

## Recovery protocol

Each window transaction contains all dependencies, replayed depth, vectors,
sources, original journal ranges and identities, MAIN lifecycle records,
V81 inputs and receipts, settlement acceptances, ledger rows, counters and the
last original file/line/session/sequence/hash. A cursor is advanced only after
the corresponding original envelope is verified and associated.

SQLite uses `journal_mode=DELETE`, `synchronous=EXTRA`, a 4 MiB page cache,
file-backed temporary storage and a hard page quota. Window ledger rows and
the checkpoint commit in the same transaction. There are no external ledger
appends to duplicate or truncate on restart. Export happens after the final
checkpoint; an interrupted export is regenerated from committed SQL rows.
A process lock excludes concurrent writers.

Recovery checks the checkpoint SHA-256, SQLite integrity, SQL schema, code
hashes, source manifest, scope and identical configuration. Per-table counts
and XOR accumulators of SHA-256 over typed row identities/values are verified
by a bounded-memory database scan. Ledgers also have ordered hash chains.
These checks detect accidental and logical corruption; they are not signatures
against an attacker who can rewrite the database and all trust anchors.

After a kill, SQLite rolls back an unfinished window and processing starts at
the last committed cursor. Earlier gzip files are hash checked; the resume
segment's prefix is decompressed to reach its line but is not reassociated.
This is checkpoint continuation, not full input replay. Every input file is
hash checked again before final commit. Changed input/code/configuration is
refused rather than silently migrated. A completed resume is idempotent.

## Retention and limits

Association evidence spills to bounded SQL storage rather than expiring an
exact reference from an LRU. Quote history, old source observations/repeats,
native origins/exits and settlements remain queryable until the run finishes.
Only current expanded vectors remain active; repeated equivalence matches
are scanned rather than collected in unbounded Python lists. Large raw
envelopes are not copied into the raw index, which retains identity/hash only.

The default working database cap is 4 GiB, configurable up to 48 GiB for
offline research. This is a hard failure limit, not a full-day sizing claim.
The default ledger limit is 512 MiB; the window manifest is independently
capped at 256 MiB. Compact state caps include 128 vector names and 512
contracts. Individual original records retain the existing 5 MiB bound and
decoded/object/vector/proof checks. Historical source files are never pruned.
Reserve room for the working DB, rollback journal, temporary SQL work,
exported ledgers and immutable source archives; allocation alone is not free
space. Database growth is measured separately from the fixed memory cache.

Losses permanently quarantine subsequent association credit. Missing origins,
invalid exit BID, missing/stale sources, broken quote sequence, wrong contract,
unverified settlement and absent three-role seals remain failures. A completed
partial archive scan is not EARLY qualification. `long_test` stays `NO_GO`.

## Reproduce offline

```bash
python -B -m unittest research.bounded_reader_recovery_20261016.test_recovery
python -B -m ops.live_recording.windowed_campaign INPUT NEW_OUTPUT --window-records 1000
python -B -m ops.live_recording.windowed_campaign INPUT SAME_OUTPUT --window-records 1000 --resume
```

Run `stress.py OUTPUT source|quote|v81` for the explicitly synthetic retention
workloads. `--preserved-input INPUT` reuses an already generated fixture.
They target 70,000 source observations, 33,000 additional quote states and
8,300 V81 attempts, including a late reference to the oldest retained input
or quote. They do not rebuild or invoke the prior 600,000-record test.

`run_isolated.py` is identity guarded for the one existing Railway research
service. It runs regressions and the preserved MAIN/V81 inputs, kills and
resumes the reader, compares every exported ledger and reads old producer
compression measurements. It never connects to production or mutates it.

## Limits of the result

Process-interruption recovery assumes a persistent filesystem honoring fsync;
host/power-loss and Railway volume replacement need separate qualification.
All exact history remains on disk under a finite quota: large burst projections
can exceed both the reader's cap and the existing research volume. Native
steady rates and database growth must be measured before selecting a day
budget. No claim of complete authentic EARLY lifecycle evidence is possible
from the retained gapped samples. Producer admission queues and the current
in-memory batch are not made durable by this reader change. A producer crash
still invalidates a supposedly loss-free continuous campaign.
