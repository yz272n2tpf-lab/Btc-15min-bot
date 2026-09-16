# Frozen V2 synthetic causal audit

Status: **MECHANISM_TESTS_PASS**.

Checks: 6952; failures: 0; synthetic tapes: 40.

No market-efficacy or certification claim. No live raw tape audited.

| Check group | Checks | Failures |
| --- | ---: | ---: |
| frozen_constants | 1 | 0 |
| verify_boundaries | 25 | 0 |
| pullback_boundaries | 20 | 0 |
| scalp2_boundaries | 4 | 0 |
| watch_boundaries | 10 | 0 |
| score_boundaries | 1 | 0 |
| decision_prefix | 2280 | 0 |
| decision_outcome_independence | 120 | 0 |
| duplicate_evidence | 120 | 0 |
| event_time_order | 120 | 0 |
| decision_future_suffix | 85 | 0 |
| entry_exit_oracle | 85 | 0 |
| watch_exit_oracle | 200 | 0 |
| watch_prefix | 3800 | 0 |
| scalp2_outcome_independence | 40 | 0 |
| input_immutability | 40 | 0 |
| source_integrity | 1 | 0 |

## Limits

- Synthetic deterministic fixtures test mechanics only, not efficacy, fill feasibility, latency, or market coverage.
- Prefixes are clean event-time prefixes. Receipt ordering, provider revisions and delayed/backdated rows are not validated here.
- Frozen Watch uses existing exec_gain semantics; this audit does not replace the V1 event clock or validate feed construction.
- This does not independently verify live raw paths, candidate feature causality, serial-opportunity creation, or cutoff eligibility.
- Existing summary-only evidence lacks raw paths; later certification still needs a separate prospective freeze and source audit.

## CURRENT STATE

- CONTROL: Source fingerprint checked before and after; no collector writes.
- NEW SHADOW: Undeployed offline mechanism tests only.
- BLOCKED: Prospective performance and live data causality are not established.
- NEXT STEP: Preserve this audit and continue reviewing unchanged prospective evidence.
