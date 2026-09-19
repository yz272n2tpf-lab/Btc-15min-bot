# BRTI CUTOVER / ROLLBACK RUNBOOK — 2026-09-19

## Preconditions
- Replacement shared owner passes BRTI_DURABLE_FIX_ACCEPTANCE_20260919.md.
- Candidate consumes private shared state with true upstream timestamp.
- Protected production branch/commit and Railway variables captured before change.
- No strategy/model/threshold/contract-timing changes bundled with transport cutover.

## Atomic cutover
1. Keep protected production serving while shared owner is already healthy/fresh.
2. Enable BTC15_USE_SHARED_BRTI=1 and private BTC15_BRTI_SHARED_URL on candidate/main deployment.
3. Confirm startup diagnostic says BRTI direct request SKIPPED because shared owner owns upstream.
4. Confirm FINAL authority and parity collector read shared timestamp/value and do not call CF endpoint.
5. Observe at least one active-contract continuation and one KXBTC15M rollover.
6. Compare ticker/open/close/target, BRTI value/age/gap/side, +/-$11 wait-zone decision, FINAL authority state.
7. Verify upstream owner request counters do not change as consumers are added.
8. Verify no consumer public egress for shared BRTI.
9. Only after gates pass, retire legacy direct-BRTI pollers/shared-feed duplicates and temporary canaries.

## Immediate rollback triggers
- shared observation true age >5s in normal operation outside a demonstrated upstream outage;
- any contract/target/clock drift;
- any +/-$11 or FINAL authority semantic mismatch at same input boundary;
- consumer direct CF request detected;
- duplicated upstream owner/poller;
- restart or rollover marks stale data fresh;
- new latency/reliability regression;
- any order-capable behavior.

## Rollback
- Restore BTC15_USE_SHARED_BRTI=0 / protected transport configuration and protected branch/commit.
- Do not modify strategy/model thresholds during rollback.
- Keep evidence/logs from failed cutover.
- Production remains fail-closed if BRTI is stale/unavailable.
- NO ORDERS throughout.
