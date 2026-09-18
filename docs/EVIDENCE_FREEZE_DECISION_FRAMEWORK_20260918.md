# EVIDENCE FREEZE DECISION FRAMEWORK — COST REMEDIATION

A research service may be proposed for freeze-and-stop only when ALL applicable conditions are documented:

1. Frozen experiment identity/cutoff is known.
2. Predefined sample-readiness gate is met (if the experiment defines one).
3. Latest evidence state and source boundary are captured.
4. Any required manual review/selection decision is explicitly recorded.
5. Stopping does not erase unique in-memory evidence that has not been persisted.
6. Restart semantics and timer segments, if any, are accounted for.
7. No downstream service requires the live endpoint for correctness.
8. Evidence artifact is durable/reproducible.
9. orders=false / no automatic promotion.
10. User approves irreversible service retirement if deletion is required.

Current triage:
- Watch/Exit: sample-ready; candidate for review/freeze decision, NOT auto-stop.
- Nextgen V2: ready for manual comparison; candidate for review/freeze decision, NOT auto-stop.
- Economics/Candidate/Regime: sample-ready in prior checkpoints but still part of active comparative evidence; review first.
- Coverage Rescue: continue; rescue increment remains sparse.
- Gap Recovery: continue; specialist sample remains sparse.
- Entry/Reversal holdouts: continue; untouched denominators still advancing.
- Blueprint/Unarmed: continue; timer/visual review evidence active.

Cost rule:
Prefer formal freeze-and-stop over engineering a permanent bounded-state daemon when the scientific objective is complete. Prefer bounded state when continued prospective evidence is still required.
