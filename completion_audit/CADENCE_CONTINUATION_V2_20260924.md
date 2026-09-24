# Recovered faster-decision result and continued engineering

**NOT DEPLOYABLE. Infrastructure is not complete. Production remains frozen PR36.**

The lost result was recovered from `audit/cadence-equivalence-rejected-20260924`, commit `0cc29a2403fdf1acc6217db16425abe603dd20d4`, in `CADENCE_EQUIVALENCE_REJECTION_20260924.md/json`. Its 30 passing tests established rejection counterexamples, not a successful candidate. No faster runtime had been installed.

This continuation did not redo the publication-expiry diagnosis, PR36, predictive scoring, parameter searches, or the September 24 20:15–21:15 UTC validation cohort. It used synthetic 2020 timestamps and the already-frozen fitted fair artifact. SIGNAL ONLY / NO ORDERS.

## What was completed after recovery

1. **Actual frozen-loop comparison.** The original loop and 41 original functions execute in independent offline namespaces with the real, hash-verified fitted fair model. Original outputs and captured state match at identical original timestamps despite intervening projected evaluations, including fast price changes and quote waits. Functions are rebound to private globals; histories, model arrays and source caches are copied. This is stronger than the earlier fixed-probability display-gate probe, but is still an offline test adapter, not a production worker.
2. **Persistence phase and rolling-history separation.** Restoring the whole pre-evaluation snapshot fixes the earlier persistence phase error but drops a real committed price extreme. Separate snapshots for historical features and the emitter's persistence phase preserve that extreme without adding hits. Tests cover inclusive/expired persistence boundaries, current partial candles, transient BTC extremes and the next original decision.
3. **Immutable frame retention.** A reader can retain the exact original quote proof while newer frames publish. Missing identities fail closed; captured bytes remain usable only within their unchanged source deadlines. The actual quote replay rejects stale/future/mixed/rollover frames. Current source failure or owner restart blocks qualification. This solves the demonstrated race in an in-memory component; it is not a deployed atomic handoff.
4. **Companion lifecycle experiment.** An immutable entry origin plus the original committed tick tape can reconstruct the unchanged profit-protection routine without counting extra queries as lifecycle evaluations. Both sides retain arm → target/trail/BRTI protection, including rollover and repeated-query tests. Protection was not disabled.

## Why the complete architecture still fails

The remaining issue is broader than copy isolation. A new entry needs an owner whose later entry/repeat/protection behavior is defined.

| Tested alternative | Result |
|---|---|
| Discard projected event state | A 301-second entry disappears from the next projection; nothing owns its later protection. Rejected. |
| Commit the extra entry into native state | Native last-entry time and the next 305-second decision change. Rejected by exact legacy equivalence. |
| Persist a separate companion entry and replay protection only at original ticks | Remembers and protects that origin without mutating native state. But publishing both the 301-second companion and unchanged 305-second native birth breaks the original single-stream repeat rule: 4 seconds versus 15 seconds for general shadow events and 120 seconds for true-scalp signals. Both directions are tested. |
| Alias or suppress one birth | Suppression changes a published native decision; merging origins changes entry time/price or loses the companion's original basis. That needs an explicitly different output/lifecycle contract. It is not established as frozen-equivalent. |
| Reevaluate native protection on every fresh input | Even a newer agreeing BRTI observation with unchanged quotes causes an armed 51c bid to exit at 301 rather than 305. New input identity alone does not prove that an exit is caused by that input. Rejected. |
| Publish faster current assessments but reserve all entries/lifecycle transitions to the original clock | Can preserve original authority and potentially improve informational source availability. It does **not** establish the requested complete actionable faster-decision lifecycle; it must be labeled as such, not sold as completion. |

The repeat counterexamples concern the actual frozen event/true-scalp shadow paths. They are **not** evidence that the raw EARLY display has a 120-second cooldown; it does not. Separately, the pinned dashboard explicitly marks Core scalp positions `NOT_LINKED`, FINAL protection `shadow_only`, and `shadow_protection_used_as_action=False`. A complete connected EARLY/Core/FINAL HOLD/CAUTION/PROTECT/EXIT/FLIP lifecycle is not defined by that frozen runtime. Selecting a live policy from shadow rules would add strategy authority, even without changing a numeric threshold. V8.1 remains a separate unchanged owner.

For a single native stream, these requirements conflict on the demonstrated path: emit an extra earlier birth, retain the unchanged later native birth, and preserve their original shared cooldown. Copying state, adding a ledger, or retaining more proofs cannot make all three true. This is a scoped counterexample, **not a proof that faster information or every possible separately defined signal architecture is impossible**.

## State inventory and test evidence

See `CADENCE_STATE_INVENTORY_V2_20260924.md` for the main state and every downstream ownership group inspected: histories, partial candles/features, pre/post-append persistence, event/profit states, cooldowns, BRTI receipts/recovery/closeouts, quote sequence/rebase state, contract staging, loop clocks, diagnostic dedupe, file publications, Rescue switch counts and pending outcomes, FINAL trigger state, dashboard joins, V8.1 boundaries, and observer/supervisor state. The result JSON records the 166 captured namespace fields and scope exclusions.

Final validation: **298/298 root tests, 29/29 audit tests, and three static gates passed**; the root suite includes 30 new engineering tests. Exact counts and commands are in `CADENCE_CONTINUATION_V2_20260924.json`. Passing counterexample tests and broad regressions must not be interpreted as semantic acceptance. The fair model bytes/weights and all production source files remain unchanged. No trained true-scalp prediction parity or full V8.1 producer-parity claim is made: lifecycle reachability tests use explicitly synthetic fixed probabilities.

Initial harness failures were corrected openly: callable test adapters were excluded from data-state snapshots (a mock otherwise recursively fabricates model attributes), and structured model arrays are compared by every named field rather than uninitialized memory padding. The read-only history view also has an explicit deep-copy method so snapshots retain its rows, and restoring an earlier snapshot removes later temporary bindings. These harness corrections do not alter the production oracle, parameters or semantic acceptance criteria.

## Availability, kept separate from performance

With constant **representative age at completed publication** of 2.486 seconds, no outages and genuinely new causal inputs available each second, the source-only duty-cycle bound is `(5 - 2.486) / 5 = 50.28%` for five-second publication, versus up to 100% at one-second publication: **up to +49.72 percentage points in that idealized case**. The recovered report also preserves timestamped delay/jitter/outage scenarios; they were not re-scored or used to choose predictive parameters.

That arithmetic is not an expected production gain. It assumes qualified quotes, timely input delivery and a valid complete-decision publication path. The new local 10-evaluation benchmark measured private copying plus actual fitted fair inference at median 0.336 seconds, maximum 0.420 seconds; it excludes network, independent parity and deployment contention. Real publication must recheck source age after that work. Model accuracy, entry economics, ladder coverage and scalp success were not evaluated.

**Expected production source-qualified improvement remains unestablished.** No accepted full candidate or deployment exists; actual deployed improvement from this work is zero.

## Review recommendation and continuation boundary

Do not merge into production or deploy. Preserve PR36 `3e552065e34a0a402bc3ca4598b57dff1f1c6e77` (tree `586f8cfd635d6ed817c63202cdec0b8bcc454e0c`) and Railway deployment `f82466d0-70ab-4779-a0fd-58832ad31513`; the read-only Railway check still reports this commit as SUCCESS. Its prior rollback `1730ceff180394fbd2ebae7a5fddc4acd1e76194` / `454f53ad-b269-4133-b0f5-60098978db71` also remains recorded. No service, variable, credential, restart, order capability or main-branch mutation occurred.

This branch is a preserved **engineering rejection and reusable tested components**, not a release candidate. There is no hidden deployment switch or production import. In-process test patching is deliberately not proposed as live isolation.

The next decision for Chat is the allowed authority contract: faster informational assessments with the original action clock, or a separately specified extra-entry lifecycle with explicit origin/deduplication/cooldown/legacy-output arbitration. The latter requires a deliberate exception to strict frozen stream semantics and a defined protection policy where the current display is unlinked. Neither has been silently approved or substituted here. Until that distinction is resolved, claiming complete infrastructure or proceeding to deployment would exceed the frozen-equivalence requirement.
