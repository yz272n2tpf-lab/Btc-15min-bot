# BTC15 Protected EARLY Forward Confirmation Freeze — 2026-09-15

**Research / confirmation only · signal only · manual execution · no orders**

This note freezes the semantics of the new EARLY forward confirmation before any
live EARLY result from the new collector is reviewed.

## Protected producer is authority

The scorecard does not qualify EARLY. It reads the already-protected production
EARLY state through `btc15_main_protected_state_adapter_v1.py`.

Recovered source facts from the protected producer:

- preferred-side Kalshi ask <= **45c**;
- target-aware model fair >= **75%**;
- model edge versus ask >= **8 percentage points**;
- **2 to 10 minutes** left in the contract;
- absolute BTC distance from the Kalshi target >= **$25**.

The producer emits `OPPORTUNITY` / `entry_tournament_ready`; the protected main
adapter maps that already-protected state to `EARLY QUALIFIED`.

No threshold above may be changed by the confirmation collector.

## Coverage universe

Protected EARLY cannot qualify before the 10:00-remaining boundary. Therefore:

- startup contract is excluded;
- fresh sample arms only on the first post-start contract rollover;
- a later contract enters the EARLY coverage denominator only if the collector
  first sees it with **>=600 seconds remaining**;
- a contract first seen below 600 seconds is excluded fail-closed because an
  earlier EARLY opportunity could have been missed.

This is intentionally different from requiring second-zero observation. It is
the earliest observation needed to score the protected EARLY window honestly.

## Frozen review sample

Do not declare the EARLY confirmation sample ready until both are true:

- >= **30 eligibility-complete contracts**;
- >= **12 officially settled protected EARLY calls**.

## Metrics kept separate

Report separately:

- EARLY-only actionable coverage;
- first EARLY Kalshi ask;
- ideal **25–35c** count/rate;
- <=50c count/rate;
- minutes remaining;
- model fair;
- model edge;
- official settlement same-side rate as a **secondary directional metric**.

EARLY is an opportunity path, not FINAL outcome authority. A later contract
settlement reversal must not retroactively erase the fact that an EARLY entry
was attractive; settlement direction and entry economics remain separate.

## Guardrails

- no EARLY threshold edits;
- no hidden price filter;
- no numeric flip-risk percentage;
- no production behavior change;
- no auto-promotion;
- no orders;
- no auto trading.
