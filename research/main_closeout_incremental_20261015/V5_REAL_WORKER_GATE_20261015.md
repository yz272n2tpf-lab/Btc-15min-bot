# V5 journal integration boundary — 2026-10-15

**Status: isolated fixture tests PASS; real-worker integration NOT completed; production NO-GO.**

New five-test research invariant suite checks crash after committed event but before acknowledgement, historical payload conflict, sequence interleaving with native decisions, preexisting duplicate closeouts, and atomic rollback of event+receipt when receipt insert fails. **5/5 PASS** against V4 research transaction adapter. This is not a test of the deployed V2 worker.

## Critical real-worker requirements

The actual `btc15_v2_product.journal.RevisionWorker` uses `_offer_closeout` to queue a tuple `(value,None)` and waits for `_replay_drain`; its return value is only `True`, not a durable sequence/digest receipt. The inherited `Worker.run` owns `Journal.commit` and updates `meta.sequence`, `meta.state`, `meta.latest` and compressed `events`. The `RevisionJournal.commit` additionally inserts V2 product identity and calls the administrative pipeline. The V4 adapter bypasses that processor envelope and is therefore **not safe to install**.

Next implementation must add receipt/dedupe within the **same** existing journal worker's SQLite transaction; it must return the committed seq/digest to the closeout caller without blocking native decisions, preserve product metadata and admin processing, reconcile existing duplicate events, and ensure no other writer can append native-cohort JSONL. It must be tested with a real offline copy of the V2 worker, its original journal and product processor before production consideration.

No production changes, merges, deployments, restarts or model changes authorized or performed.
