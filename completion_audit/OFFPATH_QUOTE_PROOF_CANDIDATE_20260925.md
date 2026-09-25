# Off-path quote-proof candidate — 2026-09-25

Status: PREPARED, NOT QUALIFIED, NOT DEPLOYED. SIGNAL ONLY / NO ORDERS.

## Proven blocker addressed
The prior Work qualification measured at least 8.33 ms to serialize a valid ~1.31 MB quote proof synchronously inside the native quote-consumption path. A timestamped counterexample changed BRTI qualification from ready to stale solely because of that added delay. The draft capture was therefore rejected before deployment.

## Candidate correction
This branch preserves the frozen production source and adds a separate candidate module. The candidate removes JSON serialization and disk I/O from Provider.consume(). The native path validates the current book, obtains the same quote, freezes a small witness (ticker, source frame, owner epoch, consumption time, market id, sid, seq, exchange timestamp, contract close), takes a tuple of already-received event references, performs a nonblocking bounded enqueue, and returns.

A daemon worker later serializes the full proof, independently replays it, verifies the exact witness identity and quote state, content-addresses the accepted bytes with SHA-256, and only then publishes a small latest-proof index. Queue overflow or worker failure loses evidence only; it must never block or alter strategy evaluation.

## Safety properties intentionally retained
Sequence gaps/out-of-order/conflicting duplicates invalidate the book; exact duplicates do not refresh timestamps; snapshots do not invent exchange timestamps; stale/future/cross-contract/cross-market evidence fails; reconnect requires a new snapshot; proof publication fails closed on identity mismatch.

## Qualification still required before any runtime use
1. Run the existing frozen suite plus the new focused candidate tests.
2. Benchmark the native consume() path with capture enabled/disabled using large valid proofs. Demonstrate no material shift in BRTI qualification or native outputs/state.
3. Adversarially test queue-full, slow worker, worker crash, event mutation, rollover, reconnect, source-owner restart, late/missing witnesses, and 1-us boundaries.
4. Bind the candidate's actual build identity separately from frozen PR36 strategy identity using the already-required versioned manifest.
5. Confirm bounded disk retention/cleanup for content-addressed blobs before a long run.
6. Only after those gates pass may a controlled passive-capture deployment/restart be considered.

No production file, Railway service, model, threshold, two-clock candidate, or order path was changed by preparing this branch.
