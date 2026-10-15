# BTC15 V4 isolated journal adapter checkpoint — 2026-10-15

**Research only — production NO-GO.** Baseline: dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72.

An isolated prototype now exercises the actual V2 SQLite **table layout** (meta/events, zlib-compressed BRTI_CLOSEOUT) in disposable fixtures, with a research-only receipt table and one atomic event/receipt transaction.

**Verified tests: 8/8 PASS** — idempotent repeat, conflicting payload rejection, restart recovery, rollback on receipt failure, matching historical receipt, historical duplicate fail-closed, native sequence interleaving, and signal_only/no orders.

**Not integrated** into deployed RevisionWorker/RevisionJournal. Missing V2 product envelope, administrative pipeline, frozen processor state, real worker concurrency and deployment-identity checks. No copied production journal has been replayed. An exclusive SQLite writer is assumed, not proven in live integration.

**Next gates:** integrate inside one isolated copy of the real V2 worker; reconcile duplicate historical closeouts; test crash/restart/concurrent native decisions and closeouts; validate exact FINAL/EARLY/SCALP replay, source/quote freshness, Kalshi target and clock, 10 isolated rollovers, and CPU profiles.

No Railway, production code, live volumes, models, deployment or orders changed. Research source and tests are retained as separate downloadable artifacts in the conversation.
