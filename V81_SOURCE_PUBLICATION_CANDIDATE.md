# V8.1 publication source guard — 2026-09-23

Companion to PR29's timestamped quote producer. Candidate only; no production deployment. SIGNAL ONLY / NO ORDERS.

The existing 3.5s publication limit remains necessary but cannot establish the freshness of prices inside a newly published response. The actual inline renderer now checks the current and original entry source identities, current true quote/BRTI ages, exact contract/target/open-close, and current bid provenance. Original entry source ages are checked at the entry time; historical entry timestamps are never renewed. Source WAIT is described as unavailable data rather than a false absence of a 30–45c side.

Preserve existing CORE/SURGE logic, EARLY/FINAL, main detector/polling cadence, staged rollover and fixed target. BRTI <=5s, publication <=3.5s, existing timestamped quote <=6s. This change contains no model, weight, strategy threshold or exit-policy change.

197/197 local main regressions passed in 15.588s, including actual inline JavaScript cases and the existing core/provenance/rollover suite. Initial test invocation from the parent directory caused relative-path errors; the complete rerun from the candidate directory passed. The publication fixture is fixed to an official mid-contract clock so tests do not depend on wall-clock quarter boundaries. Hosted results must be recorded separately.

Do not deploy this main-only component ahead of the qualified V8.1 producer. Do not restart main solely to install this guard: c482468's current actual model weights are unexported and its cold-start training universe moves. Coordinate with the unresolved native model/input reproducibility work, preserve rollback points, and freeze separate runtime/cohort identities. PR25/26/28 remain unpromoted candidates.
