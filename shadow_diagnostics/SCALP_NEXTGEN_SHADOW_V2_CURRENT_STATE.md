# CURRENT STATE — V2 deployment, September 16, 2026

This Work thread remains the sole engineering/control authority. This operations branch stores deployment records only; do not deploy it. The running source is `scalp-nextgen-shadow-v2`.

## CONTROL

Only failed legacy `v81-30-45-live-feed` was deleted, by the user through Railway's staged-change confirmation. Verified 49 services and no remaining staged changes before creation. Replacement `v81-30-45-live-feed-v2` remains SUCCESS, deployment `ae6976a2-fb93-449a-a05d-f45dc32bd478`. Comparing all 49 pre-existing service deployment IDs before and after V2 creation found zero changes. No frozen collector was edited, stopped, restarted, or given new variables.

## NEW SHADOW

- Service: `scalp-nextgen-shadow-v2` (`46b79a18-0fc2-46f0-8f12-d6bac63eecad`).
- Railway project: noble-warmth; environment: production. This environment name does not change the service's shadow-only role.
- Deployment: `17cac03e-20a2-46be-b535-c31f63aaf6fa`, SUCCESS.
- Commit: `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`, branch `scalp-nextgen-shadow-v2`.
- Code/config/dependency fingerprint: `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f`.
- Fresh development-comparison cutoff: **2026-09-16 22:30:00 UTC / 6:30 PM Eastern**.
- Window ID: `00e73c80479a5ec5d482d33429e5f2115513dcddd93babdf38a7e38c6b7cac67`.
- One replica, no attached volume. Read-only export URL/token are Railway references to the existing economics control's export configuration. No trading credentials added.
- [Health](https://scalp-nextgen-shadow-v2-production.up.railway.app/health), [readiness](https://scalp-nextgen-shadow-v2-production.up.railway.app/ready), [state](https://scalp-nextgen-shadow-v2-production.up.railway.app/state), and [audit](https://scalp-nextgen-shadow-v2-production.up.railway.app/audit) returned HTTP 200.
- All 27 startup tests passed in Railway. Real server startup and first source read followed the test output. Deliberate failure messages before the START marker belong to regression tests, not live collector errors.
- First real poll at 22:13:15 UTC: 373,581 source rows; source timestamp age about 8 seconds; all integrity checks passed. Four families / 24 lanes: SCALP-2 4, Verify 6, Watch 5, Pullback 9.
- Zero eligible full contracts and zero serial signals before the cutoff. No live V2 economic or timing result is established.

## Deployment issues resolved

Railway's create-deployment tool was explicitly given the V2 branch, but its first deployment selected main. The new service's explicit V2 start command prevented that image from starting the production bot; it failed on missing V2 test files. Only this new service was configured to correct the deployment. A documentation-only commit triggered the configured V2 branch.

The next build's startup gate found a test that assumed the code-pin environment variable was missing. Corrected that single assertion to explicitly supply an empty pin, then reran all 27 tests with Railway-equivalent settings. Experiment rules and frozen helpers were unchanged. That test-file change altered the fingerprint, so the pin was updated before any admitted sample. The old `ec18e...` fingerprint in earlier draft documents is superseded for this deployment.

Failed startup attempts: `60df0b1e-74dd-4b8c-852e-68336bee4288` (wrong initial branch), `cfc1e602-aeb9-4429-aa51-30113ce752e5` (environment-dependent test). Neither is the accepted V2 deployment.

## BLOCKED

No user action or service-slot blocker remains. Performance evaluation awaits eligible post-cutoff observations. The 100-contract / 100-signal overall floor is not per-lane sufficiency or a promotion gate.

## NEXT STEP

Confirm continued successful polling and evaluate the first fully observed post-cutoff contracts against the frozen V1 policies on matching opportunity IDs. Preserve this source commit, configuration and cutoff. Keep any subsequent engineering on another undeployed branch. No orders, production logic changes, automatic promotion, or same-sample promotion. Any candidate must later pass a separately frozen prospective certification window.
