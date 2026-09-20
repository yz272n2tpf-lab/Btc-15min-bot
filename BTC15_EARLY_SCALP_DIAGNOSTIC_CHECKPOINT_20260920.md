# BTC15 EARLY + SCALP diagnostic checkpoint — 2026-09-20

**RESEARCH ONLY · SIGNAL ONLY · NO ORDERS · NO PRODUCTION CHANGE**

This note preserves the latest bounded diagnostic work. It does not promote a threshold, alter production, retune FINAL, or authorize auto-trading.

## EARLY — correct job definition

EARLY is the affordable opportunity lane. Its primary utility question is whether a cheap entry produces a tradable same-side Kalshi bid excursion after entry. Official settlement same-side rate is secondary context; FINAL remains settlement authority.

The preserved 1-minute EARLY architecture is too coarse for the pre-repricing job. Existing research already showed that the 1-minute and prior sub-minute model-selection attempts did not reliably meet the 93–95% directional target.

A fresh development-only re-read of the preserved sub-minute tape tested a small family of momentum/lead-lag hypotheses, always using actual Kalshi ask and later executable bid for excursion scoring.

Most promising bounded development family in this pass:
- cheap candidate universe: 6–10 minutes left, 20–40c ask;
- candidate side is still behind exact target but not deeper than $120;
- side-aligned BTC 15s >= +8;
- side-aligned BTC 30s >= +12;
- 15s Kalshi ask change <= +2c;
- side-aligned BTC 60s > 0.

Development result on the preserved 57-contract sub-minute set:
- calls: 33;
- coverage: 57.9%;
- average ask: 29.0c;
- average time left: 8.77m;
- +5c executable excursion: 93.9%;
- +10c executable excursion: 78.8%.

This is promising for earliness/economics but does **not** satisfy the full project target by itself and is not frozen/promoted from this note.

A related gap-bounded variant (same lead-lag family with side-aligned target deficit no worse than -$80) produced:
- calls: 33;
- coverage: 57.9%;
- average ask: 29.6c;
- average time left: 8.70m;
- +5c: 93.9%;
- +10c: 84.8%.

That is still development-only evidence and requires untouched post-freeze validation before any actionability change.

## SCALP — replicated false-start diagnostic

The current scalp architecture remains move-first / price-second. Kalshi price buckets remain telemetry/reporting, not separate detectors.

A development-only diagnostic was run on preserved event history using side-aligned move evidence and first candidate per contract/side:
- seconds_left >= 120;
- side-aligned BTC15 >= +8;
- side-aligned BTC30 >= +15.

This is an approximate diagnostic cohort, **not** a claim to reproduce the exact frozen serial-lifecycle sample.

The most consistent pre-entry separator was side-aligned BTC position relative to the exact Kalshi target:

Across three chronological chunks, candidates already on the candidate side of the exact target (side-aligned gap > 0) showed +10c rates of:
- chunk A: 100%;
- chunk B: 100%;
- chunk C: 88.9%.

Combined positive-gap diagnostic:
- n=40;
- +10c: 95.0%;
- +20c: 57.5%;
- avg ask: 36.9c;
- median ask: 40c;
- avg time left: 9.90m.

Positive-gap candidates with ask <=40c:
- n=21;
- +10c: 95.2%;
- +20c: 52.4%;
- avg ask: 31.3c;
- avg time left: 8.56m.

By contrast, candidates deeply behind the target (side-aligned gap <= -$75):
- n=37;
- +10c: 24.3%;
- +20c: 10.8%;
- avg ask: 19.8c.

Interpretation: the very cheapest entries can be cheap because the candidate side is still far behind the exact target. Exact-target position appears to be a materially stronger false-start diagnostic than simply tightening BTC30 or adding cross-source parity.

## Guardrails / next step

- Do not convert the gap observation directly into a new hard eligibility threshold.
- Do not split the move detector into price-bucket-specific detectors.
- Do not touch FINAL.
- Do not alter +5c arm / 4c giveback protection.
- Preserve ENDED_UNARMED as metadata-only reset and keep armed/no-exit blocking behavior.
- Preserve NO ORDERS.

Next bounded research step:
1. recover exact serial candidate membership if authenticated historical access becomes available;
2. otherwise use the already-running clean post-fix tape for independent replication;
3. predeclare one quality-tier hypothesis using exact-target position as context, freeze it before clean scoring, and test retention/coverage/entry economics;
4. keep current production scalp behavior unchanged unless untouched evidence supports promotion.
