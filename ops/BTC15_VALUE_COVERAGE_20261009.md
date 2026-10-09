# Production native value and opportunity publication repair

Scope: the existing MAIN, SCALP and cockpit; signal only, no orders. User explicitly authorizes implementation and production deployment. Base cockpit commit cd46cfa57e7a403bf27bdfe211a687fb29e6a7fe includes all explanation-stability repairs; MAIN base 57f468063f31ec005f413e5032d147603c2e70c8; SCALP base a260810eb5ea76aa204225ac181e163dd4c80392. SCALP's deployed feed diagnostics were preserved from that exact commit.

## Price rules and evidence

- Removed broader EARLY's universal 50-cent veto, fixed 50-cent target, 25–35-cent ideal band and absolute-price “cheap/expensive” classification. No replacement price ceiling.
- Retained `ask_le45` exclusively in the separate historical Tier-1 origin policy, along with its model >=75%, 120–600s and absolute BTC gap >=$25 rules. It no longer determines the broad EARLY dashboard state or limits economic evaluation.
- Both sides are evaluated at every qualified native frame throughout the entire open 15-minute window, including outside historical Tier-1's time window. No future or stale source is treated as executable. Runtime cadence and feed acquisition are unchanged.
- Existing evidence does **not** establish calibrated expanded-price profitability. The source audit `BTC15_PR53_BEHAVIOR_AUDIT_20261003.md` records failed tier expansion, projected crossing, target-hold and pullback/persistence studies; `BTC15_PRODUCT_LOGIC_V2_20261003.md` explicitly lacks support for expanded authoritative EARLY. Those families are not promoted.
- An eligible historical Tier-1 remains QUALIFIED under its implemented rules, not an assertion of a measured 75% win rate. Broader positive model value is WATCH / POTENTIAL with missing reliability evidence stated; negative economics or weak direction is PASS. An ASK of 53 cents is never rejected merely for exceeding 45/50 cents.

## Native economics and publication

`btc15_v2_product/opportunities.py` publishes genuine model probabilities and identities, both same-contract bid/asks, gross model edge, entry-fee scenario, observed spread and an additional-one-spread execution stress scenario, break-even probability, settlement win/loss and reward/risk, time, BTC/BRTI relation to target, recent causal native BTC movement, probability trend, 5m range/volatility fields, FINAL support, observed pullback and model-direction reversal context. Expected profit and guaranteed fills are explicitly absent.

Fees: Kalshi's official July 7, 2026 schedule, read Oct 9 UTC, supplies the general M×0.07×C×P×(1-P) taker formula and zero settlement fee: https://kalshi.com/docs/kalshi-fee-schedule.pdf . The implementation uses an explicitly labeled M=1, one-contract, conservatively cent-rounded scenario. Actual current series multiplier, order size, order-book depth and slippage are not verified. One observed spread is a stress scenario, not an asserted slippage forecast. No future exit fee or fill is assumed. The on-page cost notice discloses these limits.

For a test-only 80% model estimate, 52/53-cent bid/ask: the one-contract fee scenario is 2 cents, all-in cost 55 cents, model-implied net EV 25 cents, spread-stress net EV 24 cents, win profit 45 cents and maximum loss 55 cents. These are conditional arithmetic, **not observed profitability**. Status stays WATCH because expanded qualification evidence is absent.

Native selection prioritizes the existing qualified policy, then observational model value after the spread stress, with lower ASK breaking equal-value ties. It does not compare settlement EV with SCALP horizon returns or claim the most profitable trade. The dashboard shows native SCALP states independently.

## Connected paths

- FINAL: original high-confidence rules, independent publication and explicit EARLY-origin confirmation/protection preserved.
- EARLY: historical origin/latched protection unchanged; price-unbounded native analysis now drives the broader no-position state and explanations.
- Secondary/pullback: causal same-contract ask pullback plus native value context, WATCH only. No extra directional origin is manufactured.
- SCALP: existing generalized BTC30 >=$15, >=120s entry policy in both directions; serial re-entry and REVERSAL_RECROSS; +5-cent arm / 4-cent giveback exit unchanged. Both-side native coverage is now published even while an origin owns the lane.
- Directional reversal: observational model-side change; authoritative reversal remains the independently qualified SCALP serial path.
- Management: only genuine immutable origins activate ladder rows. Directional EARLY EXIT remains unsupported; PROTECT remains manual risk guidance. SCALP executable exit observations remain quote observations, never fills or realized profits.

## Dashboard

The actual cockpit shows independent native EARLY status and reason, a two-side value section, costs/risks, best directional candidate, conditions needing improvement, timing, target/momentum/reversal context, plus independent SCALP diagnostics and existing management. The previous explanation single-writer and same-contract historical retention repair remains intact. Expired action fields and rung authority are revoked immediately; retained analysis is explicitly historical and disappears on rollover. The compatibility decoder accepts the previous schema during ordered rollout.

## Focused checks

- 32 Python regressions: economic boundaries including 53 cents, cheap/weak and expensive/negative examples, full-window scan, both sides, source rejection, original EARLY/FINAL gate equivalence, management, serial SCALP re-entry/reversal/exit.
- Real cockpit renderer checks: all 50 existing protected scenarios, 53-cent native WATCH projection, no invented ladder authority, stable repeated rendering, expiry, rollover, and asynchronous source arrival.
- Original lane freeze and full release hashes verified for both MAIN and SCALP; JavaScript syntax and diff whitespace checked.
- Legacy `test_btc15_read_only_revalidation` has nine pre-existing failures due to obsolete status/lease expectations. The untouched deployed cd46cfa baseline reproduces the same nine failures. This repair does not change revalidation code, source clocks, expiry or model bytes. Local environment also warns about the unchanged model artifact's sklearn version; production dependencies are unchanged.

No shadow service, performance campaign, broad backtest, new paid infrastructure, fill, order, improved coverage rate, improved accuracy or profitability claim. Deployed identities and bounded live observations are recorded separately after Railway SUCCESS and browser verification.

## Production receipt and browser verification

All three existing production services report SUCCESS in Railway:

| Service | Exact deployed commit | Deployment |
| --- | --- | --- |
| MAIN | `36bc1f296df450943201cb7152934d6283df4f6e` | `d15711cd-16da-49e4-9eab-15f099b0e9f1` |
| SCALP | `f9ef31a03662af74b0aa1bb0640f8eb49523fdb8` | `d216ebb3-c9e3-444f-bc1c-b88dff3afd2b` |
| COCKPIT | `36bc1f296df450943201cb7152934d6283df4f6e` | `5dbe4fd3-daeb-4ef3-bc6c-aaad2fbfdaf6` |

Verified the actual production browser at `https://btc15-operator-cockpit-readonly-production.up.railway.app/?mode=live`, including the independent ladders, native value section, source status and retained-analysis behavior. A full-page screenshot was captured at approximately 2026-10-09 00:55 UTC. The browser observed a 72-cent UP WATCH with an 84.6% model estimate, a weak 29-cent DOWN PASS, and subsequently an 87-cent UP PASS with an 86.3% estimate whose costs erased apparent value. These observations establish publication behavior, not calibration, fills or profitability.

SCALP native output and browser showed a genuine REVERSAL_RECROSS origin and existing protection exit lifecycle, and later a DOWN origin with CAUTION. Native receipts are in `ops/evidence/value_coverage_20261009/`. They are bounded observations, not a performance sample.

Source freshness gaps continue. The captured MAIN endpoint receipt is an UNAVAILABLE / SOURCE_EXPIRED observation; subsequent bounded endpoint reads also included BTC_SOURCE_UNAVAILABLE. The browser separately observed current native MAIN values after those gaps. The dashboard revokes current authority and labels retained values historical during expiry. This repair does not widen freshness thresholds or claim continuous feed availability.

The unrelated pre-existing staged Railway patch for service `84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1` was not accepted or modified. No other service was deployed. The documentation-only receipt commit is not a runtime deployment; runtime identities remain those above.
