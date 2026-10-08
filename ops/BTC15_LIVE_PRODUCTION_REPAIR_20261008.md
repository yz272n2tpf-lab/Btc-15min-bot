# Live product repair — October 8, 2026

Authorized scope: existing production MAIN and cockpit; pause redundant
qualification collection without deleting evidence. Signal only, no orders.

## Changes

- Render native PASS/lifecycle reasons, model assessment, BTC spot, BRTI and
  indicators in actual visible fields. Keep original source-owner deadlines,
  native action resolution and both protected five-rung ladders unchanged.
- Route SCALP through a fixed same-origin TLS relay; forward original source
  bytes and timestamps without caching, renewal, arbitrary URLs or credentials.
- Compact responsive layout. `/responsive.html` contains the actual live cockpit
  in a 390-by-844 CSS-pixel iframe for browser inspection; no simulated source.
- Production MAIN owns exactly native MAIN, the publication server and isolated
  information worker. Retire duplicate rescue/parity/validation collectors.
  Unexpected required-child exit restarts the owned group. Suppress successful
  HTTP access-log repetition. Inventory volume usage read-only every five minutes.
- Pause obsolete MAIN qualification collector using a service-ID-guarded health
  process. Preserve its mounted volume and all historical files.

No ladder thresholds, model bytes, official boundaries, input timestamps or
freshness limits changed. Native evaluation timing is unchanged. Removed
collectors are observational processes, not signal owners. Restart may briefly
make publications unavailable; no previous publication gains new authority.

Live follow-up: descriptive market fields no longer require an obsolete parity
collector's 45-second diagnostic receipt. Their original market/BRTI freshness
checks remain, and cockpit rendering still requires exact current native ticker,
target and official close. Snapshot refresh changes from five seconds to one
second, with one request at a time; this changes display delivery, never native
signal timing. Expired descriptive assessments may remain explicitly historical.

## Rollback references (control plane inspected before edits)

Project `baea4e22-d004-4434-b2c5-81a7fbc05086`, production environment
`61775c5d-c583-4dfc-af41-f25578856fd9`.

| Service | Previous build | Previous deployment |
| --- | --- | --- |
| MAIN `ab28dca6-7bea-4956-bdb9-dbb7b4c74635` | `5802d06ed267464bd17f546a3f95322bcc6482b6` | `89a08664-b836-4561-b07b-4c321ade71de` |
| Cockpit `b584a1cf-a951-4b54-9127-4826cedc3ccb` | `b1b4c5b1eaacb95293d7df7ec4fd804e4e7b2d40` | `de889d94-3732-4107-99b5-35d15195497e` |
| Qualification `e6101c69-18df-4522-99d8-94e363ad8b92` | `de4f3e20b8657eb8cfee91bd4e525c103b5bf513` | `49b15e63-fdf8-4dd6-9589-de222bbe5fdf` |

Rollback cockpit independently by reconnecting its previous pin and existing
branch `fix/btc15-live-cockpit-source-visibility-20261008`; retain root directory
`/cockpit_candidate` and existing build/start commands.

For MAIN restore the previous start command below, then reconnect previous pin
on `candidate/btc15-main-live-shadow-20261008` to create a correctly bound new
deployment. Keep existing service, volume and mount. Do not copy current action
authority across deployment identities. Verify current native publications and
the public browser following restart.

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && unset BTC15_LADDER_DATA_ROOT && export BTC15_V2_APPROVED_BUILD=5802d06ed267464bd17f546a3f95322bcc6482b6 BTC15_V2_APPROVED_MANIFEST_SHA256=45282a6f24e5a1616842883138aa3609f8fd3f841050a46f24fa015aa5e0d276 && exec python -u btc15_v2_launch.py --lane main --run-reviewed-production'
```

Qualification rollback (only if the obsolete collector is deliberately needed):
restore its prior release branch and build above, plus the command below. Its
historical full volume will still require an approved retention solution.

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && python btc15_verify_ladder_freeze_v2.py --lane main && exec python -u btc15_information_install_v1.py'
```

SCALP and shared BRTI builds are not changed by this checkpoint. The existing
uncommitted shadow patch is not part of this production deployment.

## Production result, 23:50 UTC / 7:50 p.m. Eastern

- MAIN: build `57f468063f31ec005f413e5032d147603c2e70c8`, deployment
  `39ecbc88-54bd-4122-94ee-303402d6bf11`, SUCCESS.
- Public cockpit: build `24a746dbc7aa8a0e17c821d5952f5751bb64e764`, deployment
  `2e3003a1-c9f1-4d10-a188-10689cf0bfb7`, SUCCESS.
- Qualification collector: same build as MAIN, deployment
  `5e144106-3663-4a26-9715-90875fa4db93`, SUCCESS; public health reports PAUSED.
- Native SCALP remains `a260810eb5ea76aa204225ac181e163dd4c80392`, deployment
  `7456f73f-c4f6-49d2-a5b0-4c99e26de790`. Shared BRTI is unchanged.

The real browser displayed the 7:45–8:00 official contract, exact target,
countdown, independently labelled BTC/BRTI prices, BRTI chart, verified Kalshi
prices, FINAL probability and PASS conditions, EARLY price/qualification,
both SCALP directions and native WATCH/PROTECT states, model information,
RSI/MACD/volume, evidence score and publication/journal health. Mobile-width
inspection used that same production app in a 390-by-844 iframe: body width
and scroll width both 375 pixels (vertical scrollbar included), all three
ladders retained five rows. No application JavaScript errors were observed on
the final fresh mobile load. Physical iPad/Safari remains unverified.

Live follow-up corrected a newly introduced absent-retained-record dereference
before final verification. The added actual-renderer regression covers empty
startup, identity arriving independently, qualified data, expiry and rollover.

Current-contract connection epoch stayed unchanged through the official close.
At 23:44:37 the quote book reported a missing bid side while BRTI and BTC were
CURRENT. MAIN published QUOTE_SOURCE_UNAVAILABLE, not a BRTI outage. The old
contract expired at 23:45; new qualified identity and quotes were present at
23:45:06. No pre-open next-contract quote gained current authority. These are
production observations, not a promise of uninterrupted exchange liquidity.

Protection checks: 28 focused Python tests passed; 13 source-owner scenarios,
85 checkpoints and 572 protected-render comparisons passed; fixed-source relay
and actual descriptive-renderer regressions passed. MAIN remained genuine PASS;
native SCALP changed sides and lifecycle states with actual market conditions.
No strategy performance percentage is inferred from these observations.

Read-only storage inventory at 23:50:40: 7,835,058,176 used bytes and
1,542,115,328 free bytes in the filesystem. The retired forward observer stayed
exactly 918,448,535 bytes across all three inventory samples. Historical volumes
and evidence remain; ordinary native/information evidence continues growing.
This is not a permanent retention solution. No data was manually deleted and
no storage or service was purchased. Existing bounded database maintenance was
not changed.

Raw control-plane, source-health and storage observations are in
`ops/evidence/20261008-live-production-repair.json`. Production services remain
pinned to the source commits above; this result-only checkpoint does not deploy.
