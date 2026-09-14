# BTC15 Combined SCALP UI Checkpoint — 2026-09-14

**Mode:** SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

## What is now proven

The protected-main JSON schema mismatch has been resolved. The combined bridge now reads the real nested production structure:

- canonical clock: `timer.seconds_left`
- Kalshi target/quotes: `market.*`
- protected EARLY: `early.*`
- protected FINAL: `final.*` plus recorded-final fields

Live `COMBINED_BRIDGE_V3` proof showed:

- numeric protected-main clock
- same-contract alignment
- stale SCALP fails closed
- fresh SCALP recovers automatically
- timer delta reached 0.7s in a fresh same-contract observation
- protected EARLY / FINAL remain separate authorities
- no orders

## Existing production DOM mapped read-only

The DOM probe logged IDs/function names only, never values.

Relevant existing card IDs include:

- FINAL: `finalCard`, `finalSide`, `finalConfidence`, `finalReason`, `finalAction`, `finalActionSub`, and existing FINAL watch/hold/protect/exit zones
- EARLY: `earlyState`, `earlyTitle`, `earlyFlow`, `earlyEntry`, `earlyCurrentPrice`, `earlyEdge`, and existing EARLY ladder rows
- SCALP: `scalpCard`, `scalpState`, `scalpFlow`, `scalpEntry`, `scalpCurrentPrice`, `scalpTargetStrip`, `scalpLadderEntry`, `scalpLadderHold`, `scalpLadderWatch`, `scalpLadderProtect`, `scalpLadderExit`
- contract/timer/quotes: `currentContract`, `timerRemaining`, `timerEnd`, `upOdds`, `downOdds`

The current dashboard render entry point remains `applyState`.

## Combined generalized SCALP UI V1

Prepared `BTC15_DASHBOARD_COMBINED_SCALP_UI_V1.py` on the research branch.

Design:

- existing locked dashboard layout only
- no new floating/overlay card
- protected EARLY and FINAL stay rendered by the protected main service
- replaces only the existing SCALP / REVERSAL card's legacy V8.1 inline feed
- consumes proven `/combined-state`
- price-agnostic generalized SCALP; no 30–45c eligibility wording
- ACTIVE -> PROTECT -> EXIT presentation
- +5c protection arm and validated 4c running-peak giveback EXIT are display-only reflections of the frozen management rule
- `COUNTERTREND_SCALP`, `MIXED_HORIZONS`, and `ALIGNED` context are surfaced instead of suppressing conflicting horizons
- browser feed loss, malformed envelope, or contract mismatch fails closed
- no numeric flip-risk percentage
- no orders

## Test result

One research deployment correctly failed before promotion because the older research branch did not contain a newer main-branch V8.1 helper module. The patch was made self-contained instead of copying or weakening production logic.

The corrected pre-production run then passed:

- **44/44 integration/UI unit tests**
- **BTC15 FULL VALIDATION + DASHBOARD SELF-TEST: PASS**
- dashboard files present on persistent volume
- read-only dashboard confirmed
- orders enabled by dashboard: **NO**
- combined SCALP UI self-test: **PASS**
- exact frozen Full-Time V2 collector SHA remained unchanged after return to live collection

## Production status

The main `Btc-15min-bot` dashboard service has **NOT** been changed by this work.
Protected FINAL, protected Tier-1 EARLY, and frozen generalized SCALP trading rules remain unchanged.

## Next gate

Validate the rendered combined SCALP card off-production/live against real PASS, ACTIVE, PROTECT, EXIT, stale-feed, contract-rollover, and countertrend states. Only after that passes should the legacy V8.1 scalp renderer on the main dashboard be replaced with the generalized combined-state renderer.
