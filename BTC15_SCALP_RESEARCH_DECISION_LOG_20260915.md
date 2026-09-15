# BTC15 SCALP Research Decision Log — 2026-09-15

**Research / shadow only · signal only · manual execution · no orders**

This file freezes the current research decisions so later work does not reopen
rejected paths or silently reinterpret descriptive evidence as a live rule.

## Stable shadow architecture

- Current serial lifecycle shadow: V5.
- Current shadow dashboard: V10.
- ENDED_UNARMED is lifecycle metadata only, never a sell/exit instruction.
- An armed scalp with no validated 4c giveback EXIT remains protected/blocking.
- Production EARLY, FINAL, Kalshi quotes, canonical timer, and order behavior are untouched.
- No order path exists in this research work.

## Lifecycle / coverage conclusions

- Safe ENDED_UNARMED reset resolves stale never-armed lifecycle state after collector RESULT.
- True post-exit meaningful +10c misses observed by the broader audit: 0 at review time.
- Failed-prearm adverse/time release tournament did not add measured coverage beyond lifecycle reset.
- Therefore no pre-arm stop-loss/release rule was selected.

## Rejected tightening paths

### BTC30 >= 20

Rejected by holdout. Development improved only slightly and fresh holdout did not
support the nominee with acceptable winner retention. Keep the reviewed BTC30
blueprint unchanged.

### btc5_norm / btc15_norm floors

Rejected before holdout because neither predeclared normalized-momentum feature
produced a development nominee under the locked precision + retention gate.

## Current outcome structure

On the reviewed 60-opportunity lifecycle-projected sample:

- +5c reached: 51/60 = 85.0%.
- +10c reached: 44/60 = 73.3%.
- Sub-10c outcomes: 16.
- Never armed +5c: 9.
- Armed +5c but stayed below +10c: 7.
- Of the six armed-sub10 paths that later hit the existing protected EXIT, only two exited positive.

This means the main remaining quality problem is false-start / entry selection,
not simply that the +10c reporting target is hiding a large pool of clean small wins.

## False-start hypothesis evidence

Pre-entry profile of +10c winners vs never-armed failures showed:

- BTC/BRTI 5-second momentum: nearly the same.
- BTC30: not weaker in failures; failures were slightly stronger on median.
- 15-second support: weaker in failures, especially BRTI15.
- Confirmation count: no separation in the reviewed sample.
- ask5 / ask15 lag medians: no separation in the reviewed sample.

This is hypothesis-generation evidence only. The reviewed 60-opportunity sample
must never be relabeled as independent validation for a new rule.

## Frozen collector constants recovered read-only

- BTC5_MIN = 4.0
- BTC15_MIN = 8.0
- BTC5_STRONG = 10.0
- BTC15_STRONG = 15.0
- BRTI5_STRONG = 8.0
- BRTI15_FLOOR = 0.0
- BTC30_FLOOR = -5.0
- MIN_ACCEL = 4.0
- MIN_LEFT = 120.0 seconds
- CONFIRM_WINDOW = 4.0 seconds
- CONFIRM_COUNT = 2

These are source facts, not permission to retune the reviewed blueprint.

## Fresh-forward hypothesis now frozen

**Single hypothesis:** 15-second cross-source parity

`brti15 / btc15 >= 1.00`

Fresh cutoff: **2026-09-15T04:51:00Z**.

The hypothesis validator must collect only data at/after this cutoff. It compares
current baseline serial lifecycle behavior with a research projection that skips
candidates failing parity. Existing V5/V10 display behavior is not suppressed.

Manual-review gate (predeclared before fresh results):

- >=30 completed baseline serial opportunities;
- >=15 observed baseline contracts;
- >=80% baseline opportunity-ID retention;
- >=90% baseline +10c winner-ID retention;
- hypothesis opportunity count >=80% of baseline count;
- +10c precision lift >=5 percentage points.

Even if all conditions pass, **no auto-promotion is allowed**. A pass earns manual
review and, if desired, a later independent confirmation phase. It does not
change production or the stable V5/V10 shadow automatically.

## First fresh parity observation — warning only

The first completed baseline opportunity after the frozen cutoff was a DOWN scalp
that reached +10c and later completed a valid protected EXIT. Its entry evidence was:

- BTC15 side-aligned move: about 17.70;
- BRTI15 side-aligned move: about 12.03;
- BRTI15/BTC15 parity ratio: about 0.680;
- parity rule result: rejected;
- baseline result: +10c winner.

Therefore the first fresh observation is a **lost-winner warning** for parity 1.00.
This is not enough data to reject or retune the hypothesis. Do not lower the ratio,
sweep alternatives, or restart the cutoff from this one observation. Winner-ID
retention remains the primary safety metric while the predeclared fresh sample grows.

A dedicated diagnostics observer now records direct parity rejects and any baseline
+10c winner IDs lost by the hypothesis without changing the hypothesis itself.

## Production isolation / visual parity audit

- Railway production service `Btc-15min-bot` is confirmed sourced from branch `main`.
- Research/shadow work remains on `scalp-move-shadow-v1-20260912`.
- Research branch is additive and isolated from the production auto-deploy source.
- The newer production render-fix delta was reviewed as display-only: stronger removal/
  hiding of the retired V8.1 overlay plus safer idempotent patch behavior.
- That display-only render fix was synced into the shadow branch so V10 visual review
  more closely matches current production layout behavior.
- Production's newer inline scalp diagnostic wrapper still uses the existing SCALP card,
  owns neither EARLY nor FINAL, adds no overlay, and has no order path.

## Freeze-review status

The consolidated scalp review reached the backend timer sample requirement with
perfect contract-match and canonical-clock rates on valid samples. Protection
first-crossing audit was also perfect on the reviewed protected exits. The only
hard freeze blocker left in that consolidated review is the intentionally manual:

`TIMER_VISUAL_ACCEPTANCE_PENDING`

Do not clear that blocker without an actual user visual check.
