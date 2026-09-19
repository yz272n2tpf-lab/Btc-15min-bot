# BRTI FIX SCORECARD — PASS/FAIL ONLY

| Gate | Required | Result |
|---|---|---|
| Recurring upstream owners | exactly 1 | PENDING |
| Consumer direct CF calls | 0 | PENDING |
| True upstream age | <=5.0s normal operation | PENDING |
| Sustained HTTP 429 | near-zero; no storm | PENDING |
| Retry behavior | bounded/backoff; no burst | PENDING |
| Consumer scaling | no upstream cadence increase | PENDING |
| Upstream timestamp | preserved end-to-end | PENDING |
| +/-$11 wait-zone | exact protected semantics | PENDING |
| FINAL authority | exact protected semantics at same boundary | PENDING |
| KXBTC15M ticker/open/close/target | exact parity | PENDING |
| Contract rollover | clean, no duplicate poller | PENDING |
| Restart recovery | stale remains stale; automatic recovery | PENDING |
| Health vs readiness | alive != qualified/fresh | PENDING |
| Internal transport | Railway private network | PENDING |
| Latency | no regression | PENDING |
| Cost | no material regression | PENDING |
| Orders | false / signal-only | PENDING |

Overall status: PENDING

Rule: any failed semantic/freshness/safety gate = BRTI NOT FIXED. If single-owner HTTP cannot meet <=5s sustainably, stop interval tuning and evaluate supported streaming/push or alternate authoritative source.
