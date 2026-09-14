# BTC15 Generalized Scalp — Scorecard / Forward-Test Freeze

**Status:** research only, signal-only, NO ORDERS  
**Branch:** `scalp-move-shadow-v1-20260912`  
**Development-tape freeze:** `2026-09-14T02:24:03.366238Z`  
**V2 full-time collector boundary:** `2026-09-13T13:09:01Z`

## Safety / anti-drift

- Do not modify locked V8.1, FINAL, or EARLY logic from this scorecard.
- Do not use Kalshi entry-price bucket as scalp eligibility. Price bands remain telemetry only.
- Do not tune the running generalized collector during the forward confirmation window.
- No automatic orders.
- Reversal-risk percentage remains hidden until a separate calibrated risk model earns validation.
- Any rule described below was discovered using the development tape and therefore is **not promoted** by the descriptive chronological split alone.

## Tape integrity at freeze

Uploaded persistent research tape contained:

- `68,960` total rows
- `242` CANDIDATE rows
- `240` completed RESULT rows
- `40,877` five-second PATH rows
- `27,601` SNAPSHOT rows

Across the full persistent tape, 90 settled contracts were observed and 72 had at least one completed generalized candidate: **80.0% raw candidate-bearing contract coverage**.

## V2 full-time forward subset

Using only rows at/after `2026-09-13T13:09:01Z`:

- 176 completed candidates
- 53 observed settled contracts
- 49 candidate-bearing settled contracts
- **92.5% raw candidate-bearing contract coverage**
- all candidates: +5c `67.6%`, +10c `54.0%`, +20c `30.7%`
- median peak executable move: `+11.35c`

### First candidate per contract

The first generalized candidate in each candidate-bearing contract was much cleaner than the full candidate pool:

- n = 50
- +5c: `88.0%`
- +10c: `72.0%`
- +20c: `32.0%`
- median peak move: `+16.0c`
- trailing management (arm at +5c, protect on 4c giveback): average realized `+10.86c`, median `+7.25c`, positive-exit rate `84.0%`

This supports treating the first qualified opportunity as a distinct management class and avoiding uncontrolled repeat firing.

## Late-entry finding

V2 candidates first appearing with less than 120 seconds remaining were weak:

- n = 18
- +5c: `22.2%`
- +10c: `22.2%`
- +20c: `16.7%`
- median peak executable move: only `+0.35c`

This is strong evidence for a **>=120 seconds remaining** research guardrail. It is a timing rule, not a price rule.

## Price telemetry finding — NOT an eligibility rule

V2 +10c hit rates by entry-price telemetry:

- <10c: `6.7%`
- 10–20c: `66.7%`
- 20–30c: `61.5%`
- 30–45c: `76.7%`
- 45–60c: `71.9%`
- 60–80c: `77.3%`
- 80c+: `35.3%`

Conclusion: the early log-only impression that one cheap price band was the answer did **not** survive the full tape. Price is context only. The engine must qualify evidence, not price.

## Frozen price-agnostic challenger for untouched forward confirmation

The following challenger is frozen now and must not be retuned using future rows:

1. Use the **first candidate in a contract that satisfies all evidence gates below**.
2. `seconds_left >= 120`.
3. side-aligned `btc30 >= 15` dollars.
4. **No entry-price filter.**
5. Management research policy: arm profit protection after executable gain reaches `+5c`; protect/exit after a `4c` giveback from the running executable peak.
6. One qualified challenger signal per contract for primary scoring; later candidates remain logged for secondary analysis.
7. No automatic orders.

On the V2 development tape this challenger produced:

- n = 49 candidate-bearing contracts
- +10c: `77.6%`
- +20c: `34.7%`
- trailing management average realized: `+10.06c`
- trailing management median realized: `+10.00c`
- positive-exit rate: `83.7%`

These figures are **development evidence only**, not a promotion result.

## Untouched forward-test boundary

All event rows with timestamp **after** `2026-09-14T02:24:03.366238Z` are reserved as new forward confirmation data for this frozen challenger.

Primary next score should not be judged until at least **20 new unique contracts with a frozen-challenger qualified signal** are available. Report, without retuning:

- number of observed contracts
- number of qualified challenger contracts / actionable coverage
- +5c / +10c / +15c / +20c / +30c rates
- average and median peak executable move
- median adverse excursion
- trailing-management average / median realized cents
- trailing-management positive-exit rate
- time to +5c / +10c / +20c
- performance by UP/DOWN and broad market regime

Do not move the threshold or feature gates while those forward contracts accumulate.

## Reversal-risk status

Raw BTC/BRTI reversal flags show some association with later giveback but are not sufficiently discriminative or calibrated to display a trustworthy reversal-risk percentage. Keep the dashboard's numeric reversal-risk output hidden/unvalidated for now.

Mechanical executable giveback management is currently more defensible than claiming a calibrated reversal probability.

## Tooling

`score_scalp_move_management_v3.py` was added to this research branch as a read-only offline scorer. It supports:

- full persistent-tape scoring
- `--v2-only` scoring from the full-time V2 boundary
- arbitrary `--cutoff` scoring for future untouched windows
- price telemetry tables
- time-left analysis
- candidate-order analysis
- trailing-management grid
- first-signal baseline vs frozen price-agnostic challenger
- descriptive chronological slices with an explicit no-promotion warning

No production behavior is changed by this scorecard or scorer.
