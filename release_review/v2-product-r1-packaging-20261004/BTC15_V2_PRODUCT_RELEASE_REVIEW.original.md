# BTC15 V2 coordinated offline correction candidate

Revision: `BTC15_V2_PRODUCT_20261004_R1`. Strategy: `BTC15_LADDER_COMPLETION_20261003_V2`.

**OFFLINE CANDIDATE. NOT DEPLOYED. PRODUCTION DEPLOYMENT NOT AUTHORIZED.**
SIGNAL ONLY. MANUAL EXECUTION ONLY. NO ORDERS.

The release archive's `RELEASE_INDEX.json` binds the two local candidate commits, content manifest and incremental git bundles. Both commits add an overlay; no pre-existing tracked file changes. Do not deploy from a moving branch name. This document describes a candidate for review, not a completed live correction.

## Findings preserved

- Historical cohort: 41 production contracts, 38 jointly settled, zero strict fully scoreable. Settlement links all 38. No demonstrated committed SQLite record loss.
- MAIN: 35/37 post-startup settled contracts fail an edge; 54 internal gaps exceed 15 seconds across nine contracts. Forty-nine gaps show fresh-at-cutoff evidence followed by delayed publication; five overlap quote waits.
- V8.1: better observation cadence, but genuine source unavailability remains. Forced ticker bootstrap was an avoidable unavailable observation; natural empty books, missing targets and stale causal inputs still fail closed.
- Strict completeness remains sticky after any unavailable observation and requires both lanes. Administrative evidence and descriptive diagnostics do not qualify a performance cohort.
- A five-second MAIN evaluation cadence and a five-second BRTI freshness limit can still produce true expiry between publications. The candidate withdraws guidance without concealing expiry. It does not promise continuous action availability.

## Coordinated changes

1. `btc15_v2_product/admin.py` and `runtime.py`: bounded START/FINISH administrative attempts plus native stage and publication clocks, outside strategy inputs. Link accepted native offers to original journal sequences. Distinguish skipped attempts, exceptions and commit health. Queue/disk failures remain explicit. Asynchronous administrative accounting is best effort; a hard kill can precede its commit.
2. `bootstrap.py`: prepare at most two instances of the original timestamped Kalshi provider. Preparation of the next official contract is limited to 30 seconds before open; the current unexpired book is never reset. This is a transport preparation window, not a new signal timing gate. Exact official metadata is re-fetched before native selection; target is not fabricated or copied from a prior window. The existing decoder, authentication, book validation, source timestamps, source definition and native consumption remain unchanged. No pre-open frame can qualify. Missing target/snapshot/source remains unavailable.
3. `quote_view.py`, `routes.py`: an atomic, small, same-provider executable quote view. Four prices, official identity, epoch/sequence, exchange/accepted/published/served clocks. No REST or last-price replacement, no faster strategy processing. Display polling is 500 ms; original six-second quote expiry remains mandatory. Browser receipts permit comparable-book versus DOM measurement, with explicit clock bounds.
4. `installer.py`, `panel.js`: one owner of V2 cards and current quote fields. Legacy chart/context code still runs, but its action-card lookups return detached nodes. Typed unavailable envelopes retain safe reasons and identity-only metadata; stale actionable fields are cleared. SCALP uses its own committed freshness and exact current identity. FINAL PASS/UNLOCKED dominates model probability. Obsolete diagnostic labeling is removed. Hide/pagehide abort requests; generations reject old responses; resume requires refetch. A monotonic server-clock floor prevents cached responses from renewing leases.
5. `journal.py`, `release.py`: approved new evidence revision, distinct deployment root, original schemas and scored retention, immutable build/deployment metadata, runtime epochs, explicit startup/restart-slot exclusion. Old evidence is not rewritten. Launch is locked by default, verifies the original lane freeze and candidate manifest, and checks exact service/project/environment/volume/build identity.
6. Existing `ops/btc15_v2_scoring/bridge.py`: original strict classifier and established scorer preserved. Add independently labeled recording/source/settlement diagnostics and an explicit reviewed-receipt context for the new partition. The historical default still rejects new product rows; the new partition rejects old/mixed rows. Fixture success remains blocked as synthetic.

## Semantic boundary and evidence

All 697 pre-existing MAIN files and all 607 pre-existing V8.1 files match their respective frozen commits byte for byte. Original freeze verification remains mandatory. Source/model/dependency hashes receive additional release pins. The established scorer hash is `9812c23a6200bf31c2c5eb4e8f317fe32cfcafefeaa37d2a9b9a041967447d1a`.

EARLY retains ask <=45 cents, fair >=75%, 2-10 minutes and absolute gap >=$25. FINAL remains independent. SCALP retains original ask -> strictly later same-side bid, +5-cent arm, 4-cent giveback and 180-second policy. BRTI <=5 seconds, BTC <=10 seconds, quotes <=6 seconds, capture <=15 seconds and original close-time bounds are unchanged. No entry, model weight, confirmation, protection or EXIT policy is changed.

Differential tests compare full frozen MAIN native state/functions and V8.1 native iterations, processor record/state outputs, original offers and sleep cadence. Identical input decisions yield identical strategy results; additive metadata is compared separately. Preparation intentionally changes source readiness, as approved for offline testing; it does not establish that future live input sequences or availability will be identical.

## Qualification and limits

See `qualification/v2_product_20261004/qualification_summary.json` and individual logs. The suite includes frozen logic/source gates, new bootstrap/journal/cohort tests, unchanged bridge tests and actual assembled HTML with all legacy scripts active in JSDOM.

- Real processors -> persistent SQLite -> consistent snapshot -> existing bridge: one, then two fully scoreable settled **fixture** contracts. Production claim remains blocked (`SYNTHETIC_FIXTURE_ONLY`).
- Four errors in the older V8.1 test module reproduce on the exact frozen V8.1 checkout: stale fixture calls to removed publish functions and an omitted required BTC source timestamp. The original test file is preserved; 19 current source-contract tests cover the existing runtime API and unchanged gates. These are test-fixture repairs, not strategy changes.
- Full assembled DOM integration passes ownership, stale/unavailable handling, independent SCALP, high probability with PASS, actual later-bid EXIT output, delayed replies, cached timestamps, hide/resume and rollover. A synthetic comparable 3-cent quote move reaches the displayed prices with zero post-render price delta. This is not a measured production-lag claim.
- Rendered browser validation was blocked by the browser security policy for both local HTTP and file preview. No alternate browser workaround was attempted. JSDOM has no layout engine and is not Safari. Responsive visual layout and physical iPhone/iPad Safari remain unverified.
- D04 profiling used exact pinned dependencies, 50,416 candle rows and 241 native ticks. Initial 40-sample profile excluded the optional legacy shadow model; a follow-up reconstructed its original startup training from the exact frozen 1,474-row CSV. Ten complete loops with that model took 48.226-59.950 ms locally. One prediction sample reached 74.684 ms; no 9-24-second production stall was reproduced. **No optimization was selected.** Production resource contention, network and disk conditions are not reproduced. The inner cause of the 49 production stalls remains open; candidate stage evidence is the next measurement, not a claimed fix.

## Ordered release gates

Reproduce offline in a separate checkout using Python 3.12 and the unchanged `requirements.txt`. Install only the test harness with `npm ci --ignore-scripts --prefix ops/v2_product`, then run `python -m ops.v2_product.qualify_offline --lane main` on the MAIN candidate and `--lane v81` on the V8.1 candidate. These commands do not launch production. The exact JSDOM dependency lock is included; it is a development dependency only. Stage benchmarks are separately reproducible with `python -m ops.v2_product.profile_stages` and `python -m ops.v2_product.profile_shadow`. Read benchmark limitations before interpreting them. No generated model is promoted.

1. Review this package, the original 18-defect matrix plus candidate disposition, manifest and hashes. Finish rendered assembled-page checks in an authorized browser environment, including iPhone/iPad Safari. Keep the D04 limitation explicit. This package does not satisfy those blocked gates.
2. Obtain Eric's explicit production approval for these exact two commits and manifest. Any changed strategy/source/evidence definition outside approved D02/D13 requires separate review. Never silently waive a failed gate or replace a fixture result with a production claim.
3. Before any approved deployment, capture existing service start commands, selected source commits, environment-variable names/values relevant to this change and volume identities securely. Save consistent read-only old journal snapshots through the existing workflow; never edit or copy raw live WAL files as a snapshot. Keep secrets out of the review package.
4. Publish only the reviewed local candidate commits if authorized, with auto-deploy behavior inspected first. Deploy as one coordinated release on the existing two production services and existing volumes; do not alter the shared BRTI owner, create a service, retire a process or change data-source credentials.
5. Per lane, use the existing `/data` volume guards followed by `exec python -u btc15_v2_launch.py --lane main --run-reviewed-production` or `--lane v81`. Retain the existing MAIN `BTC15_ENABLE_INFORMATION_EXPORT=1` opt-in. Pin `BTC15_V2_APPROVED_MANIFEST_SHA256` to the release content-manifest hash and `BTC15_V2_APPROVED_BUILD` to that lane's exact reviewed commit. Do not supply an old `BTC15_LADDER_DATA_ROOT`; the gate rejects root overrides. These values authorize startup only, not scoring.
6. Record control-plane actual deployment IDs, commits, service/project/environment, volume IDs and first successful runtime start times. Do not reuse the frozen deployment IDs or invent IDs before allocation. Fill `release_receipt.template.json`, remove its template marker, set `evidence_class=PRODUCTION`, independently verify every identity, then hash the exact receipt. Runtime self-report alone is insufficient. Keep the reviewed receipt with the release evidence.
7. New data goes to `/data/btc15_v2_product/BTC15_V2_PRODUCT_20261004_R1/<actual-deployment-id>/`. Startup/restart slots are excluded. The common cohort begins at the first full 15-minute window strictly after both recorded starts. Paired snapshots preserve their individual cutoff times; do not imply simultaneous capture or mix deployments.
8. Perform the bounded live acceptance below. Update only the two existing task IDs using the prepared drafts after the handoff and actual receipt are committed. Preserve task schedules, known-incident suppression and existing notification settings. No duplicate watchers. Delivery is tested only through the existing path and requires Eric's actual receipt.

## Existing bridge commands after approval

Run the snapshot command within each approved lane container with the verified receipt file accessible; it validates actual runtime identity and uses SQLite online backup. Choose unique output paths. Transfer each detached `.sqlite3` together with its `.sqlite3.receipt.json` companion; preserve hashes. Do not write the snapshot into the live database path.

```sh
python -m ops.btc15_v2_scoring.bridge --release-receipt /reviewed/release_receipt.json --release-sha256 REVIEWED_RECEIPT_SHA snapshot --lane main --output /tmp/main-acceptance.sqlite3
python -m ops.btc15_v2_scoring.bridge --release-receipt /reviewed/release_receipt.json --release-sha256 REVIEWED_RECEIPT_SHA snapshot --lane v81 --output /tmp/v81-acceptance.sqlite3
python -m ops.btc15_v2_scoring.bridge --release-receipt /reviewed/release_receipt.json --release-sha256 REVIEWED_RECEIPT_SHA score --main /detached/main-acceptance.sqlite3 --v81 /detached/v81-acceptance.sqlite3 --output /detached/acceptance-score
```

The capitalized receipt hash is an explicit placeholder to replace after approval; the template cannot authorize deployment or scoring. Strict golden logic remains unchanged. Report recording, source availability, settlement, absent-lane tails and strict classification independently. Never count administrative rows as observations.

## One bounded live contract plus rollover

Choose the first common full window after both starts. Record exact official ticker/target/open/close and deployment identities. Verify source-time causality at native cuts and at publication; no future source data, synthetic frames or pre-open eligibility. Check administrative timing reconciles observed attempts and publications; report native attempt, successful publication, cutoff-to-commit and commit-to-served intervals separately, including quantiles and worst gap.

On the assembled dashboard, inspect readable stable cards, FINAL PASS prominence, independent SCALP, true expiry suppression, origin reset at rollover and SIGNAL ONLY / MANUAL / NO ORDERS. Check current four-sided quote projection against displayed UP/DOWN asks using the same ticker/epoch/sequence and clocks. Use bounded DOM receipts and read-only accepted-book observations; report source age, acceptance-to-publication, publication-to-render bounds and price delta. Reject incomparable tuples and do not assert exact one-way network lag from unsynchronized clocks. A new accepted 2-3-cent move must appear at the next successful display poll/render without extending the six-second lease. Record actual browser throttling and refresh delay; no universal latency SLA is inferred from fixture timers.

Hide and resume iPhone and iPad Safari during the window and across rollover. Require an unavailable state until fresh identity/data arrive. Check an old response cannot restore guidance. Observe actual EARLY/FINAL/SCALP behavior; a legitimate PASS/no-entry window is acceptable. Do not manufacture signals or manual fills to exercise states already covered by frozen replay tests.

After official finalized settlement, obtain the fresh snapshot pair and run the established bridge. Require at least one **real** fully scoreable settled contract. If source conditions or D04 still prevent this, report the exact blocker and stop; do not relax coverage, freshness or source definition, and do not launch a multi-day performance campaign. Obtain one later bounded checkpoint under the same receipt to confirm accumulation; pending remains pending until finalized. No reliability/profit claim follows from functional acceptance.

Verify journals survive normal operation, admin failures are visible, effective retention is explicit and the existing snapshot workflow captures before the earliest cap. Strategy journals remain 30 days OR 300,000 events; at one V8.1 event/s the count cap is about 3.47 days. The 96-contract route is not full history. Admin retention is separately bounded by 7 days, 100,000 records or 64 MiB payload; it cannot replace scored evidence. Check one labeled test notification through the existing alert path and obtain Eric's receipt. Actual delivery is pending until that occurs.

## Rollback

Rollback immediately for identity drift, altered frozen behavior, stale actionable guidance, journal failure, mixed evidence, unsafe bootstrap selection or failure to recover readable current state. A natural unavailable book is not permission to change eligibility.

Restore MAIN source `de4f3e20b8657eb8cfee91bd4e525c103b5bf513` and V8.1 `60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1` with the original start commands:

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && python btc15_verify_ladder_freeze_v2.py --lane main && exec python -u btc15_information_install_v1.py'
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && python btc15_verify_ladder_freeze_v2.py --lane v81 && exec python -u v81_30_45_live_feed.py'
```

Restore only settings changed for this release from the captured pre-deployment values; remove the new approval/receipt settings when absent before. Preserve both original and new evidence roots and both detached snapshot pairs. Never merge them. A rollback creates new actual deployment IDs: historical strict allowlists must not silently admit rollback events. Stop new-cohort scoring and bind any future rollback scoring to a separately reviewed receipt. Restore the previous task prompts only if the candidate prompts had been activated. Verify frozen hashes, original source identities, source availability and no orders after rollback; do not claim rollback restores strict scoreability.

## Operations disposition

Alert draft updates target only `6a9a3752ab6c8191a728578348df6984` and `6aa3fd90bebc81918d82ff88676fd928`. They are inactive files, not task mutations. D16 remains inventory-only; no service retirement or cost-saving claim is made. No production deployment, restart, task update, user notification, order or execution occurred while preparing this candidate.
