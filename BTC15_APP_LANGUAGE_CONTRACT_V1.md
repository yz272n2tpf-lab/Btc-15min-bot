# BTC15 App Language Contract V1

**DISPLAY / WORDING ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS**

## Goal
The finished app must explain what the bot sees and what the user should do in plain English without exposing backend lifecycle jargon or implying the user owns a position when the app told them not to enter.

## Permanent hierarchy
1. **FINAL OUTCOME** — where the contract is most likely to finish.
2. **EARLY OPPORTUNITY** — directional value before Kalshi fully prices the side.
3. **SCALP / REVERSAL** — intracontract move opportunity, independent of FINAL.
4. **ENTRY GUIDANCE** — whether the current price is attractive enough to act on manually.
5. **PROTECTION / EXIT** — only user-facing when a manual entry was reasonably available; model-only tracking must be labeled as such.

## Entry-price wording
- 25–35c: **IDEAL ENTRY**
- 36–50c: **GOOD ENTRY**
- >50c: **NO ENTRY · DON'T CHASE**
- <25c: **LOW PRICE · CHECK SIGNAL** until the underlying signal is independently qualified.

Price labels are guidance/telemetry only unless the already-protected module itself qualifies the signal. Price must never become a hidden strategy filter.

## SCALP wording
### No qualified scalp
- Header: **WATCHING FOR SCALP**
- Detail: **Waiting for a qualified move**

### Qualified, attractive price
- Header: **UP SCALP #N** or **DOWN SCALP #N**
- State: **SCALP ACTIVE**
- Entry line: **IDEAL ENTRY** or **GOOD ENTRY** with price.

### Qualified, but >50c
- Header: **UP/DOWN SCALP #N · TRACKING ONLY**
- Main line: **MOVE VALID · NO ENTRY · DON'T CHASE**
- Protection line: **MODEL TRACKING ONLY · no manual position assumed**
- Never show user-facing **PROTECT PROFITS** or **EXIT** as though a manual position is assumed.

### Protection after an attractive/manual-entry path
- State: **PROTECT PROFIT**
- Detail: **Move reached protection level · watch for giveback**

### Valid protected exit
- State: **EXIT / PROTECT PROFIT NOW**
- Completed memory: **#N COMPLETE · PROTECTED EXIT · WATCHING FOR #N+1**

### ENDED_UNARMED lifecycle
Backend term stays internal.
User-facing wording:
- **#N ENDED · NEVER REACHED PROTECTION · WATCHING FOR #N+1**
- This is not an EXIT instruction.

## EARLY wording
### Not qualified
- **EARLY WATCH**
- Brief reason: price too high, edge too small, evidence not ready, or contract sync/feed issue.

### Qualified
- **EARLY UP** / **EARLY DOWN**
- Show actual Kalshi ask and fair probability separately.
- Show **IDEAL ENTRY** / **GOOD ENTRY** when <=50c.
- Never imply an EARLY call is a FINAL LOCK.

## FINAL wording
### Not protected/locked
- **FINAL WATCH**
- Show current bias/confidence and reason it is not locked.

### Protected FINAL
- **FINAL LOCK · UP** / **FINAL LOCK · DOWN**
- Show confidence and minutes left.
- Show locked-side Kalshi ask separately.
- If ask >50c, label **OUTCOME LOCK · ENTRY EXPENSIVE** rather than presenting it as a desirable new entry.
- FINAL correctness and entry economics are separate concepts.

## Contract rollover
At rollover:
- old completed scalp may remain briefly as clearly historical context only;
- no stale ACTIVE/PROTECT/EXIT instruction may carry into the new contract;
- new timer/contract becomes the only actionable contract authority.

## Safety wording rules
- Use **UP / DOWN**, never “short.”
- No backend jargon such as `ENDED_UNARMED`, `candidate_id`, bridge version, or parity diagnostics in the normal user view.
- No numeric flip-risk percentage until separately calibrated and validated.
- No wording that implies an order was placed.
- No automatic-trading language.
- Manual execution only.

## Layout stability
- Reason/explanation text must not resize or move the main FINAL card vertically.
- Completed scalp context must not make the active card disappear instantly.
- One visible contract timer.
- Core action/state words should remain fixed-position and glance-readable on iPhone and iPad.

## Status
Frozen as the wording target for the later dedicated polish pass. This document does not modify strategy logic or the currently running dashboard.
