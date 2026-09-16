# BTC15 Entry + Profit Ladder V1 — Frozen Holdout Result

**RESEARCH ONLY · SIGNAL ONLY · NO ORDERS · NO V1 RETUNE AFTER HOLDOUT**

Holdout reveal source SHA256: `f85a737220684cc2870c16145a32da96d9f781e61392cefd44a75eb2fe080e30`

Reviewer: `BTC15_SCALP_ENTRY_PROFIT_HOLDOUT_REVIEW_V1`

Coverage in this report means **retention of baseline-qualified signal contracts**, not true all-15-minute-contract coverage. The frozen Coverage Rescue forward scorer remains authoritative for true contract coverage.

## Validation-frozen roles

### FULL_RETENTION_QUALITY
Policy: `IMMEDIATE + RUNNER_10_4`

- Validation: 54/54 baseline-signal contracts retained; 85 signals; +10 = 78.82%; +20 = 35.29%; <=50c entries = 47.06%; avg ask = 52.24c; avg entry timing = 9.18m left; avg executable exit capture = 10.89c.
- Holdout: 54/54 retained; 76 signals; +10 = 55.26%; +20 = 27.63%; <=50c entries = 57.89%; avg ask = 44.56c; avg entry timing = 10.00m left; avg executable exit capture = 5.12c.

### AFFORDABLE_COVERAGE
Policy: `AFFORDABLE_15 + RUNNER_10_4`

- Validation: 49/54 retained = 90.74%; 66 signals; +10 = 72.73%; +20 = 39.39%; <=50c entries = 100%; avg ask = 27.38c; avg entry timing = 8.72m left; avg executable exit capture = 10.12c.
- Holdout: 51/54 retained = 94.44%; 68 signals; +10 = 52.94%; +20 = 27.94%; <=50c entries = 100%; avg ask = 26.54c; avg entry timing = 9.22m left; avg executable exit capture = 4.65c.

### SERIAL_PROTECTION
Policy: `IMMEDIATE + PROTECT_5_2`

- Validation: 54/54 retained; 98 signals; +10 = 74.49%; +20 = 32.65%; protected exit rate = 68.37%; 1.81 opportunities/covered contract; max serial index 3; avg executable exit capture = 10.56c.
- Holdout: 54/54 retained; 102 signals; +10 = 51.96%; +20 = 20.59%; protected exit rate = 65.69%; 1.89 opportunities/covered contract; max serial index 4; avg executable exit capture = 4.80c.

## Decision

`NO_PROMOTION_V1`.

The affordable-entry policy generalized well on **entry economics and baseline-contract retention**, but not on +10 conversion. The full-retention and serial-protection roles also showed material validation-to-holdout degradation in +10 movement/capture.

Do not retune V1 thresholds or select a different V1 policy after this holdout reveal. Any successor must be labeled a new hypothesis/version and must use a fresh future out-of-sample window for certification.

Exchange fees are not included. Executable exit capture is ASK-to-later-BID movement telemetry, not a net-profit claim.
