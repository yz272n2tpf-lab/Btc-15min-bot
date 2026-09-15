# BTC15 SCALP Manual Visual Acceptance — 2026-09-15

**Shadow/review only · signal only · manual execution · no orders · no auto-freeze of production**

## User visual confirmation

At approximately 2026-09-15 09:09 America/New_York, the user visually checked the current V10 combined shadow dashboard through a 15-minute contract rollover and reported that the visual timer behaviors appeared to work.

Observed details reported by the user:

- the prior contract displayed an `UP #1` scalp label through the end of that contract;
- the dashboard rolled to the next contract;
- the duplicate / second timer clock was gone;
- the user stated that the checked items appeared to work.

Interpretation:

- `UP #1` remaining on the prior contract until rollover is accepted as normal per-contract opportunity context;
- the clean rollover and absence of a second timer satisfy the intended single-visible-contract-timer behavior;
- this user report is recorded as the explicit human visual PASS required by the freeze-review checklist.

## Backend evidence attached at acceptance time

The live consolidated reviewer independently reported immediately before this acceptance:

- completed serial opportunities: 115;
- meaningful +10c rate: 0.774;
- protected exits: 70;
- first 4c protection crossing correctness: 1.000;
- timer valid samples: 532 / 535 total;
- timer contract-match rate: 1.000;
- canonical-clock rate: 1.000;
- timer within 5 seconds rate: 0.996;
- only remaining review blocker: `TIMER_VISUAL_ACCEPTANCE_PENDING`;
- orders: false;
- manual execution only.

## Manual freeze-review result

With the explicit visual PASS now supplied, the previously sole visual blocker is satisfied for the offline/manual review package.

**Status: `READY_FOR_MANUAL_FREEZE_REVIEW`**

This means the reviewed SCALP architecture is eligible to be frozen as the stable shadow baseline. It does **not** authorize an automatic production deployment, strategy promotion, order placement, or auto-trading.

## Architecture frozen for subsequent research

The stable baseline remains:

- full-contract scanning;
- serial scalp opportunities with no artificial opportunity-count cap;
- ENDED_UNARMED as non-actionable lifecycle metadata/reset only;
- armed/no-validated-exit remains protected/blocking;
- +5c arms protection;
- 4c giveback from executable peak is the protected EXIT rule;
- no pre-arm stop-loss selected;
- no new hard price-suppression filter selected;
- Kalshi entry price remains telemetry/guidance, not the frozen scalp trigger gate;
- V5 lifecycle semantics preserved;
- V10 single-visible-timer dashboard semantics preserved;
- EARLY and FINAL remain separate from SCALP ownership;
- signal-only / manual execution / no orders.

## Research separation

Rejected entry-quality hypotheses remain rejected and must not be silently retuned on the same evidence:

- BTC30 >= 20;
- btc5_norm / btc15_norm floors;
- 15-second cross-source parity `brti15 / btc15 >= 1.00`.

Any future entry-quality improvement must be tested as a separate fresh-forward research hypothesis without mutating the frozen lifecycle/protection/timer architecture.
