# BTC15 SCALP Timer Visual Acceptance Checklist V1

**Manual visual acceptance only · no code mutation · no orders**

This checklist is the final hard blocker in the consolidated SCALP freeze review.
It must be completed by direct visual observation of the V10 shadow dashboard.
Backend timer evidence cannot substitute for this check.

## What to open

Use the current `combined-dashboard-shadow-v1` V10 shadow dashboard. Do not use an
older screenshot or a retired duplicate timer.

## Pass conditions

Observe the top-right **CONTRACT TIMER** through a normal contract and at least one
15-minute rollover.

A PASS requires all of the following:

- There is only one visible contract countdown.
- The visible countdown decreases normally; it does not freeze, jump backward,
  or blink between unrelated values.
- The SCALP card does not show a second competing contract countdown.
- Near rollover, the shadow may briefly fail closed while contracts synchronize,
  but it must not show a stale actionable SCALP from the prior contract.
- After rollover completes, the displayed contract and timer belong to the new
  contract.
- EARLY and FINAL remain present and visually stable during the rollover.
- No order/action control appears anywhere; this remains signal-only/manual execution.

## Fail conditions

Any of these is a FAIL and must keep `TIMER_VISUAL_ACCEPTANCE_PENDING` blocked:

- two visible contract timers;
- countdown differs materially from the authoritative main timer;
- old-contract scalp remains actionable after rollover;
- timer freezes or runs backward;
- contract label and timer belong to different contracts;
- EARLY/FINAL disappear or are replaced by the SCALP integration;
- any order-placement behavior appears.

## Backend evidence already collected

The consolidated reviewer independently reached its backend timer sample minimum
with perfect contract-match and canonical-clock rates on valid samples. That is
necessary but not sufficient; this visual check remains intentionally manual.

## Acceptance action

Do not change the review gate automatically. Only after the user visually confirms
all pass conditions should the separate manual review input be set to accepted.
