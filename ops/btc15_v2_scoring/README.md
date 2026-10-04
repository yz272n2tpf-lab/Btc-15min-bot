# V2 read-only scoring bridge

**Production scoring: BLOCKED.** This package is an offline compatibility layer, not a deployed runtime or a strategy change. First production proof and exact complete-cohort start are still unestablished. Synthetic tests are never production evidence.

## What is reused

The unchanged root `btc15_cohort_evidence_v1.py` is pinned by SHA256 in `bridge.py`. Its `classify_early`, `classify_final` and `classify_scalp` functions remain the classification authority. The native V1 file reader and `score_native_settlement` require a different schema/60-sample BRTI closeout and are intentionally not fed invented V1 records. V2 compatibility attaches verified official finalized Kalshi receipts directly and adds signal-level correctness and recorded executable-bid telemetry. No strategy evaluator or detector is called.

No existing V2 adapter was found in the recovered documentation tree and packages. The bounded repository code/commit searches are saved with the mission receipts; search-index absence is not proof about every private/unindexed branch.

## Snapshot, then score

Use only an already authorized shell/file capability in the existing production service. Merely running a command in Codespaces does not give access to Railway's mounted `/data`. The current connectors expose control-plane reads but no verified mounted-file/exec capability. No new exporter, SSH key, credential, service, deployment or alternate access route is part of this package.

The `snapshot` subcommand must run in the corresponding existing production runtime context, with this documentation-branch utility made available as a temporary file through that authorized capability. It checks the service, deployment, SHA, project, environment and volume against the frozen allowlist. It refuses a qualification service or a missing/mismatched environment variable; do not manually fabricate the variables to bypass that check. It reads only the fixed existing journal path.

```sh
python bridge.py snapshot --lane main --output /tmp/btc15-main-detached.sqlite3
python bridge.py snapshot --lane v81 --output /tmp/btc15-v81-detached.sqlite3
```

The two commands run in their respective service contexts, not in one service. Choose fresh destination names for later runs. Each creates one detached `.sqlite3` and adjacent `.sqlite3.receipt.json`; transfer both pairs using the same existing authorized file capability. The utility opens source SQLite with `mode=ro`, sets connection-only `query_only`, and invokes SQLite backup with a 30-second bound. It never opens the source for writes, checkpoints it, migrates it, or copies the database without its committed WAL. Source and destination paths must be separate; existing outputs are never overwritten. Receipts contain content hash, journal ID, sequence bounds, row count and runtime identity. They are operator/runtime provenance receipts, not cryptographically signed Railway attestations; retain the independently verified control-plane deployment receipt beside them.

In a checkout of the documentation/closeout branch, run locally against the detached pairs:

```sh
python ops/btc15_v2_scoring/bridge.py score --main /path/to/btc15-main-detached.sqlite3 --v81 /path/to/btc15-v81-detached.sqlite3 --output /path/to/new-checkpoint-directory
```

No production authentication, upstream polling or live-path access occurs during `score`. The CLI does not accept fixture evidence. The unchanged scorer must be present at the repository root with its exact pinned bytes. No third-party dependency is required.

Outputs:

- `adapted_events.jsonl`: every original V2 JSON record, losslessly decoded, with journal sequence, record hash, snapshot hash and lane. It uses `BTC15_V2_SCORING_ADAPTER_V1`, never the old native cohort schema.
- `checkpoint.json`: per-contract EARLY, independent FINAL, separate EARLY-helper events, SCALP origins/later bids/terminal guidance, PASS and UNAVAILABLE publication counts, official settlement links, completeness exclusions and failure clusters. EARLY actual ask/time remaining and ≤50¢/25–35¢ economics are retained. FINAL distinguishes qualified publications from unique first qualified calls per contract. SCALP reports observed MFE/MAE and target-first/stop-first telemetry; actual fills and realized profit stay null.
- `BLOCKED.json`: a processing-time integrity failure if encountered after output creation. Failures before output creation raise an explicit error and produce no checkpoint. A directory without a completed checkpoint is never success.

The price telemetry is observational. It does not change +5¢ arm / 4¢ giveback, target/stop policies, or any signal gate. Invalid or non-later/same-side-mismatched bids are excluded and flag the path. Incomplete/unavailable paths remain unresolved; the snapshot retains their original records.

## Completeness and cohort boundaries

Existing journal rules are retained: MAIN has a 15-second publication coverage interval; V8.1 has 6 seconds. These are the writer's coverage limits, not new freshness or trading thresholds. Completeness requires the original missing flag to be clear, matching event/coverage census, observed opening/closing edges, no publication gaps/time reversal, consistent official ticker/window/target, and both lanes' own authoritative finalized receipts. A SCALP path with no verified terminal or a gap remains unresolved and prevents fully scoreable classification.

The 04:00–04:15 UTC deployment window is permanently excluded. `FIRST_POSSIBLE_OPEN=2026-10-04T04:15:00Z` is only the earliest possible full window; it is not the production cohort start. The cohort begins at the earliest actually complete and settled contract in the two verified snapshots. If the retained sequence prefix is missing, the bridge refuses to certify an exact first cohort start. Existing lane recording starts remain MAIN 04:14:21.909025Z and V8.1 04:13:31.705281Z, independently documented in the handoff.

All observed signals in partial contracts remain inspectable but are excluded from complete-cohort aggregate correctness. Pending results are never scored as losses or wins. Qualification, older builds, old native JSONL, Ground Zero, and fixtures cannot enter the production CLI path. Finalized official outcome is used rather than a guessed outcome from prices; no 60/60 fields are fabricated.

The adapter can be rerun unchanged on later detached snapshot pairs. Stable contract, origin and publication IDs prevent per-publication counts from being mislabeled as unique signals; repeated identical snapshots give identical reports. The focused forward test appends a second contract to the same fixture journals and reruns the same snapshot/adapter/scorer pipeline. That establishes schema continuity offline, not a live scheduled snapshot job. Contract indexing avoids rescanning the entire event list for each contract; full decoded history is still held in memory, so this is an offline bounded-journal tool rather than a streaming service.

No recurring snapshot job was created. Journal bounds remain 30 days OR 300,000 events. A later receipt with a retained-prefix gap requires the existing archived snapshot lineage; this implementation does not silently reconstruct discarded evidence or claim complete lifetime performance. It intentionally blocks first-cohort certification after prefix loss rather than inventing a start.

## Verification and remaining acceptance gate

```sh
python -m unittest discover -s ops/btc15_v2_scoring -p test_bridge.py -v
```

Tests use the unchanged frozen journal writer under temporary directories. They verify committed-WAL inclusion without changing source database/WAL bytes, no source writer lock, exact scorer pin, fixture/qualification/old-build rejection, pending settlement exclusion, actual origin ask, UP/DOWN correctness, separate FINAL calls/helper records, later-bid chronology, MFE/MAE, target/stop ordering, startup/gap exclusion, deterministic repeat and forward contract processing. They do not repeat the production qualification suite or evaluate strategy performance.

**One precise next action:** obtain the two detached production SQLite backups and their generated receipts using the existing authorized runtime file/exec route, then run the command above once. Access requires the user's existing-account sign-in; no replacement route was attempted in this mission. If the resulting snapshots still contain no complete settled contract, retain BLOCKED and the reported missing reasons; do not relax the completeness gate or introduce a multi-day pre-launch requirement.

Latest bounded coverage reads in `qualification/v2_scoring_bridge_20261004` show all four observed windows marked missing in both lanes; complete coverage is not established even for settled windows. Those summaries are not full event snapshots. Production scoring is VERIFIED only after a real snapshot-originated complete contract reaches the unchanged classifiers, V2 settlement compatibility and final report, with origin/price/settlement references intact.
