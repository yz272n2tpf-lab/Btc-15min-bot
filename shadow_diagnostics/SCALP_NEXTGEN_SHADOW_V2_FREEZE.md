# SCALP next-generation shadow V2 — revision R2

Activation state: **NOT ACTIVATED**. No V2 live observations or performance claims.

The previous document claimed a freeze at `2026-09-16T19:50:00Z`. That cutoff belongs to the earlier draft and is superseded for R2. Changes made afterward cannot be credited to that prospective window. Earlier Git history preserves the draft; none of the V1 freezes are changed.

R2 source boundary: `2026-09-16T21:33:15+00:00`.
R2 code/config/dependency fingerprint: `ec18e01e3c50cd3e52142e1451e28d985bbceeb1c602404d0aad6c51a20689c1`.

Before activation, pin this fingerprint and choose a new UTC cutoff later than deployment acceptance. Freeze both values in the deployment record. Missing timezone, missing pin, a changed fingerprint, or a cutoff older than the R2 boundary fails closed. A code change after activation requires another revision and fresh window. A separate prospective certification is still required after development comparison; no automatic or same-sample promotion exists.

## Experiment definitions

All families use unchanged V1 serial opportunity IDs and the same post-cutoff, fully observed contract universe. Quiet contracts stay in the coverage denominator. These are independent entry replays, not lane-specific portfolio simulations or live manual-trading alerts. Completed RESULT records are required by the inherited opportunity builder; the scorer refreshes every 180 seconds.

| Family | R2 experiments | Same-window controls |
| --- | --- | --- |
| SCALP-2 economics | Opportunity #2 only: ASK <=50c; ASK <=50c and >=360s left; ASK <=50c and strong evidence | Unfiltered V1 opportunity #2 |
| Candidate→Verify | Strong candidates enter immediately; other candidates need two distinct nonnegative executable quote events, one >=+1c, <=5s apart, within 30s, with ASK no more than 3c above initial ASK | Frozen immediate, 5s, 10s, 15s, 30s policies |
| Watch→Exit | Two qualifying >=0.5c drawdown observations, <=5s apart; or two successive declines, each <=5s apart, combined fall >=0.5c and current drawdown >=0.5c | Frozen 1c, 2c, 3c Watch thresholds; +5c arm / 4c giveback Exit |
| Selective Pullback | Both lanes enter immediately at <=50c. Balanced also enters immediately on strong evidence, otherwise waits <=30s for <=50c. Price-disciplined waits <=30s if initial ASK <=60c, otherwise <=60s | V1 immediate and six fixed target/window combinations: 50c/40c/35c × 30s/60s |

Strong means candidate-time confirm_count >=2, structure_ok explicitly true, BRTI PRIMARY_OK, all three reversal/against-side flags explicitly false, normalized BTC5 >=0.60 and BTC15 >=0.50. These thresholds are hypotheses, not demonstrated winners. Missing risk flags cannot qualify as strong.

V2 quote decisions reject missing/crossed quotes, negative or inconsistent clocks, and duplicate times. Missing quote events or >5s gaps reset Verify confirmation. V2 decisions are made before outcome scoring; appending later outcomes cannot move the entry. Scoring rebases to the actual ASK and subsequent observed BIDs. Frozen control helper files remain byte-identical.

## Accounting and evaluation

- Report retention, quiet-contract coverage, omitted control opportunities and their observed outcomes, unscoreable entries, and entries without protected exits.
- Pair entries by contract/candidate/opportunity ID. Economic deltas use the explicitly counted both-protected-exit subset. Conditional protected-exit averages are not total P&L.
- Compare Watch warning lead time on matching exited opportunities, >=5s lead improvement, exits lacking warnings, recovery to a new high, and unresolved warnings. Warning without an observed exit is not automatically a false alarm. New-high recovery is an explicitly labeled false-warning proxy.
- Watch does not execute exits. Exit time and gain must match across every Watch lane, not merely exit counts. Its reported economics retain the V1 economics scorer's subset. V1 Watch uses an epsilon at the arm boundary while V1 economics uses a strict comparison; the resulting discrepancies and number of fee-scoreable exits are disclosed rather than repaired in frozen code.
- Sub-cent Watch patterns may be rare at the actual quote granularity or sampling cadence. Synthetic timing success does not establish live usefulness.
- 100 full contracts / 100 serial signals is only an overall review floor. It does not establish per-lane sufficiency, significance, profitability, or eligibility for production.
- `/audit` exposes per-opportunity decisions/outcomes for reproduction against source SHA, code fingerprint, and window ID. No raw credentials are included.
- Errors clear old results; stale sources fail readiness; repeated source hashes can recover after a transient failure.

No production changes, collector writes, order routes, automatic promotion, or changes to frozen V1 service configurations.
