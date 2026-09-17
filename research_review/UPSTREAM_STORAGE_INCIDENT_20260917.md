# Early / Final upstream storage incident — read-only diagnosis

## Approved recovery update — 2026-09-17 01:31 UTC

The user explicitly approved the proposed storage-only recovery. This approval persists; no repeat permission request is needed within that scope. A fresh Railway status response confirmed `btc-15min-bot-volume` is allocated **500 MB**, attached only to the identified source service at `/data`. The proposal to increase it to **1 GB** therefore applies. The source remains CRASHED, and `main` still matches deployed commit `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.

No volume or service mutation has been executed. The user needs the direct Railway UI resize step because the available direct connector has no volume-resize operation: open the existing `btc-15min-bot-volume` in `noble-warmth` / `production`, select Live Resize, choose 1 GB and confirm. Afterward inspect capacity and source status before any separate restore action, since resizing a full volume can itself restart the attached source. All frozen collectors remain excluded from changes. Pre-recovery status/config and live state snapshots are archived in `recovery/20260917T013150Z/`.

The diagnosis and original unexecuted proposal below are historical; their allocation uncertainty and pending-approval statements are superseded by this update.

Observed 2026-09-17. No Railway mutation, restart, deletion, production code change or collector change was performed. This Work thread remains the sole control authority.

## Evidence

- Railway project `baea4e22-d004-4434-b2c5-81a7fbc05086`, environment `61775c5d-c583-4dfc-af41-f25578856fd9`: 50 services, no staged changes reported.
- Upstream service `Btc-15min-bot`, ID `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`, is CRASHED. Deployment `ebfaca47-ebc6-402a-9e99-21d948b0ee1e` uses commit `8b7f8b48694364cb8c47456d0ab491b102aa42c0`; status updated 2026-09-16T02:37:33.647Z.
- Its persisted mount is `/data`, volume ID `6ced6b1a-3755-4518-a240-c895e936d443`.
- Runtime logs report `OSError: [Errno 28] No space left on device` at 02:36:59, 02:37:06 and 02:37:21 UTC on September 16. HTTP broken-pipe errors and upstream rate-limit responses also occurred. Storage exhaustion is a confirmed failure; the exact final process-exit cause was not exposed by the inspected logs.
- Startup inventory at 02:27:08 UTC reported 424M under `/data`, including 245M unified snapshots, 76M scalp snapshots, 41M early snapshots and 29M BRTI parity records. These are evidence files and must not be deleted or truncated to recover space.
- Read-only Railway disk metrics over the last 24 hours reported current/max 0.498040832 GB. The configured capacity is NOT exposed by the inspected config tool; a 0.5-GB allocation is plausible but unverified. Do not silently equate usage with allocation.
- Early `/state` checked at 2026-09-17T01:23:06.308945+00:00 still has 22 eligible contracts, 2 recorded calls and 2 settled calls. Its last successful source poll is 2026-09-16T02:37:31.400882Z, followed by read timeouts to the crashed upstream domain.
- The Early initial review gate requires BOTH 30 eligible contracts and 12 settled entry calls. Remaining: 8 eligible contracts and 10 settled calls. Only the first qualifying entry per contract counts; eight new contracts cannot alone supply the ten missing entry calls. All currently recorded calls are already settled.
- Reviewed scorecard source reads `/dashboard_state.json` every five seconds and records official settlement after rollover. The current iteration fetches the main source before checking pending settlements. Fetch failures prevent that iteration reaching settlement processing. There are currently no recorded unsettled Early calls to recover by settlement lookup alone.

## Recovery proposal — NOT EXECUTED

Your no-production-changes lock requires explicit approval before changing this upstream production service or its storage. Frozen Early/Final/Scalp collectors remain excluded from all restarts, edits and configuration changes.

1. Confirm the exact allocation and mount for the identified existing `/data` volume. Preserve its data and any available backup; do not create a competing writer or mount the volume elsewhere.
2. If confirmed smaller than 1 GB, propose expanding ONLY that volume to 1 GB. If it is already 1 GB or larger, stop that resize proposal and investigate the conflicting capacity/inode evidence. Never shrink or delete data. A larger allocation is a separate decision.
3. Restore only the already-crashed upstream service using the same deployed commit, start command, variables and signal rules. Do not deploy a new branch tip or change protected policy thresholds. Verify the selected deployment action preserves that source identity before executing it.
4. Confirm fresh contract IDs, clocks and quotes at the existing upstream endpoint, followed by advancing source-success timestamps in the untouched Early and Final collectors. Check original call records remain unchanged. A successful deployment alone is insufficient.
5. Record the outage and recovery boundary separately. Missing contracts remain unobserved; do not manufacture/backfill live observations or count repeated polls as new samples. Treat new post-recovery evidence as a disclosed collection segment and assess continuity before acceptance.
6. Wait for genuinely qualifying first entries and official settlements. The count gate permits initial review, not automatic certification or promotion. No guaranteed completion time follows from the two existing calls.

The direct connected Railway toolset exposes status/logs/metrics/config and redeploy, but does not expose a direct volume-resize operation. The UI's existing-volume settings may therefore require the user's interaction; no action was attempted through another agent or account.

Railway documents resizing paid-plan volumes in volume settings. A completely full volume can trigger an offline resize and restart of its attached service, so approval must precede even the resize. Storage is billed on usage at $0.15 per GB/month, separate from runtime costs: a fully used 1-GB volume is approximately $0.15/month for storage alone.

Sources: [Using volumes](https://docs.railway.com/volumes), [Volume reference](https://docs.railway.com/volumes/reference), [Pricing](https://docs.railway.com/pricing/plans). Private operational observations above came from the connected Railway tools and the read-only Early state endpoint.

## CURRENT STATE

- CONTROL: No frozen collector or production service changed; existing samples preserved.
- NEW SHADOW: Existing V2 deployment unchanged; this milestone adds incident documentation only.
- BLOCKED: Confirmed upstream disk-exhaustion errors and stale Early/Final input. No storage recovery executed; actual allocation still requires confirmation.
- NEXT STEP: Obtain approval for the narrowly scoped storage/source recovery above, then confirm volume capacity before any resize. Preserve every frozen service and record the collection gap.
