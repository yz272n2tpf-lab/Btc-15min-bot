# BRTI retry recovery — tested draft, not deployed

Checked 2026-09-17 01:59 UTC. This Work thread is the sole control authority.

The volume/source recovery is complete. BRTI access is intermittent: the source recorded HTTP 429 errors after recovery, but also a fresh direct BRTI value at 01:54:06 UTC. A dashboard snapshot generated at 01:56:16 UTC reports fresh paired quotes, a BRTI effective age of 1.92 seconds and direct authority ready. This single healthy snapshot does not establish sustained recovery. The shared feed independently still reported PRIMARY_ERROR and 24-second age in the immediately preceding snapshot.

## Findings

- The deployed source revision is `8b7f8b48694364cb8c47456d0ab491b102aa42c0`. Its runtime wrapper chain reaches `bot_two_output_build_v4_13_profit_protection_shadow.py` through the full-validation and Rescue wrappers. The inspected file matches the deployed Git blob; SHA-256 `cfe325434e57588a45ea429ca160198da954cd1c739418a2ba7bdfc74e5a6c2c`.
- The source's `_brti_poller` retries on its one-second cadence even after HTTP 429. Its 30-second warning throttle only reduces logs. It does not reduce request attempts.
- The same source process tree also runs a parity process with a 15-second cadence. This draft does not edit that process, the shared feed, or any frozen collector.
- The separate shared feed already implements exponential 429 backoff. Its observed counters rose from 96,845 attempts / 77,679 successes / 19,148 rate-limit errors at 01:41:43 UTC to 97,001 / 77,799 / 19,184 at 01:53:38 UTC. That is 156 attempts, 120 successes and 36 additional 429 errors over the inspected interval. It was already receiving 429s before the root source recovered. The root retry loop is therefore an avoidable pressure source, not a proven sole cause.
- Account-wide traffic, the effective endpoint cost, and any provider-side BRTI-specific quota have not been measured. No credential values were retrieved, no direct Kalshi diagnostic requests were made, and no quota or account tier was changed.

Kalshi's current [rate-limit documentation](https://docs.kalshi.com/getting_started/rate_limits) recommends exponential backoff after HTTP 429 and states that Retry-After headers are not currently provided. This general guidance does not establish the exact CF Benchmarks endpoint quota in this account.

## Concrete draft

`brti_retry_patch.py` reads only the exact hash-pinned source, compiles the candidate without executing it, and prints `brti_retry_candidate.patch`. It has no apply or deploy operation. The proposed patch changes only `_brti_poller`:

- After consecutive 429 responses, wait 2, 4, 8, 16, then 30 seconds, plus up to 0.25 seconds of positive jitter. The wait begins after the failed response completes.
- Reset to the existing one-second cadence after success. Other error behavior remains unchanged.
- Use monotonic elapsed time for the polling schedule.
- Keep the endpoint, credentials, response parser, provider publication timestamps, duplicate handling, five-second freshness limit, qualification rules and order behavior unchanged.

Ten offline tests pass. They execute the actual extracted draft poller with a fake clock and fetch function: capped retries, slow responses, jitter, reset on success, duplicate/provider-time preservation, unchanged healthy cadence, non-429 classification, unchanged code outside the poller, and rejection of source drift. No real network, credentials or sleep is used. In a deterministic continuous-429 minute, the existing function makes 60 attempts and the candidate makes 5. This demonstrates retry suppression only; it is not a live efficacy claim.

## Deployment boundary

The user's mission lock prohibits production changes; the subsequent approval covered storage expansion and restoration at the same revision only. This draft has NOT been applied to the source, deployed, or promoted. All 50 service status/deployment records remain unchanged since completed storage recovery.

Applying this transport correction requires explicit approval for the source-only change and one restart of `Btc-15min-bot`. Do not push main: other services may follow it. Prepare a dedicated recovery branch at the verified source revision containing only this patch, bind only the identified source service to it, and preserve all other service revisions/configuration/volumes. The branch/source binding must be reviewed before deployment. If the connector cannot select that branch for this existing service, a narrowly scoped UI source-selection step is required.

The restart and changed source polling would create another disclosed upstream observation boundary even though frozen collector processes remain running unchanged. Do not backfill, re-label the gap as observed, or assert uninterrupted sample continuity. Validate actual HTTP 429 frequency, provider timestamp freshness, source and collector health, retained records, and no drift of the other 49 services after any approved deployment. Rollback would also be source-only and must preserve the volume. Do not bypass BRTI qualification or substitute another feed to improve apparent coverage.

## CURRENT STATE

- CONTROL: All frozen collectors and accepted V2 untouched; recovered upstream remains on the approved original source revision.
- NEW SHADOW: Existing V2 unchanged. Added this offline retry draft, exact diff, ten tests and diagnosis evidence only.
- BLOCKED: Intermittent BRTI rate limiting remains; a local test pass is not live recovery. The source-only transport change is outside the prior storage approval.
- NEXT STEP: Obtain explicit approval for this specific source retry change and restart before deploying; retain a separate post-change collection boundary.
