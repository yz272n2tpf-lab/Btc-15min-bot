# BTC15 Project Engineering Memory Protocol

**Purpose:** Durable project-level operating memory for the BTC 15-minute signal-only bot. This file is the standing engineering protocol and should be consulted before major audits, tests, deployments, or architecture changes.

**Control model**
- Main BTC project chat = architect, decision-maker, source of truth, and owner of system-level judgment.
- Work mode = bounded auditor/executor only when explicitly assigned a narrow task; it does not independently steer the project.
- Critical Work findings must be independently cross-checked against GitHub/Railway/log evidence before engineering decisions.
- Signal-only/manual trading remains non-negotiable. No orders. No automatic promotion.

## 1. Whole-system health, not green-service health

Never equate Railway `SUCCESS` with valid evidence.

Every important test must be evaluated across the full dependency chain:

`Kalshi/BRTI/Coinbase -> raw feed -> storage -> collector -> scorer -> evidence window -> dashboard/report`

A test is healthy only when the entire chain is verified.

## 2. Three mandatory evidence gates

### BEFORE a test
Verify:
- exact branch and deployed SHA
- configured command and actual deployed runtime
- frozen prospective cutoff
- source APIs responding and fresh
- Kalshi/BRTI/Coinbase feed freshness
- storage read/write health
- collector producing usable rows
- scorer consuming those rows
- correct 15-minute rollover/alignment
- no stale/legacy process conflict
- `orders=false`
- frozen controls unchanged

### DURING a test
Continuously inspect:
- last feed-update age
- BRTI/Kalshi/Coinbase error and 429 counts
- stale/missing feed periods
- storage write/read gaps
- collector row growth
- scoreable-row growth
- expected contracts vs observed contracts
- restart/redeploy events
- cutoff immutability
- runtime/config drift
- source-to-scorer lag

Any bad interval must be flagged immediately and classified; do not silently blend compromised intervals into evidence.

### AFTER a test
Before quoting or trusting scores, certify:
- clean vs compromised window
- uninterrupted vs interrupted collection
- expected vs missing contracts
- feed-quality failures
- restart/reset history
- denominator validity
- whether evidence is suitable for engineering decisions

No certification = no promotion.

## 3. Runtime/config parity rule

Service names, saved configs, and green status are not authoritative by themselves.

For each important service track:

`service name -> branch -> SHA -> configured command -> actual deployed command/process -> purpose -> data source -> storage dependency -> cutoff -> current health`

Any mismatch is a first-class integrity failure requiring investigation before evidence is trusted.

## 4. Authoritative system map

Maintain one current inventory classifying each service as:
- PRODUCTION / APP
- FROZEN CONTROL
- ACTIVE EXPERIMENT
- REVIEW TOOL
- PARKED
- LEGACY
- SAFE TO REMOVE
- EVIDENCE TRUSTED / QUESTIONABLE / NOT TRUSTED

Do not rely on service names alone to infer purpose.

## 5. Dependency-gated engineering

Never build a new decision layer on top of an unverified prerequisite.

Required progression:

`prove feed -> prove storage -> prove collector -> prove scorer -> certify evidence window -> then optimize logic`

A downstream layer may not be promoted or treated as validated while an upstream dependency remains unverified.

## 6. Evidence vs code distinction

A compromised evidence window does not automatically invalidate architecture or code.

Always separate:
- code/architecture that is sound
- evidence that is clean
- evidence that is partially compromised
- evidence that must be rerun prospectively

Do not throw away valid engineering work just because its certification window needs to be repeated.

## 7. Work-mode operating rule

Use Work for bounded tasks such as:
- read-only forensic audits
- broad codebase inspection
- large coding/test tasks
- long-running multi-step execution

The main chat defines the task and guardrails, Work returns findings/results, and the main chat independently reviews critical claims before deciding what happens next.

Work must not independently choose the project direction.

## 8. Outside-source discipline

For major engineering decisions, consult authoritative external material when useful, including:
- Kalshi API behavior/documentation
- exchange/API rate-limit guidance
- Railway deployment/runtime behavior
- SRE/observability practices
- streaming-data architecture patterns
- financial-market microstructure research
- prospective/walk-forward validation methods
- leakage prevention and experiment reproducibility

Clearly distinguish:
1. facts proven by our own data,
2. recommendations from external technical sources,
3. hypotheses still being tested.

## 9. Integrity Sentinel requirement

Maintain or build a dedicated evidence-integrity monitor whose job is not trading, but validating the experiment infrastructure.

It should watch at minimum:
- BRTI 429/error rate
- BRTI age/freshness
- Kalshi age/freshness
- Coinbase timeout/error rate
- storage write/read age
- collector row growth
- scorer row growth
- expected vs observed contract counts
- runtime/config SHA/command mismatch
- restart/redeploy count
- rollover/alignment health
- cutoff immutability

When integrity fails, the affected interval should be quarantined or explicitly classified rather than silently accepted.

## 10. Permanent decision rule

The project must optimize for **verified evidence quality before speed**.

Green services, increasing counts, attractive scores, or successful deployments are never sufficient on their own.

The standing engineering sequence is:

**Audit -> prove inputs -> prove storage -> prove collector -> prove scorer -> certify evidence window -> compare logic -> only then consider promotion.**

## 11. Mandatory dual-gate completion rule

Every meaningful test, milestone, release candidate, or claimed project-completion state must pass **both** of these independently:

1. **Operational Health PASS** — the system is actually running correctly: services/processes are live, storage has headroom, endpoints respond, collectors/scorers advance, runtime matches intended config, timing/rollover is correct, and no hidden restart/stale-process issue exists.
2. **Evidence Integrity PASS** — the output is actually trustworthy: feeds are fresh, BRTI/Kalshi/Coinbase quality is acceptable, rate limits/parity/staleness are accounted for, the prospective cutoff and cohort are immutable, contract paths are sufficiently observed, denominators are valid, and compromised intervals are quarantined rather than blended into results.

**Operational Health PASS + Evidence Integrity PASS = valid evidence.**

If either side fails, the result may be preserved for research/diagnostics, but it must not be certified, promoted, used as the foundation for a dependent layer, or treated as project completion.

This dual-gate rule applies to all parts of the bot, including Early, Final, scalp/reversal logic, entry quality, exits, Flip Risk, coverage, economics, handoff behavior, combined scoring, and the eventual finished app/bot.

The Integrity Sentinel and project health reporting must monitor both categories simultaneously. Operational monitoring never replaces evidence-integrity monitoring, and evidence-integrity monitoring never replaces operational monitoring.

This protocol is the default unless explicitly superseded by a later versioned authority file.