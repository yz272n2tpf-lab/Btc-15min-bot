# 24H COST BASELINE — 2026-09-18

Railway 24h engineering metrics, sampled at 30m. Not invoice/bill totals.

| service | avg RAM GB | max RAM GB | avg vCPU |
|---|---:|---:|---:|
| Btc-15min-bot | 4.397 | 4.575 | 0.485 |
| scalp-unarmed-live-tape-v1 | 5.505 | 8.309 | 0.495 |
| scalp-coverage-rescue-forward-v1 | 3.015 | 5.778 | 0.123 |
| scalp-specialist-review-v3 | 3.242 | 7.109 | 0.062 |
| scalp-blueprint-forward-v1 | 3.246 | 6.708 | 0.184 |

Incremental adapter is too new for its 24h average to be representative; current RAM reached ~1.56 GB while holding/rebuilding the ~350 MB source snapshot. This reinforces that the adapter must itself evolve to disk/bounded streaming if retained long-term.

Implications:
- Unarmed is the highest priority post-parity RAM target.
- Main bot is a persistent independent cost center and belongs in the original plumbing/infrastructure remediation.
- Coverage/Gap/Blueprint have burst peaks >5-7 GB, consistent with full-tape object graph reconstruction.
- Cost target cannot be achieved merely by private networking; bounded state / freeze-and-stop is required.
