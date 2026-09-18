# Nextgen body dedup batched V2 — bounded candidate

Base: `7c98f5e54288904534bca6a6cae22eff1823f880`. Isolated branch:
`integrity-sentinel-nextgen-body-dedup-batched-v2`. No deployment authority.

## Scope and invariants

Only newly extracted, deduplicated membership events belonging to one completed
source observation use batching. Telemetry continues using the original
single-row append; scheduling remains 5 seconds / 10 seconds. The single-row
`AppendOnlyHashChainLedger.append` implementation is byte-for-byte unchanged.
No changes to the immutable-body store, source extraction, watchdogs, redirects,
storage thresholds, control attestation, exact-ID rules, strategy or providers.
The membership subclass extends the existing body/provenance verification gate.

Every event remains an individual `STRATEGY_MEMBERSHIP` JSONL row with its exact
record, contract, event ID, record SHA, observation ID, observation row hash and,
when applicable, immutable Nextgen body SHA. No aggregate replaces any event.
The raw Nextgen entity body remains SHA-256 addressed, immutable, and fully
verified using the unchanged V1 body store.

## Batch admission and durability

`append_batch` accepts at most 8,192 rows and 32 MiB of encoded rows. These are
hard admission limits, not chunk-dropping or event-selection rules. An oversized
observation is retained but remains an incomplete obligation and fails health.
No automatic split, retry, fallback or repair is performed. Individual normalized
rows and the final encoded buffer are bounded by the admission checks; peak RSS
also includes the input observation, Python objects and full-history parsing.

One membership batch does the following under one exclusive ledger flock and
one instance lock:

1. Normalize and bound the incoming rows without changing ledger files.
2. Verify the entire existing chain, anchor, pending/durability state, immutable
   body store and prior membership provenance once. Verify that the complete
   incoming batch satisfies the one pending observation's commitment.
3. Compute each sequence, previous hash and record hash sequentially, using the
   exact canonical encoding and hash formula used by individual `append` calls.
4. Durably create the existing uncertainty marker, reserving the old tail and
   final candidate endpoint. Fsync marker and directory before evidence mutation.
5. Publish and fsync the pending (`committed=false`) endpoint anchor and directory.
6. Append encoded rows in bounded 1 MiB writes, checking the unchanged storage
   guard before each chunk. Any short write is an error; it is never retried.
7. Fsync the complete ledger, then publish/fsync the committed final anchor and
   fsync its directory. No committed anchor acknowledges an intermediate prefix.
8. Remove the uncertainty marker only after all durability steps succeed, then
   acknowledge the batch and update in-memory sequence/hash/seen-event state.

This uses seven fsync calls per successful batch, independent of its row count:
marker file+directory, pending anchor file+directory, ledger, committed anchor
file+directory. It does not eliminate any required fsync boundary. Chunk writes
are not independent transactions and do not receive individual acknowledgements.

The existing marker cleanup policy remains: unlink follows the final successful
directory fsync, with no fallible durability operation after unlink. A crash may
resurrect the marker and conservatively block a previously successful append.
An incomplete acknowledgement before cleanup leaves the marker, even when all
rows and the final committed anchor appear complete. POSIX fsync/flock semantics
and honest storage hardware are assumed, as in V1. The transaction's commit
point is successful durability completion and marker cleanup; a caller killed
after that point may not observe the Python return, but the durable transaction
is already complete. This is not an external exactly-once delivery protocol.

## Observation-first, including failures before the batch starts

Simply adding a batch marker is insufficient: the observation may have committed
when a crash, low disk or inode failure prevents creation of that marker.

After event filtering, each new membership observation therefore adds a
`membership_batch` descriptor containing schema, expected new-event count and
SHA-256 of the ordered event-ID list. This is a commitment, not an aggregate
membership record. The observation is committed through the existing single-row
append before any derived membership row is written. Body compaction preserves
this descriptor without changing the received entity bytes or their hash.

`BatchedMembershipLedger` preserves the existing V1 verifier and additionally
checks these obligations. Every declared batch must consist of the exact number
of contiguous individual rows following its observation, with ordered event-ID
digest, exact contract/record identity and observation/body provenance intact.
Extra rows referring to a completed V2 obligation are rejected. Old V1 envelopes
without descriptors remain supported without migration or rewriting.
V2 membership files must be reopened through `BatchedMembershipLedger` (as the
V2 runtime does). A generic core or old V1-only reader does not understand the
additional obligation and is not a sufficient V2 integrity authority.

Only a complete incoming batch satisfying the pending tail obligation can be
admitted by the current live writer. Ordinary verification, single append,
health, and fresh-process startup reject an unfinished obligation. A failed
open sets the existing write-failed latch, so reopening cannot silently finish
it. A partial valid row prefix cannot be adopted or completed. No ledger bytes
or anchors are truncated or repaired. A diagnostic failed open is read-only.

If a generic core batch is rejected before any intent or evidence mutation,
only the previous acknowledged prefix exists, so a fresh generic core open can
accept that unchanged prefix. In the actual membership path, the committed
observation obligation makes the same pre-intent failure persistently unhealthy.
If even the observation cannot be committed, the existing append durability
protocol applies; the batch has not started.

## Complexity and finite history

For retained history H, new batch size B and retained body bytes U, the change
removes B repetitions of verification and checkpoint fsync. Batch work is
O(H + U + B), rather than O(B*H + B²) row work plus B durability transactions.
The row and byte admission limits bound B and temporary batch storage.

H and U are not bounded: full chain verification and every immutable body remain
mandatory on subsequent operations. There is no verification cache, history
cap, retention deletion or archive shortcut. Consequently this change cannot
promise constant time or permanent 5-second cadence for unbounded evidence
history. The measured pre-population tests establish an explicit finite horizon;
the verification report states any observed cadence failure without hiding it.

## Reproduction and safety

The new independent suite uses its own fixtures and SHA/row oracle; it imports
no unit-test helpers or producer code. All fault/crash/concurrency writes use
disposable synthetic directories. Spawned-process reopens verify no mutation.
The measurement harness uses the exact failed V1 `synthetic_audit(192)` fixture:
1,634,996 bytes, 3,072 initial events, all seven synthetic sources, body changes
once per six membership observations, unchanged 5/10-second scheduling.

Commands and complete metrics are in the V2 verification report and results JSON.
No real evidence, cutoffs, certification, Railway, production, strategy, orders
or trading is part of this work. Health retains `orders=false` and
`certifiable_evidence=false`.
