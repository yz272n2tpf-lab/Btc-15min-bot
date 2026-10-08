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
