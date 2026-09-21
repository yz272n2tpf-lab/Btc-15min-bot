# BTC15 EARLY Coverage Expansion — Tiered Directional Ladder V1

FROZEN BEFORE THIS TOURNAMENT'S OUTCOME SCORING. Offline historical development only.
SIGNAL ONLY / NO ORDERS. No deployment, promotion, running-service access or changes.

## Scope and source lock

Base: `13c8988fed8c97479203910f5620df64826246f3`.
Only files at this commit, plus previously saved historical official market responses
at `b2ebd0faa498ea349570b9d0c119594e5c19d4a2`, may supply observations.
Official settlement GETs may fill missing labels for an explicit historical ticker allowlist.
No current-market listing, production dashboard, collector, or clean-forward endpoint access.
All feature contracts must close before 2026-09-07T00:00:00Z, a stricter cutoff than
both the SCALP clean boundary (2026-09-20T19:05:17.147189Z) and the EARLY clean
boundary (contracts starting 2026-09-21T03:00:00Z). Fail on newer contracts.

Sources:
- `union_optimizer_processed_snapshot_cache.csv`: 199 August development contracts.
- `brti_calibration_results.csv`: archived official market.result and target for August.
- `kalshi_scalp_shadow_snapshots_v1.csv`: preserved September 3–5 raw snapshots.
- `kalshi_early_conf_shadow_v1.csv`, `_v1_1.csv`, `_v1_2.csv`: backward-only confidence enrichment.
- `kalshi_direct_brti_parity_v1.csv`: backward-only BRTI enrichment.
- `kalshi_subminute_unified_v1_1.csv`: preserved September 6 observations.
- `subminute_official_truth_cache.csv` and `kalshi_official_settlement_check.csv`: archived labels.
- `subminute_early_dataset_v1.csv`: inventory/provenance only, excluded from scoring
  because its feature builder permits nearest/future joins and its population is price-filtered.

Do not pool August reconstructed candle quotes with September observed snapshots
to claim executable coverage. Report each cohort separately; overlapping contracts
within the September sources count once. No interpolation or synthetic ASK prices.
Archived ASK does not prove a later manual fill, depth, fees, or latency.
August BTC candle timestamps have unresolved close-versus-open semantics; retain
the benchmark as archived development replay, not certified causal live evidence.

## Protected Tier 1 — exact, no retuning

Preferred ASK <=0.45, preferred fair >=0.75, edge >=0.08,
2 <= minutes remaining <=10, absolute exact-target gap >=25.
First qualifying row per contract. Do not add directional-gap, spread, or persistence
requirements to Tier 1. In raw data, use the logged preferred side and its ASK/fair/edge;
missing required fields fail closed. Lower tiers never rewrite its standalone call.

## Three fixed candidate families; no grids or learned models

Common lower-tier rules: 4–10 minutes remaining inclusive, 0<actual side ASK<=0.50,
0<=BID<=ASK<=1, spread<=0.05. Evaluate both sides, missing fields fail closed.
One earliest call per family per contract. Simultaneous opposite-side ambiguity => PASS.

**A — Volatility-scaled settlement cushion.** Side is currently ahead of the fixed
target. z = signed target gap / (sigma_per_sqrt_minute * sqrt(minutes_remaining)) >=1.50.
No momentum projection, fair-model threshold, or persistence confirmation.
For August, sigma=max(10 dollars, current BTC price*vol5, range5/sqrt(5)); current
price is derived from the cached exact gap and target percentage.
For raw data, use only trailing 120 seconds of same-contract prices: >=10 prices,
observed span>=90 seconds, no adjacent gap>15 seconds. sigma=max(10 dollars,
sqrt(sum(adjacent_price_change^2)/span_minutes), observed_price_range/sqrt(span_minutes)).
This tests a time-scaled diffusion cushion, not the rejected fixed ratio+momentum runway rule.
z is a structural statistic, NOT a calibrated probability.

**B — Fresh dual-feed agreement.** Side-aligned BRTI gap>=25 dollars AND BTC
gap>=25 dollars, absolute BRTI-minus-BTC<=15 dollars, BRTI ready, effective
BRTI age in [0,2] seconds. Both gaps refer to the same fixed target. No momentum,
target-hold duration, classifier, or threshold relaxation. This tests contemporaneous
independent-feed agreement; unavailable on the August cache => no calls there.

**C — Fair-value strengthening before ASK repricing.** Preferred side only;
fair>=0.75; side fair increased >=0.10 over the preceding 30 seconds and did not
decrease over the preceding 15 seconds; side ASK change over 30 seconds<=0;
signed BTC target gap>0. Recompute same-side changes causally, using only
observations at/before t-15 or t-30, tolerance 5 seconds; never compare preferred
probabilities across a side flip. No generic persistence meta-model or prewatch
loosening. This is unvalidated WATCH unless advancement gates pass.
Unavailable at minute resolution => no August calls.

Raw alignment: backward only, same contract and target (<=0.01 dollar discrepancy),
maximum enrichment lag 5 seconds. Add enrichment lag to logged BRTI age.
Existing logged fair is an input, not newly fitted. Validate numeric ranges and
time-left versus ticker close to within 2 seconds for raw snapshots.

## Fixed ladder tournament and honest time order

L1: Tier1, then A as candidate Tier2, then B as candidate Tier3.
L2: Tier1, then B as candidate Tier2, then C as candidate Tier3.
L3: Tier1, then A as candidate Tier2, then C as candidate Tier3.

For requested incremental accounting, first report disjoint membership attribution:
Tier1 gets its contracts, Tier2 gets contracts outside Tier1, Tier3 gets contracts
outside both. This is retrospective overlap accounting, NOT an executable policy:
it cannot know that a later Tier1 call will occur.
Also score the operationally meaningful causal union: earliest qualifying entry
across enabled tiers, Tier1>A>B>C only for equal-time ties. One entry per contract;
no hindsight replacement by a later Tier1 call. Report preempted Tier1 counts and
side disagreements. Advancement depends on this causal result.
All-family union is a fixed diagnostic envelope, not a fourth optimized strategy.
WATCH and PASS never increase actionable coverage.

## Chronology, outcomes and reporting

Split each cohort's unique observed contracts by close time: first floor(N/2)
development half, remaining report-only half. Freeze all rules before either half
is scored. No selection or threshold change after report-only results. These are
reused historical development samples, not independent holdouts.
Denominator: all unique contracts with a valid observation in 2–10 minutes,
irrespective of price, feature availability, or outcome. Also report total observed
contracts and missing-window exclusions. Retain unresolved calls; never count them
as wins or silently remove them from coverage. Official result yes=UP, no=DOWN;
no final-price proxies. Check archived label conflicts, retain raw evidence where available.

Per family/tier, incremental subset, ladder prefix, half, and source report:
unique calls, correct/settled, unresolved, accuracy, Wilson 95% interval, coverage,
ASK mean/median, 25–35c count/share, <=40c count/share, <=50c share,
minutes mean/median, UP/DOWN counts and accuracy. Report chronological-half counts
and accuracy, not row-level accuracy. Fees/depth/latency unmeasured.

Prespecified impossibility diagnostic: count contracts whose eventual winner had
ANY recorded ASK<=50c in (a) 2–10m and (b) 4–10m. This is an oracle, not a tradable
rule. At required accuracy p=.93, maximum covered calls cannot exceed floor(W/p),
capped by contracts with any affordable side, where W is winner-affordable count.
Report full-observed-tape ceiling and conservative missing-label bounds; do not
generalize sparse observation ceilings to unseen seconds or other market regimes.

## Advancement gates (research eligibility only)

Each new actionable tier must add >=30 unique incremental contracts, >=10 in each
chronological half, >=93% settlement accuracy overall, >=90% in each half, and
Wilson lower 95% bound>=85%. Both sides represented. No unresolved calls.
All entries<=50c; mean ASK<=40c; mean time remaining>=6m.
Combined causal ladder must have >=100 calls, >=40 per half, >=70% coverage,
>=93% overall accuracy, >=90% each half, both sides >=10 calls, no unresolved,
mean ASK<=40c, mean time>=6m, and all lower tiers pass incremental gates.
Target 80% is reported separately; >80% is not penalized if all quality gates hold.
If no ladder meets these criteria, return NO STABLE HIGH-COVERAGE EARLY LADDER.
Passing historical gates merely identifies a freeze for later independent validation.
Do not start or alter validation. Never deploy or promote automatically.

No new families, thresholds, exclusions chosen for performance, or optimizations
after outcomes are scored. Implementation defects may be fixed transparently with
a changelog and the same preregistered rules rerun.
