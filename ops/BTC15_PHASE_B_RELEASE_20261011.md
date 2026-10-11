# Phase B release preparation — 2026-10-11

Production activation remains unauthorized. PR #67 stays open and unmerged.

## Identity and packaging

Initial remote repair HEAD was resolved to
`4b36ccd97bafc8aeb94a8527cdd3824a41f278ac`, not assumed from the handoff.
PR base is `2f1901006296b45fbd93a1d73c9a08df62357939`.
The release candidate is the commit containing this document and its sealed
manifest. Resolve and record its full SHA before any authorized deployment.

The reviewed and now committed `BTC15_V2_PRODUCT_RELEASE_R1.json` SHA256 is
`e8d8a1b54ff9ea3850296567ee8921149e5ea07697144b7bbeb41ea382045949`.
This is byte-identical to GitHub manifest-review artifact 11693498066 from run
38116019318. That original artifact ZIP digest is
`8edde69f9bbb67a117db712c121f9742ab4f7ebe3f711971ffe3a7efcb9dc2b2`.
All 46 release files and 9 MAIN protected files match. The original freeze
manifest and verifier remain mandatory and unchanged.

Two packaging defects were corrected, without changing strategy/runtime code:

- The release manifest still named the old handoff hash; it now seals the
  reviewed `early_origin_transfer.py` at
  `d8d89249e1189e89e89bceae311ef026257bae447268c5bafc40495c39be492d`.
- The cockpit hosting manifest still named the old conflict-explanation code;
  it now seals `trade_records.js` at
  `9163cd75a91c6f4cbf95de463d5869c39af2aeeeaa49f526adedfe03dbf9f181` after the display-only reconciliation below.

The manifest workflow now checks the exact PR head, installs pinned dependencies,
requires candidate/committed manifest byte equality, checks all cockpit hashes,
and runs current authorization, journal restart, source and startup regressions.
No strategy safety assertion was removed. The broad workflow was not weakened.

Read-only control-plane inspection also found the dedicated cockpit at build
4750954bbe1415712950a1b20db3bbf7a1c448aa (deployment
2868eadc-e36b-41de-814b-1927572515c5), ahead of this branch in FINAL history and
compact completed-EXIT display. Its stale “One BUY per contract” message and
five EARLY action rows contradict the approved lifecycle. The candidate now
preserves that deployed renderer, verified FINAL history owner, compact details
and styles, while retaining the approved three EARLY states and distinct reentry.
The exact new EXIT publication highlights once; completed recommendations retire
to history and cannot create action authority. Existing conflict rejection is
retained. Authentic candidate-native fixtures verify a second distinct BUY,
prior history retention, three EARLY rows, WATCH/could-flip, expiry, rollover,
100-render stability and unchanged SCALP states. Presentation assertions now
follow the deployed compact UI; no source-expiry/origin-binding gate is relaxed.
The dedicated read-only cockpit needs its own explicitly approved deployment
of these sealed assets; a MAIN-only deployment cannot update that separate app.

## Strategy and history

EARLY, SCALP, FINAL, the frozen native model, source clocks, thresholds and
protected files are unchanged from the approved PR base. EARLY still requires
causal directional corroboration, covers the contract without an artificial
entry-window/count cap, and permits another distinct BUY after EXIT plus a
new unqualified-to-qualified opportunity. Duplicate native decisions fail
closed. User-facing management remains BUY / WATCH (could flip) / EXIT.
SCALP owns short-duration UP/DOWN opportunities and its own lifecycle. Momentum
alone does not establish an executable profitable scalp. FINAL's standalone
publication and protected qualification remain independent. All paths remain
signal-only, manual execution only, orders=false.

Completed real-snapshot evidence is accepted from the user's explicit handoff:
both existing historical SQLite snapshots passed; 62,984 events and all eight
saved BUY/EXIT identities were preserved in each. The original snapshots were
not downloaded, modified, or rerun. This session adds synthetic current-journal
handoff/restart checks; it does not claim to have re-observed those private files.
The old maintenance deployment still logs HANDOFF_MISSING_HISTORY because it
runs the old code; that is not a failure of the repaired snapshot campaign.

## Regression disposition

Identical 109-test selection covering every failing module was run against
PR base 2f19010, initial head 4b36ccd and the sealed candidate with the same
Python 3.12.14/pinned dependencies. Results:

| Build | Tests | Failures | Errors |
|---|---:|---:|---:|
| PR base | 109 | 31 | 13 |
| Initial repair head | 109 | 32 | 13 |
| Sealed candidate | 109 | 31 | 13 |

The sole new failure was release-file mismatch before the authorization test;
sealing the reviewed manifest removes it. Every remaining local failure record
is shared with the baseline. Baseline full discovery also ran 655 tests with
31 failures / 13 errors. Initial-head GitHub discovery ran 656 tests with
32 failures / 15 errors. The extra two GitHub errors are `/data` permissions in
live-delivery test setup; current focused CI uses a temporary BTC15_DATA_DIR.
A local initial-head full-discovery attempt was interrupted after stalling;
it is not counted as a completed run. The identical failing-module comparisons
completed on all three revisions.

Root causes, rather than baseline status alone, were inspected:

- Legacy processors emit the older BTC15_LADDER_COMPLETION candidate identity;
  current public_view correctly rejects them as JOURNAL_UNAVAILABLE. Resulting
  missing journal/guidance and lease assertions are obsolete fixture failures,
  not evidence that the current journal lost data.
- Two journal/cohort fixtures supply production-like deployment IDs without
  creating the now-required predecessor journal. Read-only handoff rejects the
  missing source. Never bypass this guard in production.
- Old receipt fixtures use the scoring bridge's older strategy identity and
  therefore reject before their intended lane-field assertion.
- Extracted-loop fixtures omit the installed `_v2_timing` namespace. Actual
  startup installs it through prepare_main. Current fair-startup/recovery tests
  exercise native recovery and contract rollover.
- Old revalidation tests demand CONFIRMED/PENDING, renewed authority or latching.
  The accepted informational evaluator uses AGREES/CHANGED/REFRESHING and never
  renews/revokes native authority. Current NativeAuthority tests verify this.
- Old EARLY fixtures lack required directional corroboration and expect an
  origin anyway; old SCALP fixtures expect momentum-only entries despite the
  existing net-economics guard. Relaxing strategy guards to satisfy them would
  contradict the approved architecture.

Local release evidence: 96 focused Python tests passed (including five new
release/startup/journal checks), seven additional protected-boundary and native
independence tests passed, all four cockpit Node suites passed, all 16 cockpit
package checksums passed, and the actual committed MAIN release verifier passed.
The five new gates include tampered-file rejection, missing-approval rejection,
all startup identity mismatches, synthetic actual RevisionJournal transfer,
same-deployment restart, distinct reentry, source expiry, closed-contract loss
of authority, and foreign-build refusal without changing the source journal.

## Verified Railway inventory

- Project noble-warmth: baea4e22-d004-4434-b2c5-81a7fbc05086.
- Environment production: 61775c5d-c583-4dfc-af41-f25578856fd9.
- MAIN Btc-15min-bot: ab28dca6-7bea-4956-bdb9-dbb7b4c74635.
- Current deployment: a8a034da-d1c5-487c-a5cf-42756423cba0, SUCCESS, 1 running replica.
- Current pinned maintenance build: 2f1901006296b45fbd93a1d73c9a08df62357939.
- Current manifest: 4bd064b314055daa01492ecae2615e4048b703c9b0f9b4474a9d481ddf848684.
- Original volume 6ced6b1a-3755-4518-a240-c895e936d443 at /data, iad, 10,000 MB.
- GET /health returned mode=MAINTENANCE_NO_SIGNALS and orders=false.
- MAIN has no staged service changes.
- Environment patch ead9997e-b5b7-4668-a612-e8417e197838 contains exactly four
  source-field changes on shadow service 84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1.
  Preserve the patch and its branch/commit/image/repo fields unchanged. Never
  call environment-wide accept-deploy to activate MAIN.
- Independent SCALP service 6025e83e-a41c-4e0a-8c16-f71120bd501b remains at
  build 6e04aced0f718b29f8ed805abcc0f76b01ed5096, deployment
  49b01605-2a56-4ff5-b55e-332adf4b5b11. This preparation does not deploy it.

## Startup preparation — do not execute until separately approved

Set CANDIDATE to the reviewed full commit SHA. Set only MAIN's startCommand,
with explicit project/environment/service scope and no deploy while configuring:

```sh
/bin/sh -c 'set -eu; test "$RAILWAY_VOLUME_MOUNT_PATH" = /data; test "$RAILWAY_VOLUME_ID" = 6ced6b1a-3755-4518-a240-c895e936d443; test "$BTC15_ENABLE_INFORMATION_EXPORT" = 1; test -n "$KALSHI_KEY_ID"; test -n "$KALSHI_PRIVATE_KEY_B64"; unset BTC15_LADDER_DATA_ROOT BTC15_COHORT_EVIDENCE_PATH BTC15_ARCHIVE_LEGACY_ONCE BTC15_V2_RELEASE_RECEIPT BTC15_V2_RELEASE_RECEIPT_SHA256; export BTC15_V2_APPROVED_BUILD=CANDIDATE BTC15_V2_APPROVED_MANIFEST_SHA256=e8d8a1b54ff9ea3850296567ee8921149e5ea07697144b7bbeb41ea382045949; cd /app; exec python -B -u btc15_v2_launch.py --lane main --run-reviewed-production'
```

CANDIDATE is a deliberate review placeholder in this versioned runbook; the
final external readiness report supplies its exact value. Never substitute
HEAD or a moving branch name at activation. Do not persist fake Railway IDs.
Railway must supply the actual project/environment/service/deployment/git/volume
IDs; verify_environment compares each value and enforces the original volume.
Keep /health on port 8080, timeout 120 seconds, one iad replica. Preserve the
existing volume attachment, variables and unrelated fields.

Required runtime configuration to verify before approval: PORT=8080,
BTC15_ENABLE_INFORMATION_EXPORT=1, existing valid KALSHI_KEY_ID and
KALSHI_PRIVATE_KEY_B64 (check presence/authentication without revealing values),
BTC15_USE_SHARED_BRTI, BTC15_BRTI_TRANSPORT, its matching existing
BTC15_BRTI_GATEWAY_URL or BTC15_BRTI_SHARED_URL, and BTC15_V81_LADDERS_URL pointing
to the independent approved SCALP /ladders service. Preserve source configuration;
do not invent replacements or create credentials. The connected Railway OAuth
inspection returns variable names only. Actual nonsecret values and current
runtime source configuration have NOT been verified in this session.

## Controlled activation procedure — approval required, no cutover performed

1. Resolve repair HEAD again; require the exact reviewed commit, manifest and
   passing release-specific CI. If any changes occur, stop for a new review.
   Merging PR #67 needs separate authorization and is not required for a pinned
   candidate deployment.
2. Complete read-only runtime-variable inspection. Record nonsecret source URLs
   and flags, credential presence, current free-space headroom, and the exact
   current MAIN maintenance start command. No historical backup campaign.
3. Re-read MAIN deployment, volume and the four-field shadow patch. Freeze those
   observations into the deployment receipt; abort on identity drift.
4. Obtain explicit approval for MAIN activation and the separate read-only
   cockpit display update with this exact commit and manifest. Deploy the
   cockpit assets first while MAIN is still in maintenance; preserve its
   /cockpit_candidate root, existing build/start commands, host variables and
   /index.html healthcheck. Confirm history-only maintenance display and all
   exact package hashes before authorizing the MAIN step. If the cockpit gate
   fails, roll it back to 4750954 and leave MAIN in maintenance.
5. Use a MAIN-only configuration update (explicit environment, staged=false),
   which takes effect on its next deployment; do not accept any environment
   patch. Read back the exact startup command and unchanged volume/patch.
6. Trigger one MAIN-only deployment pinned to the reviewed commit. The source
   connector's live connect affects that service in all environments: first
   prove MAIN has no other environment instance, or use an authenticated
   environment-scoped deployment route. Do not execute a global source change
   while that scope remains unverified. The current list-services inspection confirms this
   project has only the production environment; recheck immediately before the
   authorized source connect. Never deploy a moving branch head.
7. Observe deployment SUCCESS and runtime build/manifest/volume/deployment
   identity. Capture the newly assigned deployment UUID; do not pre-invent it.
   Confirm only native/dashboard/information owners, signal_only=true,
   orders=false, no legacy collectors, no archive trigger.
8. Confirm origin_transfer names predecessor 4b33134d-d832-409e-bf35-f80689beb66b
   / build 6d5897c26fc83e62a5425148a773d648dfcbacde; history count/identities
   reconcile with the completed eight-record evidence; publication_imported=false.
   Expired origins must not regain action authority.
9. Observe /health, /ladders, /ladders/quotes, /ladders/coverage and /information.
   Healthy HTTP alone is insufficient: exact official contract/target/window,
   original source times, increasing native/journal sequences, valid book and
   current model must agree. BRTI <=5s, quotes <=6s, BTC <=10s; expiration never
   extends past the original source deadline or official close. Genuine missing
   sources must display unavailable, never fabricated freshness.
10. Observe an official 15-minute rollover: old contract loses action authority,
    new identity/target match native sources, history remains historical, no
    duplicate BUY/EXIT, no pre-open authority. This is a bounded post-cutover
    operational check, not another historical or performance campaign.
11. Recheck the shadow patch and volume, then issue a control-plane-verified
    deployment receipt. Runtime-only identity is insufficient for scoring.

## Restart and rollback

Same-deployment restarts reuse the deployment-specific journal at
/data/btc15_v2_product/BTC15_INTEGRATED_OFFLINE_20261006/<deployment>/main.sqlite3.
Existing state/origin_transfer makes the handoff idempotent. Startup slot is
excluded from scoring. No restart was performed here.

Rollback target is the current NO-SIGNAL maintenance deployment/build above,
not an older active strategy build. Save and use its exact current startCommand
and manifest authorization together with build 2f19010. Railway reports this
existing deployment can redeploy/roll back. Review the service-only rollback
preview; never assume rolling back an image also restores config. If necessary,
restore the saved maintenance command as a scoped config change, then redeploy
that exact known build. Confirm /health is MAINTENANCE_NO_SIGNALS, orders=false,
all writers stopped, original volume attached, and four shadow changes unchanged.
Preserve the new candidate journal and original journal; never copy a database
back over either of them.

Important: a new deployment UUID creates a new root, and the current handoff
names a fixed predecessor. After an active candidate has written new history,
do not redeploy/re-activate as a new UUID and assume it imports those newer
records. Remain in maintenance until a separately reviewed handoff from the
latest candidate journal is prepared. Same-UUID restart is distinct from a new
redeployment. No data restore, volume detach or history deletion is a rollback.

## Release decision

BLOCKED for production activation pending read-only verification of actual
production variable values/source configuration and current storage headroom.
Environment scope was verified as production-only. Final candidate CI must also
complete after this preparation commit. Dedicated cockpit deployment is a
separate, explicit part of the future approval scope.
The safest next step is scoped read-only inspection, not a restart, deployment,
backup rerun, strategy retune or broad research campaign. Then obtain explicit
production approval. No production operation is authorized by this report.
