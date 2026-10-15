# BTC15 V4 single-writer integration gate — 2026-10-15

**Decision: NO-GO production; isolated tests only.**

The V4 prototype passed 8/8 tests again. Three additional SQLite boundary tests passed: a competing writer's lock is surfaced rather than acknowledged, sequence assignment after an intervening native event remains ordered in the fixture, and the original V2 events schema does not itself prohibit duplicate BRTI_CLOSEOUT records.

**Interpretation:** These tests do NOT prove integration with the deployed RevisionWorker. They demonstrate why the external transaction adapter cannot be safely attached as a second writer. V2's native Journal.commit owns a transaction, sequence, meta state and event insert; RevisionWorker serializes through its queue. The V4 research adapter independently inserts events and meta values, omits the V2 product envelope and admin pipeline, and is not a drop-in implementation.

**Next exact gate:** isolate the real RevisionWorker and frozen processor with copied fixtures; add an in-writer atomic receipt/dedupe mechanism; demonstrate commit/ack crash recovery, historical reconciliation and concurrent native+closeout queue processing without changing the native action path. Then test publication/rollovers and cost profile. Do not modify production or the protected journal until proof.

No Railway service, deployment, volume, trading model or production branch was changed.
