# Clean collector: complete the approved source/storage cutover

Rollback: deployment a8237852-34c3-44bc-9f90-34ee3755684e, source f59276fd4733bbc374be53aaa4bb8063ed0f81ab. The new volume is mounted at /data. The pre-cutover path-summary at19:34UTC reports the configured relative event file does not exist. Mounting storage alone did not migrate its paths or source transport. Preserve that observation, not a claim of recorded trades.

The historical export remains separate:49,574rows,29,110,553bytes,SHA2569c82646867c34b4534e6cf72b498bb760e08d531cf10187757a130e7a6911a3a. No historical file/service is deleted or overwritten.

This change aligns the strict source-v2 consumer with the healthy shared owner; requires a real /data mount; preserves known existing datasets before startup; fixes new event/state paths under a distinct immutable run identity; and fails if an existing run's source hashes change. The detector payload hashes and all strategy parameters remain unchanged. BRTI and contiguous quote freshness are rechecked after the BTC read, so a slow read cannot silently age them beyond the existing qualification limits.

A read-only observer records main, owner, displayed V8.1 and generalized serial states every5seconds. Errors and WAIT states remain in the record. The clean collector additionally records actual source/receipt timestamps for accepted BTC/BRTI input frames. It never replaces missing timestamps. Each append is an fsynced gzip member; the fixed-file, bounded byte export supports immutable snapshots and resumable retrieval without buffering the entire retained history. No observer HTTP request calls the authenticated upstream BRTI feed. No orders, private keys or environment values are included in its payload.

The run starts as DEVELOPMENT until a separate future cohort registration fixes UTC boundaries, revisions, universe and split roles. Five-second observations cannot certify all short-lived signals, full excursions or actual browser/manual execution. Production deployment timelines must be reconciled with the registered revisions before scoring.

Validation before deployment:19local tests pass, including frozen detector fingerprints, strict source schema, future/stale rejection, delayed BTC reads, post-read quote expiry, contract close during I/O, run-identity restart, changed-code rejection, append/concurrent integrity and real HTTP bounded incremental exports. Hosted CI uses this service's pinned requirements. Keep code, variables and explicit start/restart policy coordinated; the owner is already healthy.
