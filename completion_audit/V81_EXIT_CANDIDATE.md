# V8.1 exit lifecycle: offline candidates, not deployed

Current production V8.1 publishes5/10/20c movement states and expires after180 seconds. It has no connected stop/exit policy. This PR prepares the missing lifecycle comparison without selecting a numeric policy or changing live entries.

The four predeclared hypotheses are the existing180s baseline, PROTECT5/2, RUNNER10/4 and an8c-target/10c-stop comparison. The latter three originate from separate established research/core concepts; applying them to V8.1 is a new hypothesis, not evidence of equivalent performance. Their manifest is registered before the common universe starts September23 20:30 UTC. Development, validation and untouched holdout remain separated by PR24's immutable cohort.

The replay connects actual published event identities to qualified same-contract bid observations, preserving both UP and DOWN. It retains stale/missed entries, refuses out-of-order/future/stale input, does not backdate a missing horizon quote into a fill, keeps negative excursions and makes terminal exits immutable. It does not synthesize extra reversal/reentry signals after a hypothetical exit.

Eleven local tests cover the lifecycle and connection through the actual event/journal schema. These are implementation tests, not performance proof. Production feed/dashboard integration and policy promotion remain blocked on valid common-universe prospective comparison, complete detector/reentry replay, and the applicable production change approval. No exit advice is currently published by this code. No orders are possible.
