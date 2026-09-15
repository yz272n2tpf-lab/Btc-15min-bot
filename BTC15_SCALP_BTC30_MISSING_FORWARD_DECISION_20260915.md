# BTC15 BTC30-Missing Fresh-Forward Decision — 2026-09-15

**Research / shadow only · signal only · manual execution · no orders**

## Decision

**REJECTED. Do not promote the missing-BTC30 recovery rule into V5 or production.**

The fresh-forward observer used a frozen cutoff of **2026-09-15T14:16:00Z**. The hypothesis under test was narrow: when the frozen raw collector already emitted a candidate but BTC30 was unavailable, test whether the candidate could be recovered instead of being rejected solely for missing BTC30. When BTC30 existed, the reviewed V5 BTC30 rule remained unchanged. Kalshi price stayed evaluation telemetry rather than a hidden eligibility filter.

## Fresh-forward result at decision

Status: **REVIEW_SAMPLE_READY_REJECTED**

At the first sample-ready rejection:

- baseline serial opportunities: **36** across **20** contracts;
- baseline +10c rate: **58.3%**;
- projected opportunities with recovery: **40**;
- projected +10c rate: **70.0%**;
- apparent +10c lift: **+11.7 percentage points**;
- baseline opportunity-ID retention: **66.7%**;
- baseline +10c winner-ID retention: **66.7%**;
- recovered missing-BTC30 opportunities: **14** across **14** contracts;
- recovered +5c rate: **92.9%**;
- recovered +10c rate: **92.9%**;
- recovered entries at or below 50c: **5**;
- recovered <=50c +10c rate: **80.0%**.

The observer remained rejected as the sample continued. Later baseline opportunity-ID retention fell to about **63.2%** and winner retention to about **63.6%**.

## Why it is rejected despite strong recovered candidates

The recovered subset itself looked strong, including useful <=50c entries. However, serial lifecycle interaction matters: an earlier recovered candidate can occupy the serial scalp slot and prevent a later frozen-baseline candidate from becoming the active opportunity. The fresh-forward projection therefore cannot be judged by recovered-candidate precision alone.

The rule displaced too many existing baseline opportunities and winners. The retention failure is materially worse than the predeclared preservation requirement, so the apparent precision/coverage lift is not safe to promote.

## Frozen follow-up rule

- Do **not** loosen V5 to accept candidates merely because BTC30 is missing.
- Do **not** tune a secondary missing-BTC30 filter on this same decision sample.
- Preserve the existing V5 serial lifecycle and qualification architecture.
- Treat the attractive missing-BTC30 examples as diagnostic evidence only.
- Any future revisit requires a materially different, independently motivated hypothesis and a new fresh cutoff.
- No production behavior changes are authorized by this test.

## Safety

- Production untouched.
- V5 qualification untouched.
- +5c protection arm / 4c giveback EXIT untouched.
- Entry-price handling remains telemetry/guidance only.
- No stop-loss added.
- No orders or automated execution.
