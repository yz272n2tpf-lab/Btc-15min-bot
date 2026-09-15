# BTC15 Combined Forward Rollover Integrity — 2026-09-15

## Status

The running `combined-forward-scorecard-v1` sample is **DIAGNOSTIC ONLY** and must not be used as final authoritative common-universe evidence.

## Finding

The V1 observer reads `scalp-display-bridge-v6/combined-state`. Around contract rollover, V6 can briefly return 503 while its upstream combined-state and scalp-state contract IDs disagree. This is correct fail-closed display behavior, but it creates a research-observation gap.

Observed live examples:

- 18:00 UTC rollover: new contract first accepted at roughly +32 seconds.
- 18:15 UTC rollover: new contract first accepted at roughly +45 seconds.

V1 then labeled those as fully observed contracts even though the opening 30–45 seconds were not observed through V6. That can undercount very early EARLY or SCALP opportunities and therefore bias union coverage.

## Root cause

V6 is a display enrichment bridge. It reads the frozen V5 combined-state plus frozen V5 scalp-state and requires their contract IDs to match before returning an enriched payload. During rollover, main contract authority can advance before the scalp source does.

The underlying V5 combined-state already behaves correctly for research composition:

- main dashboard owns the canonical contract and timer;
- EARLY and FINAL remain available from main authority;
- if scalp contract is not aligned, SCALP is forced to PASS / fail-closed rather than blocking EARLY/FINAL;
- no order path exists.

## Required replacement

`BTC15_COMBINED_FORWARD_SCORECARD_V2.py` is the required authoritative observer design.

V2 semantics:

1. Read frozen V5 combined-state directly for immediate main contract/timer + EARLY/FINAL authority.
2. Read frozen V5 scalp-state separately.
3. Capture EARLY/FINAL even while scalp is temporarily on the prior contract.
4. Merge serial scalp evidence only after scalp contract alignment and freshness/integration readiness.
5. Record first-seen canonical seconds-left for every contract.
6. Only contracts first seen within **5 seconds** of the canonical 15-minute start are eligible for the common-universe gate.
7. Late-seen contracts remain diagnostic only and cannot inflate the 30-contract / 25-settled threshold.
8. Union coverage still counts each contract once regardless of serial scalp count.
9. No signal thresholds, price filters, lifecycle rules, EARLY logic, FINAL logic, Kalshi integration, or order behavior change.

## Decision

- Do **not** use V1 30/25 results for promotion, freeze, or production decisions.
- Keep V1 only as diagnostic evidence until V2 is the active validated observer.
- Preserve production, V5/V6/V12, BTC30-missing research, and FINAL V2 unchanged.
- No auto-promotion.
- Signal only / manual execution / no orders.
