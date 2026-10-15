# V7 owner-transaction research — executed offline tests (2026-10-15)

**Status:** 10/10 PASS in isolated SQLite fixtures. **Production NO-GO.**

The five tests in `test_btc15_v7_owner_transaction_research.py` were executed locally and passed: idempotent repeat/conflicting payload, restart receipt replay, receipt-trigger transaction rollback, native sequence interleaving, and no-orders boundary.

Five additional isolated tests were executed and passed: matching historical closeout reconciliation, conflicting historical payload rejection, duplicate historical closeout rejection, missing product envelope rejection, and durable receipt replay across restart.

**Important scope:** These tests exercise the published V7 helper against SQLite fixtures with the V2 events/meta column layout. They do not run the deployed `RevisionWorker`, its `ProcessorEnvelope`, administrative pipeline, actual journal state transitions, or native thread/queue lifecycle. No per-process CPU or latency benefit has been proven.

**Next gate:** Implement an isolated copy of the actual V2 worker's single-writer transaction path and demonstrate end-to-end native+closeout event sequencing, replay after commit-before-ack, history reconciliation, product identity/admin behavior, and output equivalence. Do not deploy or alter frozen production components.

No Railway deployments, restarts, variables, volumes, models, or orders were changed.
