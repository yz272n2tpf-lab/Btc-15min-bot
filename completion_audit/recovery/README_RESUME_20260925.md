# BTC15 integrated mission recovery — STOP at Gate 1

Checkpoint `31416eee2d927373139a41ff62846effa49b9556`; tree `42370af013b2ce8a8100b2a87b6b195b333a1718`; local branch `audit/pr36-origin-adapter-20260925`.
Qualified V2 remains `9b5b02744d8e31307516efb5a33c5190d8c74e90`.
Production/rollback remains PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`.
Two-clock remains undeployed `06261dbfbe6d8336a6886a4f2b349f33b06b6202`.
SIGNAL ONLY / NO ORDERS.

## Current result
Gate 1 BLOCKED: the unchanged V2 closed context pins runtime_commit to PR36 and
cannot bind the actual new instrumented build separately from its frozen strategy
baseline. Three new counterexamples demonstrate rejection, without installing
runtime hooks. No deployment, Railway mutation, authentic lifecycle admission,
continuous scoring or through-Wednesday connected test was started. Existing
collectors were not changed. Two-clock live acceptance remains outstanding.

Read `offline/completion_audit/INTEGRATED_CAPTURE_GATE_BLOCKER_20260925.md` and JSON.
The earlier V2 report/README records its historical offline-format PASS; it is not
runtime capture qualification. All 40 prior tests and V1/V2 components are unchanged.

## Restore without authentication
1. Extract this archive to a fresh folder and run `python3 verify_recovery.py`.
2. Run `python3 run_focused.py` for exactly 43 focused stdlib tests, including the
   three tests that PASS by confirming Gate 1 rejection. No network or model run.
3. Retain the original archive and manifest. No credentials/private live captures
   are present. Never execute the bundled full native file: AST/blob checks only.

The source/test package is self-contained for this offline work, not a deployable
repository mirror. `local-ladder-history.bundle` preserves exact local commits
since `852e9a4638eb487ffe5a307b79d039d2a9b747c1`. To restore Git objects into a full repository containing that
base, verify the bundle and fetch its `audit/pr36-origin-adapter-20260925` ref into a NEW local recovery
branch. Verify commit/tree above. No GitHub credentials or local push are needed.

## One next action requiring the user's revised authorization
Authorize a narrow versioned build-identity contract extension, preserving V1/V2,
that records frozen strategy identity separately from actual capture runtime
identity and validates the latter against an explicit qualified capture-build
manifest. This revises the integrated mission's unchanged-V2 requirement. Do not
lie about deployed commit identity or automatically trust an arbitrary build.
Then resume the previously specified offline passive capture/equivalence gates.

No production deployment/restart, two-clock change, cost cleanup, authentication
troubleshooting, predictive scoring/tuning, new lifecycle rules or orders are
permitted merely by restoring this package. Preserve remaining Work usage.
