# BRTI DURABLE FIX — EVIDENCE + ACCEPTANCE GATE (2026-09-19)

## Observed root-cause evidence
- Production main contains multiple direct CF Benchmarks BRTI request paths: startup diagnostic, FINAL authority request, and a parity thread explicitly polling once per second.
- Existing brti-shared-feed-v1 also defaults to 1.0s polling with 1.35s qualification age.
- Existing shared feed observed 154,959 upstream attempts, 28,367 HTTP 429s, 81.7% success at captured boundary, with stale-age excursions into hundreds of seconds.
- Isolated 3s/5s canary initially recovered but later accumulated 429s and stale ages while legacy direct callers remained active; therefore this is NOT a clean one-owner cadence result.
- Shared-consumer canary successfully consumed the private shared observation with true upstream timestamp, e.g. age 2.5s, preserved target gap/side and authority-ready behavior, while adding no direct upstream BRTI request.
- Protected main continued to emit DIRECT/PARITY HTTP 429 warnings during the canary period.

## Non-negotiable semantics
- True BRTI upstream-success/publication age <=5.0s for authority.
- Existing +/-$11 wait zone unchanged.
- Existing Kalshi target/contract clock semantics unchanged.
- Stale/error source fails closed; a consumer read must never refresh an old BRTI timestamp.
- Signal only. NO ORDERS.
- Private Railway service-to-service transport.
- No performance/quality degradation to save cost.

## Durable-fix acceptance — ALL required
1. Exactly ONE process owns recurring Kalshi CF Benchmarks BRTI upstream requests.
2. Production consumers make ZERO recurring direct CF BRTI requests, including diagnostics/parity.
3. Consumer count does not change upstream request cadence.
4. Upstream timestamp/value/sequence are preserved end-to-end.
5. Authority uses locally recomputed age from upstream timestamp, max 5.0s.
6. +/-$11 wait-zone and FINAL/EARLY downstream semantics match protected behavior at identical captured boundaries.
7. Sustained 429 rate is near zero over a meaningful run; no retry storm after 429.
8. Freshness remains within <=5s during normal operation; stale periods fail closed immediately and recover automatically.
9. Restart and KXBTC15M rollover do not duplicate pollers or reset stale data as fresh.
10. Health/readiness distinguish process alive vs BRTI qualified/fresh.
11. Internal consumer reads use Railway private networking and do not create public egress.
12. NO ORDERS / manual execution unchanged.
13. Rollback is one switch back to protected transport/config if any semantic/freshness regression occurs.

## Decision boundary
If a truly isolated single HTTP owner cannot sustainably provide <=5s true BRTI age without material 429/stale excursions, STOP tuning polling intervals. Treat Kalshi HTTP /values as incompatible with the required authority SLA and investigate a supported streaming/push transport or alternate authoritative BRTI source. Do not weaken the <=5s rule merely to make HTTP polling pass.
