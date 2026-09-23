# BTC15 BOT COMPLETION SCORECARD — interrupted rollout checkpoint

2026-09-23 03:52 UTC. **Not production ready. Main candidate deployment FAILED; latest dashboard read timed out.** Existing main deployment remains listed SUCCESS by Railway, but serving recovery is not confirmed. No original evidence was deleted. The follow-up release operation was cancelled before its branch/PR was created, so production mutations were paused.

| Area | Current result |
|---|---|
| Infrastructure | FAIL: main startup blocked by archive sizing; clean collector has no durable mount; raw reference coverage remains incomplete. |
| Kalshi | Auth/discovery observed in owner and migrated consumers; corrected main acceptance FAIL/pending. |
| BRTI | Source-integrity PASS: true timestamps,3600real one-second history points,503on429 and200on recovery. Post-consolidation51/51 sampled ready states qualified over03:44:02–03:50:24UTC; source age median1.954s,range0.442–3.433s;168/168additional requests succeeded,0additional429. Long-run reliability acceptance pending. |
| 15-minute alignment | Existing exact ticker/fixed target behavior preserved; corrected main live acceptance pending. |
| Rollover | FAIL for corrected candidate:0. Historical10handoffs median2.0785s remain historical only. |
| Ladder1 / FINAL | Thresholds unchanged; valid current contribution/calibration not yet measured. |
| Ladder2 / EARLY | Thresholds unchanged; valid common-universe coverage/entry evidence pending. |
| Ladder3 / SCALP-reversal | Both directions and frozen detectors retained; qualified incremental contribution pending. |
| EARLY | No corrected frozen cohort yet; accuracy/coverage/odds/timing/MFE/MAE unavailable. |
| FINAL | No corrected frozen cohort yet. Historical raw263/278=94.60%,46.72%coverage is uncertified; not proof of93–95%goal. |
| SCALP | Consumer cold-start PASS after reference repair; archive674,352,533bytes retained;65startup tests pass. Prospective signal/exit performance pending. |
| Restart/recovery | Owner and useful consumers cold-start; main fails preservation preflight. Full-system FAIL. |
| Consecutive corrected live rollovers | FAIL:0; at least4still required. |
| Logging/scoring | Historical data preserved; corrected main observer has not started. Certification FAIL/pending. |
| Signal-only / NO ORDERS | PASS throughout. No credentials exposed/created/rotated; no strategy threshold or weight change. |
| Temporary/dead dependencies | Useful V8.1/scalp services migrated to shared owner and direct main credential references. Isolated test confirmed idle. Inactive immutable service future start set idle; effective restart configuration still must be rechecked. Raw reference expressions remain inaccessible. Clean collector transport/retention not yet migrated. |

## Merges and deployments

- PR16 owner, fix/brti-source-history-20260923:37735e737690096edea31beb2faff6842770ac4f; deploymentb73bdf23-af30-4150-883e-1a300229538eSUCCESS.
- PR17 V8.1, fix/v81-single-brti-owner-20260923:1aa353ca46fc4348bfe6855325d544a02af20f8a; first cold start failed malformed PEM; repaired existing credential references directly to current main; deploymentacb3034a-26ae-40f5-919b-c9235bf6e9d7SUCCESS.
- PR18 generalized SCALP, fix/scalp-single-brti-owner-20260923:0d698328b17825a0c89479053c0433f945bea8cd; first cold start had empty credentials; direct references repaired; deployment009fce2f-af6d-4b3a-a4df-fff79e092c8bSUCCESS.
- Isolated idle deployment8ae6c679-ac45-4935-9b81-1f3f4cf5deb4SUCCESS; logs explicitly confirm PARKED/no upstream polling. Prior redeploy reused old start configuration; a fresh config-triggered deployment was necessary. No service deleted.
- PR15 main, audit/btc15-completion-20260923:03055fe21e9df9ea7c0da9e6ed5d354e8fe26e8c; deployment55147fe6-0120-4b92-877f-f9db85c4842eFAILED before collector startup because worst-case uncompressed archival space did not fit. Main baseline rollback662873c41fde364a994b6a22dc0bb18f21d43fdc remains preserved.
- PR19 clean, fix/clean-scalp-shared-source-20260923:18a142c6af43476fdc8a7ed388099b5d6db8a6c0 remains unmerged. Clean export49,574rows preserved separately; SHA2569c82646867c34b4534e6cf72b498bb760e08d531cf10187757a130e7a6911a3a.

## Concrete pending correction

ARCHIVE_SIZING_FIX.patch applies to main03055fe. When the conservative uncompressed size cannot fit, it computes a ZIP size without writing data, checks actual compressed capacity plus reserve, compares exact prefix hashes between passes, fsyncs and validates the final ZIP. Originals remain untouched. The cancelled operation created no follow-up PR or deployment.

Tests: initial baseline168(167pass/1fail); merged main192/192local and hosted35815308694PASS; pending sizing fix193/193local in13.507s, including3preservation tests. Pending sizing fix has not run hostedCI. Owner11local/source tests and hosted35814659326PASS; shared guard migrations hosted35813362132/35813365423PASS; scalp archive migration hosted35815332216PASS; scalp production65startup testsPASS; clean3consumer testsPASS. Static path/parity/authority gates and wrapper self-tests passed before rollout.

## Exact remaining work and required access

1. Resume the cancelled release action: create/review/test/merge the sizing correction, deploy, prove successful preservation and main cold start. Do not bypass preservation. Verify the current serving outage/recovery explicitly.
2. Main1GBvolume has about706MBused before the new archive; measure growth and establish adequate retention capacity. Connected Railway tools expose no volume creation/resize operation. Clean requires a durable volume mounted/data before any restart/configuration change. This needs Eric to provide that infrastructure operation or an authorized supported capability. No browser sign-in.
3. Prove source freshness/429reliability with consolidated consumers, new main parity/final60, strict quote provenance, exact target/open/close and downstream publication readiness. Verify one upstream owner, inactive/parked processes and effective restart policies; retain credential-reference visibility limitation.
4. Obtain at least4consecutive corrected live rollovers, main/container restart and upstream interruption/recovery. No old-rollover substitution.
5. Establish an immutable common-universe forward cohort with missed intervals and separated tuning/validation/untouched holdout. Current raw scorecards and moving research splits remain uncertified. No threshold tuning is justified yet.
6. Measure ladder overlap/unique contribution, EARLY coverage/accuracy/entry odds/timing/excursions/FINAL relationship, FINAL accuracy/coverage/timing/calibration/failures, and SCALP both directions/reversals/exits/false positives. Main V8.1 stop/profit-protection integration is still unfinished and needs prospective evidence.
7. Preserve and diagnose crashed research jobs before any restart; no historical run mixing or deletion. Complete whole-system acceptance after evidence gates pass. Final visual dashboard remains a separate phase.

## Continuation authorized at12:04UTC

Eric requested continuation. PR20 fix/evidence-compressed-sizing-20260923, head5afc9a71cb836bb4a23368142a064357a6686d2f, passed hosted run35858210008 and was authorized for merge/deployment. Owner overnight501minute samples:500qualified,median2.089s,max6.192s; no new429over03:45–12:05UTC. These are point samples, not continuous availability. Main restoration and corrected rollovers remain pending.

## Continuation checkpoint at 12:26 UTC

PR20 merged e09f295701266383209cad05370faa6c7294dcf1; main successfully archived 16 files /718,017,780 original bytes into110,023,470 ZIP bytes before startup. Repeat main restart reused the validated archive. Original evidence remains intact. Main deploymentaf1c398c-8e6d-4b5d-9339-a1e3b214707b SUCCESS.

PR21 fix/rescue-retained-history-memory-20260923 merged26e9d09d4b82290dd930a73b686d573d88f3a03f.195/195 local regressions and hosted35859253575 PASS. Streaming applies exactly the previous timestamp filter before retaining the eligible batch; sorting, duplicates, signals, thresholds and original391MB CSV are preserved. Deploymentdd140dca-2abc-4a86-8edd-eb84eb3d0804 BUILDING.

Owner restart unexpectedly reused a launch snapshot without the shared entrypoint and ran legacy bot.py, which failed before credentials/authentication. Deployments3e2d8a79-2308-4df2-a424-63549b32886b and8a2698af-0aaa-47ff-b188-79b46ac82d14 CRASHED. Updated explicit start command and healthcheck, then a fresh config-triggered deploymentc7708b61-892d-4c31-9e8a-8d6d5f7ecff9 SUCCESS launched the shared owner. Source age0.739s,17/17 requests,0errors, new epoch a1dd7b2d95a84737b2b72be6c6f2721f;3600 true source points exported before a repeat restart test. Tool rejected setting railwayConfigFile as deprecated; no workaround/authentication attempted. Reapplying an identical variable produced no new deployment; changing the non-secret infrastructure revision marker did.

Main during owner outage:18 sampled API frames had no raw EARLY/FINAL/coreSCALP readiness; BRTI authority false and parity WAIT with true stale ages. V8.1 WAIT and no new qualification observed. This is sampled evidence, not proof that every intermediate frame was observed.

12:15 handoff on e09f:1.830s exact ticker; target ready27.257576s; timestamped book27.532430s; usable quote/source snapshot32.358314s. Preceding contract closeout60/60 true readings, average85462.47, DOWN completeTrue. This precedes the memory correction and does not count toward four consecutive final-candidate rollovers.

Storage remains a blocker: main1GB volume usage0.936312832GB; clean collector lacks a persistent mount. Connector has no volume create/resize capability. No deletion, key operation, visual redesign, threshold change or order operation performed.
