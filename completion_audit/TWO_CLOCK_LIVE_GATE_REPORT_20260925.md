# Two-clock live deployment gate — held before deployment

Result: **BLOCKED_COST_PREFLIGHT — candidate NOT deployed.** Production remains PR36. No deployment, restart, stop, configuration/variable update, subscription change, new service, merge, tuning, or production load test was performed. SIGNAL ONLY / NO ORDERS.

## Exact identities verified

| Item | Verified identity |
|---|---|
| Approved runtime | `06261dbfbe6d8336a6886a4f2b349f33b06b6202` |
| Approved runtime tree | `196707359f1ce25786bacbf419f409b3564a51c5` |
| Prior evidence checkpoint | `ca03e4cd85037116a866d2b9108df0ad2365e738` |
| Hosted run / job | `36084580891` / `107913492515` |
| Hosted artifact | `10843278145`, two-clock-integration-evidence, 18,235 bytes |
| ZIP SHA-256 | `54d4837469ed91ed4c7de8126b1851077090b9645ae499c275b1415e17ff7d56` |
| Production and designated rollback | PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77` |
| PR36 tree / deployment | `586f8cfd635d6ed817c63202cdec0b8bcc454e0c` / `f82466d0-70ab-4779-a0fd-58832ad31513` |

Fresh GitHub reads confirm the runtime tree and successful hosted run at the exact runtime SHA. The downloaded ZIP still matches the hosted digest. All 10 recorded code hashes and 19 evidence hashes match. The evidence head has no runtime/config changes relative to the approved candidate.

Existing acceptance remains 357 root + 29 audit = 386 Python tests, 9 hosted Chromium tests, 3 static gates and 5 assembled topology scenarios. The prior 367 tests and faster-action rejection cases remain in this evidence. These suites were **not rerun or rebuilt** for this preflight; identity validation reuses their passing result.

## Required resource/cost gate

Actual Railway resource metrics were read before any candidate deployment. Each service uses a trailing six-hour window, 60-second sampling, 361 samples per measurement. Queries span several minutes and are not perfectly simultaneous. PR36's six-hour window begins after its startup. All 43 service reads ultimately succeeded; initial tool errors were retried and were never counted as zero.

The sum of reported service means is **1.865871 CPU cores and 9.344861 GB RAM**. At Railway's published container rates ($20/vCPU-month and $10/GB-month), the existing project has a **$130.77/month CPU+RAM run rate** if those averages persist for a full month.

| Existing service | Mean CPU cores | Mean RAM GB | CPU+RAM monthly run rate |
|---|---:|---:|---:|
| scalp-unarmed-live-tape-v1 | 0.479335 | 5.418637 | $63.77 |
| Btc-15min-bot (PR36) | 0.939079 | 0.899013 | $27.77 |
| scalp-move-shadow-v1 | 0.127191 | 0.988577 | $12.43 |
| scalp-finalprod-clean-v1 | 0.073762 | 0.811078 | $9.59 |
| All remaining services combined | 0.246505 | 1.227556 | $17.21 |
| **Project total** | **1.865871** | **9.344861** | **$130.77** |

This is a measured-resource extrapolation, **not an invoice, exact billing forecast, or claim of permanent irreducible cost**. Storage, network egress, taxes, account-specific credits/discounts and other projects are excluded. No network charge was extrapolated from ambiguous metric aggregation. The raw metric records and formula are preserved in TWO_CLOCK_LIVE_RESOURCE_PREFLIGHT_20260925.json.

A separate earlier six-hour PR36 read yielded 0.940934 CPU and 0.898814 GB RAM, equivalent to $27.81/month; the one-hour read implied $26.26/month. These independently confirm the direction of the budget conflict. Even preserving only PR36, its separate V8.1 owner and shared BRTI owner at their observed averages gives approximately $30.42/month CPU+RAM before storage/egress. This is an arithmetic diagnostic, **not a proposal to remove other required services**.

Railway's account tool reports effective **PRO** tier. Its plan-limit payload has `includedUsageDollars=0`; that field is not an invoice and is not reconciled with public Pro documentation, which says the $20 subscription includes $20 usage. The connector expressly cannot read billing-period charges, invoices or projected bills. The browser reached https://railway.com/workspace/billing but required login; no billing data or credentials were obtained. Consequently actual account credits, invoice total and cycle forecast remain **unverified**. Under ordinary documented Pro billing, included usage is part of the $20 minimum, not an extra $20 discount from the resource run rate.

Pricing sources retrieved 2026-09-25:
- https://docs.railway.com/pricing/plans
- https://railway.com/pricing

## Information-layer optimization diagnosis

The information worker is absent in production, so its actual current incremental usage is zero. Setting its hypothetical future CPU and RAM increment to zero still leaves the measured existing project far above approximately $20/month. Thus information-only savings cannot resolve this preflight conflict.

The exact candidate already serializes inference, rejects duplicate source novelty before model evaluation, bounds frames/history/proofs, keeps client queries from triggering inference or native polling, caps forwarding concurrency/rate, uses one numerical-library thread, and lowers the information worker's scheduling priority. Cadence, retention or code changes would create a different candidate and require qualification; none were substituted. Reducing source freshness, native cadence or required telemetry is not an acceptable budget mechanism.

The largest existing cost is the unarmed-tape service's memory; next are PR36 and two existing SCALP services. Their ownership, retention and required evidence roles must be established before any consolidation or optimization. No service was declared disposable from its name or SUCCESS status. No collector was stopped, history deleted, or required behavior reduced.

This is a budget conflict within the currently authorized exact-candidate scope, not proof that the complete project can never meet $20 after a separately qualified cost-remediation effort.

## Rollback and deployment mechanics

Fresh direct Railway metadata confirms PR36 SUCCESS, `canRollback=true`, `canRedeploy=true`, and snapshot `3819e9e0-5282-47f1-8b2b-4a52eb30a2a6`. Original start command, /data volume, source branch, region, single-replica configuration and variable names are preserved. The information-export flag is absent, config is byte-equivalent as returned, and staged config is null. V8.1 remains SUCCESS at deployment `4105da0a-e5a2-4a76-8abc-242b0bab5ad8`, commit `b05723ec622f901a05402ecf27f4d33505753ef1`.

No rollback was necessary or invoked. Railway's documented retained-image rollback restores image/settings/variables; actual invocation and a supported explicit stop-complete/start operation still need to be established immediately before deployment. Do not rely on startup sleeps or an in-container lock to prevent cross-container overlap.

The Railway agent's narrative incorrectly discussed the pre-PR36 deployment as the designated rollback and inferred that REMOVED meant an expired image. Those assertions, guessed drain defaults and unverified mutation signatures were rejected. Direct deployment metadata and documented image retention are the evidence; no production mutation used that narrative.

## Live acceptance status and continuation

**No candidate live acceptance claim is made.** Candidate native scheduling/cadence impact, informational AVAILABLE/WAIT duty cycle, source/publication/inference latency, display expiry, live parity/authentication, source causality, rollover and bounded-client overload measurements are all **NOT RUN** because the required budget preflight blocked deployment.

The previously recorded 1.445-core, 670.6-MiB RSS and 15.73-ms scheduling-lateness stress maxima remain offline evidence, not continuous billed usage or actual Railway candidate measurements. Railway's container memory metric is not identical to summed process-tree RSS. No incremental cost estimate was manufactured from stress peaks.

Native authoritative semantics, Core NOT_LINKED, FINAL shadow_only=True, shadow_protection_used_as_action=False and V8.1 ownership remain unchanged because production/config/source code were untouched. Information remains INFORMATIONAL_READ_ONLY in the approved candidate. Actionable publication expiry and lifecycle gaps remain unresolved as previously documented.

Before proceeding:
1. Reconcile actual account billing/credits and the measured existing service footprint with the approximately $20 total objective.
2. Obtain a reviewed baseline cost-remediation scope that preserves required services/behavior, or an explicit revised operating budget. Information-only optimization cannot bridge the measured gap.
3. Reverify exact runtime/artifact/rollback identities and establish supported no-overlap stop/start and immediate image rollback operations.
4. Deploy only the approved candidate if still authorized, then perform every requested live native/information/source/resource/rollover gate with automatic rollback. Do not substitute a changed candidate without its own qualification.

This report and raw preflight evidence are committed on `audit/two-clock-live-cost-gate-20260925`, descended from the prior evidence checkpoint. The commit containing this report is evidence-only and is **not a deployable replacement for 06261db**.
