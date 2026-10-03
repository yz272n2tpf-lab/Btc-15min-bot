# BTC15 V2 focused functional verification

Candidate: `BTC15_LADDER_COMPLETION_20261003_V2`.

Local final gate: **89/89 tests passed** under Python3.12, including the Node dashboard DOM contract check. Manifest SHA256: `2b15692e33837dacfa33a71f421b56d7e8f52d065d7c9063085bbe0280399d2e`.

Run from repository root:

```
python btc15_verify_ladder_freeze_v2.py
python -m unittest test_btc15_ladder_completion_v1 test_btc15_scalp_journal_v1 test_btc15_product_logic_v2 test_directional_position_manager_v1
```

The companion V8.1 artifact also passed `btc15_verify_ladder_freeze_v2.py --lane v81`. Both runtime entry points verify the pinned bytes before startup.

The focused gate covers:

- retained EARLY entry membership, actual ask, no FINAL entry veto and immutable origin;
- independent FINAL, genuine linked confirm/strengthen/weaken/MIXED/opposition/flip, material confirmation loss, clearance without unlatching PROTECT;
- UP and DOWN SCALP entry,5c arm,4c giveback, overshoot at actual bid, latched EXIT across restart,180second horizon at actual later bid, no stale or fabricated fills;
- serial ownership, reversal/re-entry only after explicit EXIT and new confirmation;
- target/stop chronology, MFE/MAE, missing paths and immutable causal prefixes;
- causal feature lookbacks, wrong contract/target, stale/future inputs, sequence rollback, duplicate quote rejection;
-5M/3M warning authority and informational flip-risk;
- atomic journal/state rollback, durable SCALP EXIT before publication, contract quiet/missing denominator, bounded records, separate BRTI closeout and official Kalshi final-result receipts;
- byte-identical recovered protection modules, unchanged protected native source, generated installer compilation;
- existing dashboard card IDs, independent probabilities, HOLD, current/historical EXIT bids, wrong-candidate rejection, monotonic expiry and hidden-page invalidation.

The UI check executes the production JavaScript against the generated card structure and synthetic processor outputs. It is a DOM functional check, not a screenshot/browser visual inspection. The available Playwright package had no installed Chromium binary; no browser or infrastructure installation was undertaken.

These are functional/adversarial checks, not a historical policy backtest, live-market qualification, reliability estimate or claim of profitable execution. Runtime publication still requires the brief later approved live wiring check. No Railway approval was requested and no runtime was changed in this mission.

Hosted CI status is recorded on PR #53 for the exact published commit. This file deliberately does not claim a hosted result before the run completes.
