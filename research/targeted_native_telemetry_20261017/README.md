# Final targeted native recorder corrections — 17 October 2026

**READY for one separately authorized corrected 60-second diagnostic.** Offline engineering passes. Native performance, clean native seals and readiness for the 20-minute preflight or 10-hour EARLY evaluation remain unproven. No Railway operation, native capture, order, production restart, resize or configuration change was performed in this assignment.

Research branch: `research/targeted-native-telemetry-20261017`, based on `be1c02a1e0a320b668c9b7aa394aae6fe1f88269`, retaining corrected baseline `f1a234e670890f64a5a0eff11704dfbfde9bcd16`. The exact engineering commit is the commit containing this package. Candidate producer commits below are separate, pinned release installations.

## Minimal changes and guarantees

Six recorder/reader files changed: `telemetry.py` (new), `adapters.py`, `capture.py`, `burst_journal_research.py`, `reader.py`, and the reader code fingerprint in `windowed_campaign.py`.

- **Publication outcome:** observations are inserted into recorder-owned clones of two SHA-256-pinned native functions. Removing the observation seams must reproduce the original AST exactly before installation. Original input hash, prior native/latest publication identity, original boolean return or exception, native rejection reason, outcome stage, actual health snapshots and validation-clock returns, evaluation count and resulting frame identity travel with the existing information evidence. No extra evaluation, health read, clock call, refetch or publication attempt is made. Original exceptions are re-raised. Concurrent native workers retain separate traces using thread-local state and the original worker lock.
- **Strict bounds:** at most 16 KiB per outcome, 2 MiB total and 2,048 inputs; snapshots have depth, item, string and byte bounds. The existing writer's 1-KiB field bound is preserved through bounded chunks reassembled on its existing archive worker. Exceeding a bound explicitly fails capture without changing the native return. Existing information failures remain failures.
- **Quote overruns:** MAIN `QUOTE_ACCEPT` and V81 `QUOTE_RECEIVE` carry a unique recorder hook ID and original event identity. At most eight overrun/admission-failure samples retain wall duration, thread CPU, off-CPU difference and exact admission result. Overflow is an evidence failure. Samples are written through the existing recording-health stream at stop and retained in terminal status. In-flight hooks have a 250-ms stop bound; timeout remains INCOMPLETE.
- **Unchanged protections:** nonblocking queue admission remains; mutex contention is explicit `ADMISSION_BUSY` loss with `QUEUE_MUTEX_BUSY` detail. Individual >5-ms and p99 protections (>1% over 1 ms after 100 calls per label), native freshness, clocks, entry policies and signal-only/no-orders behavior remain unchanged. Existing immutable admission-charge accounting, drain and candle chronology corrections remain intact.

Protected production files are byte-identical: all 38 MAIN and 14 V81 protected paths, original entrypoints/native writers, dependencies, FINAL/EARLY/SCALP strategy, Kalshi integration, thresholds, settlement and order policy. Both packages are default-off and signal-only. This proves source/policy and controlled-call equivalence, not zero wall-clock impact: observation work can shift real validation boundaries and must pass the native diagnostic.

## Focused verification

| Check | Result |
| --- | --- |
| Targeted regressions | 13 pass: success/frame/journal equivalence; original call order/count; six rejection stages; original exception propagation; no-progress/prior identity; concurrent input isolation; detached health snapshots; bounds; reader linkage rejection; exact charge/drain/seal; overrun CPU/wall identity; explicit mutex loss; durable overrun association. |
| Retained correction regressions | 18 distinct cases pass across retained logs. Two queue fixtures initially failed because they bypass construction; compatibility was fixed and both passed with the affected overrun cases. |
| Existing package checks | 7 pass: archive/inventory exactness, allowlisted deployed diff, release integrity, compilation, entrypoint/native-call preservation, shared information installation and exact rollback restoration. |
| Static installation | MAIN, information and V81 pass using preserved native dependency metadata; zero native callbacks, new threads, network or capture. Complete installed Git trees equal the published candidate trees. |
| Authentic replay | Existing reader/finisher once, new output directory, 29.971 s, max RSS 36,288 KiB. All 12 original objects unchanged. All five result ledgers byte-identical to the authentic baseline. |

**38 distinct focused tests passed across these runs**, not a claim of one uninterrupted 38-test invocation. Initial failures and their corrections remain in `tests-initial.txt`, `test-results.txt`, and subsequent logs. The initial telemetry chunk/fixture defects were corrected before candidate packaging. A package reproduction initially encountered a workspace rsync temporary duplicate CSV; the failed output was retained, and the unchanged builder reproduced exactly in a private directory. The initial compatibility check lacked local copies of newly published Git objects; without a shell/proxy retry, full installed Git tree hashes were compared with successful GitHub commit receipts. These are preparation failures, not discarded native diagnostic attempts.

The authentic three raw segments still total **10,890,786 bytes**. MAIN SHA-256 `f8b106347fa7020375b7656dc90106ab7feada4c0698371c1c9fa85808c0267b`; V81 `2d30908bb04dcd8cc415d28934908958182e2cb2461939a5722fc5af79f55dd4`; information `02c6a32b8435e2a7a48e2b7b0287b02ab6288a8f2e75c4769f6c3e5ebea3e83d`. Replay remains **INCOMPLETE**, with 27 V81 causal matches, 195 quarantined records and all seven publication failures. MAIN sequence 308 remains a current bucket not completed at acceptance; the chronology correction is intact. No original failed counter, seal, missing observation or genuine rejection was reclassified as recovered evidence.

Bounded synthetic measurement (128 inputs, stub evaluator/journal): publication median 0.255 → 0.352 ms, p99 0.479 → 0.611 ms, observed maximum 1.079 ms; both paths used exactly 256 health reads, 256 clock calls and 128 evaluations/journal calls. Largest outcome 1,432 bytes. Quote wrapper **without queue I/O** p99 0.0148 ms, max 0.0503 ms. These are local observations, not native performance projections. Local sklearn 1.8 emits warnings when existing fixtures load 1.9 model objects; no model-accuracy or native-inference qualification is claimed. Static installation uses the preserved native 1.9 dependency metadata.

## Exact installation and rollback identities

Information uses the MAIN installation; no third service or volume is introduced.

| Identity | MAIN / information | V81 |
| --- | --- | --- |
| Candidate branch | `research/corrected-native-main-20261017` | `research/corrected-native-v81-20261017` |
| Candidate commit | `8847c61b0a98c436618d7aef8b07a1626bc00e13` | `510da93a925a66f2040cc10dd08c2532caccece2` |
| Package ID | `BTC15_TARGETED_NATIVE_MAIN_20261017` / `BTC15_TARGETED_NATIVE_INFORMATION_20261017` | `BTC15_TARGETED_NATIVE_V81_20261017` |
| Archive bytes | 24,573,741 | 24,557,477 |
| Archive SHA-256 | `d45fc04602c5228261a474b8e90ce61bc85bc98f8f6fee518feceab33c450150` | `b7065dcd7b75163c9d2f19f3a18bfa01104f2e6e0642b29a65e6f8d8f011b451` |
| Release manifest SHA-256 | `913d77886a903214757dc1e15a9a4780f35969809fbeb03cc4485d00ddc5d634` | `ddce706f5df7811c5c099da2ae92beb5c942b695956441c419a03220cc2e565b` |
| Rollback source | `dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72` | `c14b3f9b04caea13e62bcdd6fb0e5990049aa17b` |
| Last verified rollback deployment | `3d4b26ce-d11c-4b3c-ac8c-1ed5a403f3c9` | `c04d806f-d279-4a0b-8b3b-5f6316c985a6` |

Full source inventories, protected hashes, install hashes and rollback-copy checks are in `PACKAGES.json`. Archives reproduce using the existing builder through `build_candidate.py`; source deployment uses the pinned candidate commits. Eighteen package paths differ from deployed releases, including retained prior recorder engineering and manifests; this assignment changes only the six files listed above.

## One-run authorization package — do not execute without separate approval

Run ID: `CORRECTED_DIAG_20261017_8847c61b_510da93a`.
Config: `campaign.approval-draft.json`, SHA-256 **`e5cfbed6bfe35dc43ab45bc2db2530bd00f1c69dd582f7dea8cd5904f6514ccb`**.
Exact six activation and six rollback service calls are in `SELECTIVE_ACTIONS.json`; authorized/executed are both false. Rollback actions equal the previous approved rollback list. No environment-wide staged patch, accept-deploy, railway-up, storage change or new infrastructure is included.

Storage requirements remain **2,181,038,080 bytes per producer** (32 MiB capture plus 2 GiB operating reserve), plus 256 MiB conservative native-growth allowance: **2,449,473,536 bytes before provisioning**. Latest preserved post-rollback readings are MAIN 9,112,469,504 and V81 2,583,113,728 bytes; V81 then exceeded the approval floor by 133,640,192 bytes. These are historical readings, not current free space. A fresh pinned read immediately before approved writes must pass; no resize is proposed.

Caps stay MAIN/information/V81 compressed 16/16/32 MiB, decoded 128/128/256 MiB, records 20,000/50,000/200,000. Queue remains 32 MiB/16,384 items, observation charge 4 MiB, batches 1 MiB/256. New telemetry consumes these existing caps. Research requires 5 GiB free; existing reader DB limit 1 GiB and reader budget 240 s. No capacity workload was repeated.

Proposed execution, only after approval:

1. Reuse existing research service `1fff593b-8b09-4cc4-8c51-f9603082657f` and its existing `/research-evidence` volume `2dba2ef6-b84d-4abf-9d04-58a1e77082c5`, with one replica and restart NEVER. Pin its source to the exact engineering commit containing this package; never launch its old operational-probe command. Preserve its prior source/start configuration for restoration. Read current producer identities, sole production environment, seven historical volume identities, four staged fields, pinned SSH access and rollback availability once; stop on mismatch. Do not repeat lease/capacity audits.
2. With `BTC15_APPROVED_RESEARCH_SHA` set to that exact reviewed commit, run the existing-adapted `provision_once.py --separately-authorized-once` under a 180-second outer deadline. It checks both producer source/dependency identities and fresh storage before either exclusive control-file write. It refuses existing run roots. Configuration is fsynced under `/data/btc15_recordings-control/<run-id>/campaign.json` and `/research-evidence/approved/<run-id>/campaign.json`. This is a future approved action; the helper was only compiled here.
3. Execute only the listed `activation` operations, once, in order. Variables use `skipDeploys:true, staged:false`; start-command and source substitutions are service-specific and pinned. Read back source and staged state after changes. Preserve staged patch `ead9997e-b5b7-4668-a612-e8417e197838`, four changes for unrelated service `84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1`. Stop if sole-environment or field scope differs; follow platform approval requirements.
4. Bind actual returned deployment IDs to recorder attestations. Run once for **60 seconds per role**, including startup. Existing 0.5-s watchdog scheduling is not a hard real-time kill; report actual duration and any overshoot. No role extension, repeated capture, input reevaluation or freshness relaxation.
5. On first recorder loss, contention, overrun, p99 breach, telemetry bound/schema/link failure, native-journal gap, identity/storage failure, drain failure or native-health regression, stop admission and preserve INCOMPLETE evidence. Native publisher rejection remains a failure with its actual reason; do not convert it to success. Operator stop uses existing pinned-SSH `python -B -m ops.live_recording.remote finish --roles main,information` / `--roles v81`, with this exact config on stdin. Never signal native owners. In-flight hook closure is bounded to 250 ms; existing writer join is 5 s and remote seal wait 8 s. Late seals do not erase timeout/loss.
6. Before normal rollback, invoke the existing finisher/reader once, serially, with its mounted lease:

   `timeout --signal=TERM --kill-after=10s 420s python -B -m ops.live_recording.finish --config /research-evidence/approved/CORRECTED_DIAG_20261017_8847c61b_510da93a/campaign.json --output /research-evidence/CORRECTED_DIAG_20261017_8847c61b_510da93a-reader`

   Preserve producer originals under `/data/btc15_recordings/<run-id>/`, transfer hashes, health/terminal/seal receipts, partial failures, logs and reader ledgers. Require exact admitted/durable accounting and zero losses for PASS. Native-health failure takes priority: rollback promptly and retain whatever incomplete evidence exists. No second finisher campaign or broadened recovery is authorized.
7. Execute only the `rollback` list once: disable capture without immediate variable deployment, restore original start commands/build/manifest pins, connect original release sources. Retain control files and evidence. Verify returned rollback deployment IDs, healthy source/manifest, disabled capture, unchanged seven volumes and four staged changes. Stop an unsuccessful rollback for operator review. Restore research configuration and end its job, verifying zero running replicas. Do not proceed to the 20-minute preflight.

Installation and rollback each may restart both producers; downtime, cold-start duration and current-contract signal continuity are not guaranteed. The service operation sequence is not atomic. A spontaneous restart between settings and source connection can fail closed on mismatched pins. Added observations may expose or worsen timing pressure; that is a diagnostic failure, not grounds to relax guards.

Cost request: **$0.10 incremental compute planning allowance**, reusing the earlier 17-minute bounded research-job plan and existing services/volumes; retained storage is separate. This is not a hard billing cap. Current account credits, total spend and headroom under the preferred $20 monthly budget are unverified. No capacity adjustment is requested.

**Authorization request:** approve the two exact candidate commits and six selective activation calls above, the exact configuration hash, one 60-second-per-role corrected diagnostic, bounded existing-research provisioning/finishing and exact rollback, accepting the interruption risk and $0.10 planning allowance. No other deployment, native run, resize, strategy change or order is included. If this corrected diagnostic fails, reassess whether the architecture merits further work before authorizing additional engineering. The next target remains the fixed 10-hour EARLY evaluation after a separately successful 20-minute preflight.
