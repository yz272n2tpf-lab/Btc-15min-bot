# BTC15 SCALP lifecycle state spec V1

**RESEARCH / SHADOW ONLY · SIGNAL ONLY · NO ORDERS**

This spec separates **trade management** from **state lifecycle** so the dashboard cannot stay stuck on an already-completed scalp.

## Frozen behavior that does not change

- Frozen qualification remains: `seconds_left >= 120`, side-aligned `btc30 >= 15`.
- There is **no Kalshi entry-price eligibility filter**. Entry price remains telemetry only.
- `ACTIVE` means the qualified scalp has not yet armed profit protection.
- `PROTECT` begins after executable gain reaches `+5c`.
- `EXIT` is the existing protected management exit on the first observed `4c` giveback from the running executable peak after protection has armed.
- Protected `EXIT` remains latched.
- EARLY and FINAL are independent and untouched.
- Manual execution only. No order-placement path exists.

## Lifecycle gap

A qualified scalp can receive a collector `RESULT` before ever reaching `+5c`. Today that candidate can remain displayed as `ACTIVE` even though its observation is complete. That is misleading and can prevent the next qualified scalp in the same 15-minute contract from being surfaced.

## Research-only terminal state

### `ENDED_UNARMED`

Definition:

- matching collector `RESULT` has been received;
- the scalp never reached the existing `+5c` arm point;
- no protected `EXIT` occurred.

Meaning:

> The scalp observation ended and profit protection never armed.

`ENDED_UNARMED` is **not** a sell signal, stop-loss, or validated trading exit. It carries no instruction to exit a real position. It only closes the stale dashboard/state-machine lifecycle after the collector itself has finished that candidate.

## Proposed shadow lifecycle

`PASS -> ACTIVE -> PROTECT -> EXIT -> RESET`

or, when protection never arms:

`PASS -> ACTIVE -> ENDED_UNARMED -> RESET`

The second path is allowed for **shadow lifecycle / handoff research only** until live evidence is reviewed. It does not replace the separate failed-pre-arm stop-loss research.

## Serial scalp behavior

After a terminal state, resume scanning the same 15-minute contract for the next frozen-qualified candidate. There is no artificial scalp-count cap. A contract may therefore surface scalp #1, #2, #3, #4, etc., provided each new scalp qualifies after the preceding scalp reaches a valid lifecycle terminal.

- After `EXIT`, the terminal timestamp is the protected-exit timestamp.
- After research-only `ENDED_UNARMED`, the terminal timestamp is the collector `RESULT` timestamp.
- An incomplete candidate cannot be auto-terminated.
- A candidate that armed `+5c` but has no validated protected `EXIT` cannot be reclassified as `ENDED_UNARMED`.

## Dashboard copy guardrail

If this lifecycle state is later accepted for shadow UI, use wording such as:

**SCALP ENDED · PROFIT PROTECTION NEVER ARMED**

Do **not** use `SELL`, `EXIT NOW`, `CUT LOSS`, or similar actionable language unless a separate loss-management rule is independently validated.

## Promotion gate

Do not promote `ENDED_UNARMED` handoff into the production dashboard until:

1. unit/integration tests pass;
2. live event-tape audit shows the state matches completed collector results correctly;
3. post-terminal secondary candidates are measured separately;
4. no frozen +5c / 4c protection behavior changes;
5. no price filter is introduced;
6. timer/contract alignment still passes;
7. user explicitly reviews the behavior before freeze.
