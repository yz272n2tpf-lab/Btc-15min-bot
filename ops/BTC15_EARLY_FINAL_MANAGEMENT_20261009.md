# Live EARLY + FINAL management repair

This release supersedes the `EARLY_SUPPORTED_VALUE_V1` entry route deployed in MAIN/cockpit `f2f5045b740fd5bbbb14b48be50d0d92abecfa1e`. Verified predecessor deployments: MAIN `29d99668-bdcb-47bc-85c7-bb470eb68ea8`, cockpit `6c16078b-c36a-4c41-be16-c27295ebc5aa`, both SUCCESS and rollback-capable. SCALP remains `f9ef31a03662af74b0aa1bb0640f8eb49523fdb8`, deployment `d216ebb3-c9e3-444f-bc1c-b88dff3afd2b`.

## Exact entry policy

`EARLY_CAUSAL_VALUE_V2` replaces the superseded route's 90% probability, 120–480-second window, two advancing observations, $75/$50 BTC gap, $11 BRTI gap, distance/range >=1 and eight-point cost-adjusted edge reserve. There is no replacement ASK ceiling, universal confidence threshold, fixed entry window or confirmation count. The first fully supported native frame can create the actual BUY/origin.

Required conditions:

- Unchanged official contract identity/window, exact executable same-contract quotes, genuine BTC/BRTI source freshness and causal timestamps.
- Exact existing RF+sigmoid artifact and weights; the exact causal feature snapshot used by that model decision, bound to cutoff, target, official open and BTC price. Existing one-minute and five-minute BTC movement, range and volatility are copied from the original function; no new inference, model fitting, candles or fabricated history.
- BTC and BRTI both on the preferred model side of the exact target. Existing one-minute momentum and five-minute trend must both point in that direction. This is cross-horizon market corroboration, not a count of advancing decision observations. Continuously available FINAL model direction must not oppose the entry; no FINAL lock required.
- Valid positive same-side BID and ASK. Time remaining must exceed the already observed maximum source/delivery age; this is measured execution feasibility, not an entry window. Actual manual latency and executable size remain unverified.
- Current supported published Kalshi series fee schedule. Positive remaining settlement upside after entry fee. Model fair must exceed ASK + one observed spread of entry stress + conservative one-contract entry fee + sale-fee scenario at model fair. The latter is a cost/value comparison, not a prediction that a future BID will reach fair. Positive model EV alone cannot qualify.

The model already uses volatility, target distance, momentum and remaining time. The native assessment also exposes range, volatility, target/range position, model flip probability and remaining time. No new arbitrary volatility or flip-probability cutoff is introduced. Historical calibration fit is genuine; current conditional accuracy and price-movement profitability are not established. Existing evidence references remain `completion_audit/MAIN_INTEGRITY_RELEASE_20260923.md`, `completion_audit/model_artifact/manifest.json`, `BTC15_PRODUCT_LOGIC_V2_20261003.md` and `BTC15_PR53_BEHAVIOR_AUDIT_20261003.md`. Rejected research rules are not promoted.

Historical Tier-1 remains a separately labeled unchanged origin route (ASK <=45 cents, model >=75%, 120–600 seconds, absolute target gap >=$25). Those historical predicates and FINAL's predicates remain byte/AST equivalent; they do not veto the independent new route. The earlier universal 50-cent opportunity cap stays removed. The broader WATCH analysis no longer imposes the historical 75% probability or 2–10-minute window.

A 53-cent/83% setup qualifies only with all new-route evidence above. Lower prices improve the actual cost comparison; equal-value ranking prefers lower ASK. Cheap unsupported setups remain observational or PASS, not new-policy CALLs.

## Native management

The genuine immutable origin retains side, original signal ASK, acceptance time, source timestamps, official target/window, complete entry provenance and policy. No manual fill or realized profit is inferred. The existing source-qualified reducer owns the origin; the native management function supplies the real guidance. FINAL's model direction and held-side probability are used every valid frame, below its 90% lock.

- ENTRY: native origin accepted.
- HOLD: direction/target/market support continues without the weakening conditions below.
- WATCH: weaker held-side probability, opposition, target conflict, adverse recent/longer trend, observed BID giveback, or missing causal momentum without stronger protection/exit evidence.
- PROTECT: existing qualified-FINAL opposition/loss-of-established-lock protection remains latched. Continuous sub-lock protection also applies when weakening/opposition is corroborated by BTC/BRTI target conflict or adverse momentum plus observed BID giveback; or positive estimated liquidation value coincides with adverse momentum and weakening/giveback. No fixed-cent target or stop is introduced.
- EXIT: a genuine origin plus a strictly later accepted positive same-side BID and either (a) model direction now opposes the origin, BTC and BRTI are both across the exact target against it, and existing one-minute momentum is adverse; or (b) BID minus current sale-fee estimate reaches/exceeds held-side model fair while held-side probability weakens and one-minute momentum is adverse. Neither condition requires a FINAL lock. Route (a) can reduce loss or protect gain; route (b) is a model-value risk decision, not empirical proof of optimal timing.

EXIT records immutable recommendation time, accepted quote provenance, trigger BID, reason, economics and origin binding. It remains terminal through recovery/restart; no repeated event or origin/price rewrite. Subsequent current BID is distinct from the original trigger BID. Closure stays unconfirmed. Signal ASK-to-BID movement and entry/exit fee scenarios are explicitly hypothetical; realized profit and manual fill remain null.

Clock advance, source loss, missing causal momentum, repeated/pre-entry quotes or zero BID cannot manufacture EXIT. Missing fees disable the net-sale-value exit route; structural-thesis risk guidance reports unknown costs honestly. Existing position protection is not removed on recovery. One existing origin owns the contract; no new directional re-entry strategy is invented. SCALP's independent continuation/re-entry/reversal and protection paths are unchanged.

Restart-safe native checkpoints now include the exit terminal. At this deployment, a bounded read-only transfer imports a still-open origin from the verified predecessor journal into the new deployment's journal, preserving entry and protection state. No old market publication or freshness lease is copied. The predecessor journal and historical records remain untouched. Subsequent releases must identify their actual predecessor when deploying; platform rollback references above remain available.

## Live dashboard

The actual cockpit validates native origin/helper/terminal binding and maps ENTRY → HOLD → WATCH → PROTECT → EXIT. JavaScript creates no strategy decisions. It displays original ASK, current BID, immutable EXIT trigger BID, entry/current model estimates, cost/value and reward/risk scenarios, gross movement, estimated entry/exit fees, hypothetical net liquidation, remaining time, FINAL relation, momentum and source freshness. No origin means no assumed position. Management says “If manually entered”; closure is unconfirmed.

Both-side native analysis remains independent of FINAL qualification, with QUALIFIED/WATCH/PASS, exact failing safeguards and needed improvements. Historical-only explanations remain stable when source authority expires; action/rung authority is removed promptly. The read-only presentation revalidator cannot reproduce the exact native momentum snapshot, so it reports that limitation rather than claiming to revalidate entry/exit. It never changes or renews native authority.

## Narrow verification and limits

43 focused Python checks pass: first-frame 53-cent/83% UP/DOWN origins; no fixed price/probability/window/count gate; positive EV insufficient without corroboration; all five management states below FINAL lock; profitable-scenario and loss-reduction EXIT; source/repeated-quote/missing-feature/zero-BID rejection; immutable terminal/journal restart/rollover; origin transfer; unchanged historical Tier-1/FINAL predicates and SCALP serial paths. Actual renderer checks pass 50 existing scenarios plus native 53-cent WATCH and native CALL through all five rungs, invalid-terminal rejection, expiry, rollover, repeated stable explanations and asynchronous source display. Release/frozen-byte verification is mandatory. These are correctness checks, not a shadow campaign or performance study.

Expanded-entry reliability, current calibration, achieved win rate, coverage improvement and exit-strategy net profitability are not established. Depth, actual fills, manual execution latency, size, event/account fee overrides and slippage remain limitations. No automatic orders, paid infrastructure, new services or model refitting.

Production commit/deployment receipts and direct live observations are recorded after deployment; no qualifying signal will be fabricated for demonstration.

## Completed production deployment and observation

MAIN and cockpit are deployed at **`7a0b661291743222c1f6ac30df8b42e274fd6c73`**. MAIN deployment **`83dc7169-2807-46a2-b011-e189e4cde60f`** and cockpit deployment **`b7fea289-e95c-4c04-b4a7-fb23ea1cfdd8`** both reached SUCCESS and are rollback-capable. The prior deployments remain rollback-capable. MAIN's `/data` volume and historical journals are retained. SCALP is still **`f9ef31a03662af74b0aa1bb0640f8eb49523fdb8`**, SUCCESS; it was not redeployed. No staged shadow changes were accepted. Release manifest SHA-256: `f763ec3aaf32ad8123e942ef809e0ba7ca164cd85c72bd0d79b57461067fc2ca`.

Direct production `/ladders` returned the new build and `EARLY_CAUSAL_VALUE_V2`, with verified-model, causal-feature, current-fee and execution checks passing. Journal sequence 23 reported queue 0 and drops 0. The actual browser on `https://btc15-operator-cockpit-readonly-production.up.railway.app/?mode=live` displayed those native conditions and economics for official contract `KXBTC15M-26OCT082200-00`, target $81,919.72. At 01:51:02 UTC, DOWN model 66.6% / ASK 63 cents remained WATCH: recent momentum and five-minute trend conflicted, and round-trip stress value margin was -1.37 cents. Subsequent actual observations showed PASS where costs removed value, and WATCH where BTC/BRTI target support was missing. FINAL remained independently PASS; SCALP retained its genuine 41-cent UP origin and WATCH management. Source and expiry labels stayed truthful.

The production handoff log verified the predecessor checkpoint identity and reported no still-open EARLY origin to import. The active-origin transfer path was covered by the focused checkpoint check. No new live EARLY CALL or EXIT was observed during this brief deployment verification; authentic 53-cent/83% origins and both EXIT routes were verified through the real native processor in focused correctness checks, not fabricated on the production feed. Live accuracy, expanded coverage and profitability remain unmeasured.

Control-plane receipts and the exact observed native response are committed under `ops/evidence/early_final_management_20261009/`. The actual dashboard screenshot is `btc15-live-management-overview-20261009.jpg`. This receipt update is documentation/evidence only; deployed services remain pinned to the production commit above.
