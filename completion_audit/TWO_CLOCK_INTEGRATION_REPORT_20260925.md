# Production-integration qualification: PASS for controlled deployment

**Candidate:** `06261dbfbe6d8336a6886a4f2b349f33b06b6202`
**Tree:** `196707359f1ce25786bacbf419f409b3564a51c5`
**Branch:** `audit/two-clock-integration-20260925`
**Decision:** Ready for a controlled single-instance, small-client deployment after Chat review, using the documented traffic/resource envelope. **Not deployed or merged.** This is informational infrastructure qualification, not predictive/trading improvement or completed EARLY/Core/FINAL lifecycle policy.

Production still reports SUCCESS at PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`, deployment `f82466d0-70ab-4779-a0fd-58832ad31513`. V8.1 remains SUCCESS at `b05723ec622f901a05402ecf27f4d33505753ef1`, deployment `4105da0a-e5a2-4a76-8abc-242b0bab5ad8`. No production setting, source, credential, volume, deployment or native file was changed.

## Installed topology and authority

The optional installer preserves the exact PR36 dashboard payload, original render fixes and V8.1 inline diagnostic script. Generated supervisor copies change only child-path constants; dashboard/full-validation → parity → Rescue → native ownership remains intact, along with FINAL shadow protection and the prospective observer. The native leaf executes the pinned PR36 AST with the accepted single read-only observation call. A separately supervised, credential-stripped information worker receives immutable bytes over loopback. It never loads entry/protection functions, polls an authenticated upstream, changes native history or writes strategy logs.

Information has its own panel, routes and closed **44-field INFORMATIONAL_READ_ONLY** contract. Unknown fields, routes and queries fail safely. Native `/dashboard_state.json`, EARLY/SCALP/FINAL cards, fair-input export, persistence/scoring and source owners retain their original implementation. An information WAIT cannot rewrite or refresh any native object. Only the original clock can write **AUTHORITATIVE_ACTION_STATE**. API error metadata and request-nonce headers are informational transport metadata, never advice or source qualification.

The unchanged field and lifecycle contracts remain `TWO_CLOCK_FIELD_AUTHORITY_20260925.md` and `TWO_CLOCK_LIFECYCLE_SPEC_20260925.md`. Core positions remain **NOT_LINKED**; FINAL protection remains **shadow_only=True** and **shadow_protection_used_as_action=False**. Undefined EARLY/Core/FINAL management policies remain undefined. V8.1 remains its separate owner. No new HOLD, CAUTION, PROTECT, EXIT or FLIP advice is created.

## Exact gates

| Gate | Result |
|---|---|
| Local root regression, exact final source | **357/357**, 138.980s |
| Local preserved audit | **29/29**, 1.977s |
| Previously accepted tests | All **367** retained; **19** new integration tests; total **386** |
| Original static gates | **3/3**: production/canary paths, dashboard quote/parity authority, BRTI main cutover |
| Hosted root + audit on exact candidate commit | **357 + 29**, all pass; 55.770s + 0.596s |
| Chromium on assembled production HTML | **9/9**, Chromium 151.0.7922.34 |
| Assembled multiprocess scenarios | **5/5**, local and hosted; real supervisor/telemetry/dashboard/worker processes; native network and disk effects replaced by synthetic adapters |

Hosted Actions run **36084580891**, job **107913492515**, succeeded on the exact candidate. Artifact **10843278145**, `two-clock-integration-evidence`, ZIP SHA-256 **54d4837469ed91ed4c7de8126b1851077090b9645ae499c275b1415e17ff7d56**. The downloaded archive was hash-verified; its five text/JSON files are permanently checkpointed under `TWO_CLOCK_INTEGRATION_HOSTED_06261db/`, avoiding reliance on Actions retention. Local Chromium installation was blocked by the workspace download path; browser execution is the successful hosted result, not a claimed local run.

## Authoritative equivalence and causality proof

1. Original main, source owners, fitted artifact, supervisor logic, Rescue, FINAL collector, observer, packaged state builder and active Railway configuration remain byte-identical to their pins. Removing the one observation expression restores the exact original native AST. Installation tests compare supervisor ASTs after removing only the replaced child constants and recover the exact original HTML by removing the separate panel.
2. The recovered complete-loop oracle tests compare native outputs, sinks and **166-plus mutable data bindings**, including model arrays/source cache and loop temporaries, at identical supplied native timestamps. All comparisons still pass with intervening fast reads. Histories/partial candles/rolling features, persistence, event and profit state, arm→later-exit, repeat/cooldown, contract/rollover and source qualification retain frozen semantics. The accepted faster-action rejection counterexamples still pass; no rejected action projection is installed.
3. Export copies bounded committed history and exact quote-event membership; owner locks are nonblocking and held only for membership/reference capture. Exact immutable source bundles are retained by hash. Concurrent publication does not substitute a latest proof into an old frame. Evicted identities return WAIT. No fast read calls consume/accept/select, appends a BTC tick or enters a native lifecycle function.
4. Capture, pre-inference, post-inference and display checks retain original source timestamps. Inference-time expiry, future/stale input, interruptions, owner restart, target/ticker change, rollover, missing provenance and incomplete features fail closed. **BRTI never exceeds 5.0s**. No stale forward fill or future data is used. Repeated requests cannot extend immutable source deadlines.
5. Browser tests exercise the actual assembled assets: full transport RTT is charged, stale/future/slow responses and disconnects clear information, page transitions invalidate tokens, serialized tokens are rejected, and a new request nonce prevents replay of an old serialized HTTP response. Every native card remains unchanged. Health sampling retains its original timestamp and at most a one-second lease; client reads cannot renew it or amplify native polling.

These establish semantic equivalence at identical timestamps, not a mathematical guarantee of zero physical scheduling jitter. The independent process/load measurements below cover observed wall-clock impact.

## Resources and native timing

All scenarios use 50,416 completed history rows and the real frozen fair model. Native evaluates every five seconds; quotes/BRTI come from a synthetic January 2020 source owner. Normal load is four clients (three information readers at 2Hz plus one native reader). Overload is 24 clients at 10Hz (18 information + six native), deliberately far above the public information budget of 20 requests/s. Proofs contain 2, 2,000 or 7,000 events; largest serialized proof is **1,519,207 bytes**. Each scenario measures 30 seconds, then exercises worker restart and group cleanup. Native produced six or seven evaluations per scenario without starvation; every restart/cleanup assertion passed.

| Local assembled scenario | Mean process-tree CPU cores | Peak summed RSS MiB | Max native tick lateness | Max native iteration |
|---|---:|---:|---:|---:|
| No information worker, 1 CPU | 0.037 | 327.5 | 0.378ms | 161.7ms |
| Normal, 1 CPU | 0.253 | 537.8 | 0.144ms | 177.0ms |
| Overload / 2,000 events, 1 CPU | 0.835 | 557.3 | 3.870ms | 289.4ms |
| Overload / 2,000 events, 2 CPUs | 0.965 | 562.8 | 5.341ms | 413.0ms |
| Overload / 7,000 events, 2 CPUs | 1.445 | 615.2 | 15.730ms | 495.7ms |

Normal native median iteration increased from **140.64ms to 145.98ms** in the local paired small-proof runs, with no missed five-second schedule. Large-proof rows also change workload and are absolute stress measurements, not isolated causal estimates of information overhead. Hosted normal CPU/RSS were **0.090 cores / 589.6 MiB**; hosted maxima were **1.387 cores / 670.6 MiB**, **8.822ms** scheduling lateness and **179.4ms** native iteration. Summed RSS double-counts shared pages and is a conservative process-tree footprint.

Read-only Railway measurements show configured ceilings of **24 CPU / 24 GB**, one replica; recent production CPU average/max **0.814 / 1.203 cores**, memory average/max **0.916 / 0.925 GB**. These are limits and observed usage, not a statement about prepaid monetary allowance. The candidate fits this resource envelope in the exercised scenarios. Real authenticated network latency, native training/warmup and long-lived production traffic are not reconstructed by synthetic effects adapters. Therefore this is a controlled-rollout recommendation, not a hard real-time or fleet-scale capacity guarantee.

The information child is limited to one logical CPU, nice +10, single numerical-library threading, 2GiB address space and 128 file descriptors. It retains 32 frames, each ≤3MiB; native anchor ≤32 completed rows/4,096 existing ticks, original quote evidence ≤2MiB. Public forwarding permits four in-flight requests, sustained 20/s with a burst of 20. Over-budget/slow operations return unavailable; native scheduling takes precedence.

## Availability: distinct clocks, no predictive claim

The following is a **time-grid measurement for one actual HTTP viewer**, charging full RTT, honoring original deadlines, and clearing on HTTP failure. It is not a request-success percentage. Native availability independently measures the retained original complete decision's source qualification. No ladder readiness or outcome is scored.

| Run | Information display availability | Native source-qualified availability |
|---|---:|---:|
| Normal local assembly | **88.20%** | **33.77%** |
| Normal hosted assembly | **96.53%** | **33.43%** |
| Local overload / 2,000 events / 1 CPU | 11.87% | 30.10% |
| Local overload / 2,000 events / 2 CPUs | 9.17% | 22.87% |
| Local overload / 7,000 events / 2 CPUs | 0.83% | 14.73% |

Normal same-run informational gains are **+54.43pp local / +63.10pp hosted** over the native retained-decision timeline. These are synthetic infrastructure observations, **not production estimates or predictive/trading gains**. Native percentages vary across independently started runs because of source phase and measured latency; they are not claimed action improvements. At identical native timestamps the original stream/state is exactly equivalent. The previous accepted fixed-source-age experiment remains separately preserved (91.27% information versus 46.93% native before the installed browser/proxy path).

**Actionable publication expiry is not solved.** The original action clock remains frozen. Information overload can be worse than native availability because the separate panel fails closed. The deployment is not qualified for unrestricted concurrent viewers; start within the tested small-client envelope and maintain aggregate information traffic below the documented budget. No threshold or source deadline is relaxed to improve these numbers.

## Integration corrections and residual scope

Corrected client-driven native health fan-out with a bounded sampler and fixed original lease; corrected unfair per-request spacing with a bounded burst; added old-response nonce rejection; bounded worker CPU/memory/files; made spawn failures retry without stopping native and removed upstream credentials from the information child; added root ownership locking and process-group cleanup with independent child grace. A regression proves a child finishes its cleanup even after its supervisor exits. No predictive/lifecycle policy was changed.

An early stress fixture incorrectly injected receipts from two synthetic writers and triggered the existing backwards-receipt rejection. The fixture was corrected so the source simulator is its sole writer and native only consumes it; all final runs passed. This was a test-adapter issue, not evidence to weaken production causality checks.

Remaining limits: bounded health revocation lease (at most one second, always still subject to original source expiry); fail-closed information capacity under overload; unknown real deployment network/timing variation; single-replica ownership; and the already documented unfinished EARLY/Core/FINAL lifecycle. Use controlled stop/start without overlapping native owners on the shared volume; in-container locks are not cross-container coordination. Do not promote any shadow lifecycle or proceed into ladder optimization from this result.

Installation and exact rollback are in `TWO_CLOCK_INSTALL_AND_ROLLBACK_20260925.md`; the optional configuration is `railway.information-candidate.json`. Rollback is PR36 commit **3e552065e34a0a402bc3ca4598b57dff1f1c6e77**, tree **586f8cfd635d6ed817c63202cdec0b8bcc454e0c**, with its preserved original start command and `/data`. No migration or information-ledger cleanup is needed. **SIGNAL ONLY / NO ORDERS.**
