# V2 activation attempt — 2026-09-16

CONTROL: User completed deletion of failed legacy v81-30-45-live-feed. Confirmed 49 services, no staged changes, replacement v81-30-45-live-feed-v2 SUCCESS. All existing collectors remain untouched.

NEW SHADOW: Created scalp-nextgen-shadow-v2, service 46b79a18-0fc2-46f0-8f12-d6bac63eecad. Configured this branch and explicit V2-only start command. Read-only export variables reference scalp-economics-forward-v1. Code fingerprint ec18e01e3c50cd3e52142e1451e28d985bbceeb1c602404d0aad6c51a20689c1. Intended cutoff 2026-09-16T22:30:00+00:00, conditional on successful acceptance before that time; no accepted V2 observations yet.

BLOCKED: Railway create-deployment was explicitly called with branch scalp-nextgen-shadow-v2, but initial deployment 60df0b1e-74dd-4b8c-852e-68336bee4288 selected main commit 8b7f8b48694364cb8c47456d0ab491b102aa42c0. This is not an accepted V2 build. Service source now reads scalp-nextgen-shadow-v2. Startup is explicitly restricted to V2 files. Redeploy is blocked while the initial build runs; Railway Agent is usage-limited.

NEXT STEP: This documentation commit requests the configured branch's normal GitHub deployment. Verify exact branch and code fingerprint, health, source access, and frozen-service deployment parity before accepting activation. No production code or frozen branches changed. No orders or promotion.
