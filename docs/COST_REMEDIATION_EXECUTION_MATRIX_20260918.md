# COST REMEDIATION EXECUTION MATRIX — 2026-09-18

## Current gates
| Component | State | Next gate |
|---|---|---|
| Public scalp CSV egress | 13/13 PRIVATE | continue monitoring |
| Incremental adapter V1 | LIVE / SUCCESS | retain until V2 + consumer canary pass |
| Disk adapter V2 | CODE + STATIC/FUNCTIONAL TESTS PREPARED | isolated runtime |
| Regime consumer canary | CODE + FAIL-CLOSED PARITY GATES PREPARED | isolated runtime |
| Protected Regime live | UNCHANGED | control only |
| Blueprint/Unarmed | PRIVATE, timer segments preserved/accounted | do not state-optimize until Regime pattern proven |
| Actual accrued dollars | NOT AVAILABLE VIA METRICS API | read Railway Usage/Billing UI with user |

## Cost-impact migration sequence
A. Shared adapter V2: target <=0.20 GB, hard <=0.35 GB.
B. Regime bounded-state canary: target <=0.75 GB, exact evidence parity.
C. Unarmed: current 24h avg ~5.50 GB, highest impact; special timer boundary.
D. Main BTC bot: 24h avg ~4.40 GB, but defer to original plumbing integrity work.
E. Gap/Coverage/Blueprint: ~3+ GB avg, peaks ~5.8-7.1 GB.
F. Remaining 2.5-3 GB forward/review services.
G. Holdouts: prefer evidence freeze-and-stop when objectives complete.

## Stop conditions
- source SHA/bytes/rows mismatch
- contract/opportunity identity mismatch
- cutoff or evidence segment drift
- health failure
- any orders/write capability
- public export fallback
- RAM target missed without clear next bounded-state fix

## Definition of cost-remediation complete
1. 13/13 private egress still verified.
2. Shared adapter within RAM threshold.
3. Eligible active research consumers incremental/bounded OR frozen/stopped with evidence preserved.
4. No protected evidence reset.
5. Main bot cost center handed to plumbing remediation with baseline.
6. Stabilized 24h run-rate measured.
7. Railway Usage/Billing actual accrued dollars recorded separately from projections.
