# BTC15 DEVELOPMENT OPERATING CONTRACT V1

Status: MANDATORY PROCESS GATE
Scope: all BTC15 strategy, evidence, timing, Kalshi/BRTI, dashboard, deployment, scoring, and integration work.

## Non-negotiable product invariants
- SIGNAL ONLY. Manual execution. NO ORDERS.
- Every active 15-minute contract is analyzed; PASS/No Edge is a valid output.
- FINAL authority is separate from continuous informational probability.
- EARLY is entry/value guidance, never FINAL authority.
- SCALP/REVERSAL and profit protection use their qualified lifecycle only.
- Use UP/DOWN terminology.
- Entry presentation: ideal 25–35%, good 36–50%, target <=50%; never upgrade qualification because price is attractive.
- Exact Kalshi contract identity, target, canonical clock and rollover alignment are mandatory.
- Qualified BRTI must be causally available and satisfy the frozen freshness rule (currently <=5.0s where applicable).
- Informational values fail closed on stale data, rollover, reconnect, background/foreground transition, owner restart, clock regression, identity mismatch, or expired lease.
- No cross-contract composition.
- No UI-derived qualification.
- Recovered app visual source of truth is the exact V11/V12/V13 lineage; no redesign unless explicitly approved.
- Live BTC/BRTI chart remains part of the product.
- Profit protection stays with the scalp/ladder lifecycle.

## Protected evidence / production rules
- Production and the prospective cohort are frozen unless the task explicitly authorizes a production change.
- Never tune model weights, thresholds, feature definitions, ladders, persistence, timing gates, or scoring against the protected prospective cohort.
- Never rewrite, delete, truncate, or contaminate prospective evidence.
- Bot-reported performance is not sufficient for launch. Final prospective results require independent reconstruction from raw evidence.
- No merge/deploy/restart merely to preview UI work.

## Mandatory development state machine
Every candidate MUST move through these states in order:

INVESTIGATE
→ DESIGN COMPLETE CHANGE
→ IMPLEMENT COMPLETE CANDIDATE
→ VERIFY STORED SOURCE
→ BUILD/INSPECT RESULTING ARTIFACT
→ STATIC + ADVERSARIAL TESTS
→ EXECUTE COMPLETE RELEVANT SUITE
→ DEVICE/VISUAL CHECK WHEN APPLICABLE
→ CANDIDATE QUALIFIED

Rules:
1. A failure at any gate returns to INVESTIGATE. Do not patch only the observed assertion and immediately ask the user to rerun.
2. Diagnose the full failure set and dependency chain before producing the next candidate.
3. ANY code change invalidates execution qualification from older commits. Re-run the complete relevant suite on one exact commit.
4. Never describe a candidate as PASS/qualified/ready until the exact stored commit has completed its required execution suite.
5. Distinguish: source inspected, artifact built, test executed, device observed. Never substitute one for another.
6. Fail closed when expected source/DOM/schema/identity anchors are absent. Never fuzzy-patch a live trading presentation.
7. Preserve evidence of rejected candidates; do not rewrite history to make a failure disappear.

## User interaction rule
- Do not use the user as an iterative terminal debugger.
- Exhaust repository/tool-side investigation first.
- Bundle all remaining execution checks into ONE qualification command/script for the exact candidate.
- If that run fails, collect/diagnose the whole failure set before asking for another run.
- Keep commands short for iPad/iPhone and avoid long paste blocks.

## Qualification output rule
One exact commit receives one final result:
- BTC15 CANDIDATE QUALIFIED — ALL REQUIRED GATES PASS
or
- BTC15 CANDIDATE REJECTED — <failed gates>

Partial PASS results may be reported as evidence but never promoted to candidate qualification.

## Launch gate
No onboarding/real-money reliance until:
1. protected prospective cohort completes,
2. independent forensic reconstruction reconciles with bot scoring,
3. production identity/timing/authority suite passes,
4. recovered app integration qualifies on one exact commit,
5. iPad and full-feature iPhone visual/device checks pass,
6. signal-only/no-orders invariant is reverified.
