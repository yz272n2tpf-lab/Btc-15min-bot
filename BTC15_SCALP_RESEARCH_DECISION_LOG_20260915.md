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

### 15-second cross-source parity (`brti15 / btc15 >= 1.00`)

**REJECTED decisively on fresh forward data.**

Frozen cutoff: **2026-09-15T04:51:00Z**.

Predeclared manual-review requirements were:

- >=30 completed baseline serial opportunities;
- >=15 observed baseline contracts;
- >=80% baseline opportunity-ID retention;
- >=90% baseline +10c winner-ID retention;
- hypothesis opportunity count >=80% of baseline count;
- +10c precision lift >=5 percentage points.

By 2026-09-15 09:09 ET the fresh sample had reached **61 baseline opportunities across 33 contracts**,
well beyond the required review sample. Results:

- baseline +10c rate: **82.0%**;
- parity +10c rate: **78.4%**;
- precision lift: **-3.6 percentage points**;
- winner-ID retention: **52.0%**;
- opportunity-count retention: **60.7%**;
- review status: **REVIEW_SAMPLE_READY_REJECTED**;
- auto-promotion: forbidden;
- production behavior: unchanged.

Parity therefore failed in both directions: it reduced +10c precision and discarded
far too many valid winners/opportunities. It must not be promoted, relaxed, or tuned
on this same fresh sample. In particular, do not lower the ratio from 1.00 and relabel
the same cohort as validation.

Fresh diagnostics repeatedly showed rejected candidates with parity ratios below 1.00
that later reached +10c and often +20c, confirming that strict 15-second BRTI/BTC parity
is not a safe binary entry gate for this blueprint.

## Current outcome structure

On the reviewed 60-opportunity lifecycle-projected development sample:

- +5c reached: 51/60 = 85.0%.
- +10c reached: 44/60 = 73.3%.
- Sub-10c outcomes: 16.
- Never armed +5c: 9.
- Armed +5c but stayed below +10c: 7.
- Of the six armed-sub10 paths that later hit the existing protected EXIT, only two exited positive.

This means the main remaining quality problem is false-start / entry selection,
not simply that the +10c reporting target is hiding a large pool of clean small wins.

A separate fresh-forward baseline cohort later showed stronger recent conditions
(82.0% +10c on 61 opportunities), but that is a different cohort and must not be
confused with FINAL UP/DOWN accuracy.

## False-start hypothesis evidence

Pre-entry profile of +10c winners vs never-armed failures showed:

- BTC/BRTI 5-second momentum: nearly the same.
- BTC30: not weaker in failures; failures were slightly stronger on median.
- 15-second support: weaker in failures, especially BRTI15.
- Confirmation count: no separation in the reviewed sample.
- ask5 / ask15 lag medians: no separation in the reviewed sample.

This was hypothesis-generation evidence only. The independent parity test above did
not validate strict 15-second cross-source parity, so that apparent development pattern
must not be converted into a hard gate by threshold tuning.

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

The consolidated scalp review currently has **115 completed serial opportunities** with
an overall **77.4% +10c meaningful-move rate**, **70 protected exits**, and a perfect
**100% first-4c-crossing correctness rate** on those protected exits.

Backend timer evidence has reached **532 valid samples out of 535 polls**, with:

- contract-match rate: **100%**;
- canonical-clock rate: **100%**;
- within-5s rate: about **99.6%**;
- fetch failures treated separately from valid samples.

The only hard freeze blocker left in the consolidated review is the intentionally manual:

`TIMER_VISUAL_ACCEPTANCE_PENDING`

Do not clear that blocker without an actual user visual check.

## Next research rule

Do **not** add another hard threshold immediately. Three tightening paths have now failed
(BTC30>=20, normalized momentum, strict 15-second parity). The next entry-quality step
should be an independent replication/diagnostic study on fresh failures, with no live
suppression, to determine whether any pre-entry pattern repeats consistently across
cohorts. If no stable replicated pattern emerges, freeze the current scalp qualification
and lifecycle architecture rather than over-layering it.
