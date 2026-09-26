# Main publication polling candidate — not deployed

One-second internal observation (189 owner samples) found the owner fresh in all sampled states, with maximum true-source age 3.208s. Of 185 in-window main snapshots, 85 were BRTI-fresh and 184 passed the separate frame/parity checks. The five-second main producer cycle ages BRTI between decisions. The browser also polls every five seconds and can repeatedly miss the short eligible window. Actual browser observations independently showed stale WAIT and recovery to a fresh state. These samples do not establish continuous availability.

This narrowly scoped candidate changes only the packaged HTML's cached main-API refresh schedule to one second, with a 250ms minimum delay after a slow request. The existing awaited request completes before another is scheduled. Hidden-tab pause, request/contract epochs, receipt/source clocks, the BRTI5s requirement, V8.1 3.5s limit and fail-closed rendering are unchanged. No upstream request is added by the read-only dashboard endpoint. Main's five-second detector loop is unchanged: accelerating it would change sampling-dependent persistence and event behavior and cannot be treated as a harmless display fix.

This can reduce missed fresh windows; it cannot make a five-second-old model/BRTI snapshot continuously fresh. Do not claim it completes publication readiness. The remaining coordinated correction needs a qualified source/decision publication path with unchanged strategy semantics and measured load/coverage.

Do not merge/deploy this branch on its own. A main restart currently refits against a moving 35-day window; existing fitted weights are not exported. The calibration safety floor fails just after September25 12:45UTC. Coordinate any production rollout with a verified frozen model/runtime identity, prospective out-of-sample acceptance and the existing change-control scope. PR25 contains the separate leakage-free input/model candidate, not an accepted replacement. Preserve main c482468 and all existing cohorts/rollback points until that dependency is resolved.

SIGNAL ONLY. NO ORDERS. No visual redesign, ladder threshold, weight, target, clock or settlement change.
