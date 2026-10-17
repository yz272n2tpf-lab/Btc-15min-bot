# Native diagnostic operational gates — 2026-10-17

**NOT READY / NO-GO for diagnostic activation.** This report continues
`research/native-diagnostic-bundles-20261017` at
`7b4cbfe026e1c110a1f5ed3cd6b5b09355c2ad24`. Changes are confined to this new
research directory. No producer, reader, validator, package, strategy, signal
policy, threshold, timing policy or entry-price code was changed. No deployment,
restart, resize, setting change, capture, order or historical-data write occurred.

| Operational gate | Decision | Evidence / exact limitation |
| --- | --- | --- |
| Live source and package identity | PASS | MAIN `dd46b7bc...`, V81 `c14b3f9b...` and deployment IDs match baseline; both unchanged package archives rehashed successfully. |
| Actual producer storage and reserve | FAIL — blocked | No authenticated shell with the existing key is available here. Metrics are not filesystem free bytes. |
| Minimum safe V81 capacity | FAIL — unresolved | Nominal metric-derived deficit is 400,395,776 bytes before native growth. Actual free space and supported resize increment are required. |
| Mounted research-volume single-reader lease | FAIL — not run | Existing research deployment has zero running replicas; code is still d50, before the lease addition. Starting/deploying it is forbidden in this run. |
| Exact native runtime compatibility | FAIL — not run | Source/requirements equality is preserved; actual installed versions and candidate compatibility under that runtime remain unverified. |
| Selective deployment procedure | PASS — source/API contract only | Official CLI has direct `EnvironmentPatchCommit` distinct from `EnvironmentPatchCommitStaged`. Exact two-service patch is prepared; authenticated execution and backend preservation were not tested. |
| Billing/credits/remaining budget | FAIL — unavailable | Connector exposes metrics, not billing; no authenticated CLI/token locally. No browser fallback was used. |
| Historical protection / source behavior | PASS | Seven production volumes and four staged changes retained; package source behavior attestation remains valid. Native wall-clock overhead is not yet qualified. |

Here FAIL includes absent required evidence, not a claim that an unexecuted
test failed. These failures prohibit the diagnostic authorization request.
The mounted lease test also cannot establish crash durability of SQLite; the
earlier concurrent corruption remains unresolved and one-reader containment
must remain mandatory.

## What was completed

- Refreshed read-only Railway environment, staged patch, research state,
  one-hour producer metrics, workspace identity and rollback-build availability.
  Both current producer deployments report `canRollback=true` and
  `canRedeploy=true`; refresh these flags again immediately before approval.
- Verified that the old research command would rerun bounded-reader research.
  It must **not** simply be restarted. Neither it nor any other service was started.
- Inspected official Railway CLI commit
  `05ed159796ef6bf15de0dab388b1054c1af6f395`. `environment edit` without
  `--stage` submits the supplied JSON directly; it does not invoke the staged
  commit mutation. The published schema distinguishes the supplied-patch and
  staged-patch operations. `SELECTIVE_ROUTE_SOURCE.json` records exact source
  blob identities and the limits of this verification.
- Prepared `ACTIVATE_NOT_AUTHORIZED.patch.json` and
  `ROLLBACK_EXACT_SOURCE_NOT_AUTHORIZED.patch.json`. Only MAIN/V81 source pins,
  approved start-command pins and recorder variables occur in these patches.
  The shadow service, volumes, shared variables and other settings are absent.
- Prepared `probe.py`: one strict-host-pinned read-only SSH attempt per producer,
  seven runtime identity fields including deployment/source, two statvfs samples,
  Python/dependency versions, 36 MAIN / 17 V81 application-source hashes, and the
  **existing** mounted lease test. No native owners are imported, no market
  requests are made and no evidence DB is opened. This probe has not run natively.
- Five new offline safety tests passed in 0.002 seconds. They cover wrong-target
  rejection before subprocess/receipt creation, pinned-host/no-retry transport,
  remote identity failure, storage/dependency non-passes, and production-patch
  scope. Existing 52 packaging/recovery checks were reused, not rerun. Neither
  packages nor the 600,000-record capacity test were rebuilt.

## Immutable packages and deployed identities

| Role | Candidate commit | Existing deployment | Candidate manifest SHA-256 |
| --- | --- | --- | --- |
| MAIN | `e2294683d2ec268d921df0277f5a9cb518f2e67d` | `c0993600-34b7-4501-92cd-b8d4a934b68a` | `a31e1bd814771aaf678538e4d0f552f71ba8bc60a23dfad47fa78ae37121174d` |
| V81 | `f7c32d04556335632c862515a9ee1b742ad88ad3` | `21bf7fd3-c294-46d9-8a0a-f551cce7a303` | `02aedccf31ceec8507900a93f1635d90ccbd9064fea9203599ab0d2c1e4eee8c` |
| Information | MAIN candidate, same worker | MAIN deployment | MAIN manifest |

Package identities are `BTC15_NATIVE_DIAGNOSTIC_MAIN_20261017`,
`BTC15_NATIVE_DIAGNOSTIC_V81_20261017` and
`BTC15_NATIVE_DIAGNOSTIC_INFORMATION_20261017`.

Archive SHA-256 (deterministic installer archives, not GitHub codeload tarballs):

- MAIN/information, 24,567,912 bytes:
  `f04b5e667e9d7dd958fb171bdf57c5e136ce768ff6e5d62a99aad4f62e53e73c`.
- V81, 24,550,761 bytes:
  `abf1d1cffcfdcd9555f30099a3175954a6edbbbb8fa2eaf84dda4dfebbec5c1c`.

Original source commits remain MAIN
`dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72` and V81
`c14b3f9b04caea13e62bcdd6fb0e5990049aa17b`.
[Existing package receipt](../native_diagnostic_20261017/PACKAGES.json) retains
the full comparison: 903 MAIN / 889 V81 unchanged files, all native strategy,
Kalshi, settlement, order, entry and timing logic unchanged. Source remains
signal-only, orders false. Runtime dependency and hook overhead claims require
native evidence; source equality alone is insufficient.

## Storage decision and cost

Every producer must have **2,181,038,080 actual available bytes**: 2 GiB reserve
plus 32 MiB compressed capture. MAIN combines its 16 MiB and information's
16 MiB. Add a reviewed allowance for native-journal growth during installation,
startup, capture and drain; the capture cap does not bound native journals.
Use `f_bavail * f_frsize`, rather than total blocks or allocation minus metrics.

| Producer | Allocation | Current disk metric | Nominal unused bytes, NOT actual free |
| --- | ---: | ---: | ---: |
| MAIN | 20,000 MB | 11.700629504 GB | 8,299,370,496 |
| V81 | 5,000 MB | 3.219357696 GB | 1,780,642,304 |

V81's nominal deficit is **400,395,776 bytes** before native growth and
filesystem uncertainty. Do not authorize a blind resize. After actual free
space `F` and approved growth allowance `G` are known, choose the smallest
provider-supported increase `D` satisfying `F + 0.97 D >= 2,181,038,080 + G`.
The 3% incremental metadata allowance is a planning assumption, not a guarantee;
recheck actual free bytes after any separately approved expansion.

A **conditional** 5,000→6,000 MB expansion adds 1 GB gross and leaves about
569.6 MB above capture/reserve after 30 MB metadata, using today's metric
estimate. It is sufficient only if measured free space and growth validate it.
The minimum supported allocation increment has not been verified. No expansion,
new volume, deletion, remount, quota change or shrink is proposed for execution.

Railway publishes $0.15/used-GB-month for volumes and bills used storage,
including filesystem metadata, rather than empty allocation. An extra 1 GB
therefore costs at most **$0.15/month when fully used**, approximately
**$0.003–$0.0045/month** for 2–3% metadata alone. Additional 64 MiB diagnostic
producer evidence costs about $0.0101 per full month retained, excluding its
research copy, database and native-journal growth. All prior volumes continue
to incur their existing used-storage charges.

The prepared research-only probe at the existing 4-vCPU / 8-GB limits has a
five-minute compute planning ceiling of **$0.01850**, using published container
rates. Proposed incremental allowance: **$0.03**, not an enforced account cap;
the process deadline is 180 seconds and no restart loop is allowed. This excludes
all ongoing services, historical storage, subscriptions, tax and other usage.
Failure to exit requires an operator stop of this research job only.

**Current bill, credits, plan and spend limits remain unknown.** The observed
one-hour average RAM usage of the two producers totals 3.684246 GB: if sustained
for a month, RAM alone would be **$36.84 before credits**, excluding CPU, all
storage and other services. This conditional run rate is not a measured bill or
forecast; it demonstrates why the preferred $20 budget cannot be assumed safe.
`STORAGE_COST.json` distinguishes every measurement, projection and missing value.

Official references: [pricing](https://docs.railway.com/pricing/plans),
[volume billing/metadata](https://docs.railway.com/volumes/reference),
[usage CLI](https://docs.railway.com/cli/usage),
[staged changes](https://docs.railway.com/deployments/staged-changes).

## Smallest next actions — separate authorization required

1. Authorize **one research-only operational run** on the existing service and
   volume, using this report's published commit and the exact command in
   `OPERATOR_PLAN.md`. This is necessary because the authenticated key and pin
   reside on the stopped research volume. It permits production read-only SSH,
   the existing lease probe and a new research receipt only. It does not permit
   a production change, capture, resize or evaluation. Proposed incremental
   compute allowance: $0.03, subject to verified account headroom.
2. Supply current workspace usage/credits/limits through an authenticated
   read-only Railway account session or authorize a read-only billing-dashboard
   fallback. No secret should be pasted into chat. The connector cannot retrieve
   this information and a CLI session is not configured here.
3. If measured V81 space fails, request a **separate exact volume expansion**
   with the measured minimum target, incremental cost and post-resize check.
   All seven historical volumes and all evidence remain in place.
4. Resolve any native dependency/source mismatch before deployment; run the
   already prepared compatibility checks in an isolated matching runtime.
   No replacement validator or new service is required. The research probe
   gathers prerequisites; it does not certify candidate imports/hook behavior.

Only after all operational gates pass may the 60-second authorization be
presented. The [existing diagnostic procedure](../native_diagnostic_20261017/DIAGNOSTIC_PROCEDURE.md)
continues to govern capture, strict loss/timing checks, sealing and evidence
transfer. `OPERATOR_PLAN.md` adds the precise selective patch route, its
authorization boundary and rollback. No automatic transition to the 20-minute
preflight or fixed 10-hour EARLY evaluation is allowed.
