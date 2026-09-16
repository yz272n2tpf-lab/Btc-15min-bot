# Frozen V2 review tools

A read-only, undeployed reviewer for the running combined BTC15 shadow experiment. No new Railway service or slot. No collector imports in the review executable. No orders, production writes, ranking, promotion, or automatic policy selection.

The source/deployment remains frozen on `scalp-nextgen-shadow-v2` at `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`. This work belongs on `scalp-nextgen-v2-review-tools`; do not deploy this branch or merge it into a frozen collector. `nextgen_v2_manifest.json` pins the accepted version, code fingerprint, window, cutoff and lane names. It does not silently follow a new deployment.

## What it builds

- A coherent archive of `/state` and `/audit`: reads state, audit, then state again; retries the entire capture if source/window identities changed. Three attempts maximum.
- Independent checks for code/window/cutoff identity, safety flags, source freshness, JSON digests, all 24 policy lanes, duplicate IDs, serial opportunity anchors, summary/audit counts and economics, sample-floor readiness, and exact Watch exit time/gain/economics parity.
- Twenty-eight matched comparisons: 3 SCALP-2 filters against their control; Dynamic Verify against all 5 V1 delay policies; 2 selective pullbacks against 7 V1 entry policies; and 2 Watch experiments against 3 V1 warning thresholds.
- Coverage and selection accounting: actual unique contracts versus the full quiet-inclusive denominator, signal retention, added/lost contracts, unmatched entries, omitted control outcomes, unresolved exits, and distinct contract counts in paired economics.
- Separate Watch lead-time changes, materially earlier/later pairs, exits without warnings, unresolved warnings, and new-high recovery proxies. No-warning-exit is not automatically labeled a false alarm.
- Timestamped JSON evidence and a readable Markdown report. Existing capture directories are never overwritten. Invalid snapshots produce no performance comparisons.

## Run

The reviewer uses Python's standard library. From the repository root:

```bash
python research_review/nextgen_v2_review.py
```

It performs GET requests only and writes a new directory under `research_review/captures/`. Each directory contains `bundle.json`, `review.json`, and `review.md`. Preserve the bundle when saving a milestone. No credentials are required for these read-only summary endpoints.

To reproduce the checked-in checkpoint without any network call:

```bash
python research_review/nextgen_v2_review.py --bundle research_review/captures/accepted_checkpoint/bundle.json --output research_review/captures/reproduced_checkpoint
```

That output directory must not already exist. Historical replays assess freshness at capture time; they do not claim that an old snapshot is current.

Tests use the repository's existing pinned requirements to generate realistic fixtures through the unchanged frozen scorer:

```bash
python -m unittest discover -s research_review -p 'test_*.py'
```

42 tests cover snapshot integrity/comparisons (21), longitudinal history (6), and extra execution costs (15). They include mixed refresh snapshots, identity drift, duplicate observations, tampered evidence, altered exit timestamps despite equal counts, false readiness, exact paired arithmetic, missing outcomes, coverage denominators, all controls, rendering, offline replay and non-overwriting archives.

## Longitudinal scorecard

The collector snapshots are cumulative. `nextgen_v2_longitudinal.py` therefore validates a chronological sequence and never adds checkpoint totals together. It rejects window/code drift, decreasing totals, missing historical opportunities, changed historical records, duplicate capture times, or invalid component bundles. The latest accepted snapshot supplies current totals and all 28 current comparisons.

Pass explicit, chronological archives so drafts are never included accidentally:

```bash
python research_review/nextgen_v2_longitudinal.py \
  research_review/captures/accepted_checkpoint/bundle.json \
  research_review/captures/20260916T225513444136Z/bundle.json \
  --output research_review/scorecards/reproduced_first_contract
```

The output directory must be new. It writes `scorecard.json` and `scorecard.md`; it makes no network calls and cannot change a collector.

## Extra execution-cost sensitivity

`nextgen_v2_execution_costs.py` is offline arithmetic on validated audit records, not a fill simulator or new strategy. It reports all 24 lanes and 28 control comparisons under the unchanged 1-lot and 10-lot taker/taker fee model, subtracting a fixed extra 0, 1, 2, or 5 cents **per side**. Thus the extra round-trip costs are 0, 2, 4, or 10 cents per contract. Fees are already in the baseline net, are not subtracted twice, and are not repriced for hypothetical fills.

```bash
python research_review/nextgen_v2_execution_costs.py \
  research_review/captures/20260916T233157908004Z/bundle.json \
  --output research_review/execution_costs/reproduced_checkpoint
```

The directory must be new. `stress.json` includes both lot scenarios, paired conditional deltas, exit counts, distinct contracts, positive/zero/negative scored exits, unmatched entries, coverage, and mean break-even extra-cost buffers. `stress.md` shows the one-lot table. Missing exits and missing fee scores stay separate; no outcome is imputed as zero. No lane totals are added together.

Equal costs on both sides of a paired comparison cancel in its delta. Watch warnings still share their frozen exits, so this tool does not award any economic benefit for earlier warnings. Costs do not model manual delay, liquidity, changing spreads, execution feasibility, repriced fees, or path-dependent exits. The grid is descriptive, not a tuned threshold or promotion gate. These small conditional samples do not establish comparative superiority.

## Interpretation limits

The overall 100-contract / 100-signal floor permits manual review only; it does not establish lane-specific sample sufficiency. Comparisons show opportunity and distinct-contract counts. They do not claim independent observations, statistical significance, confidence intervals or total portfolio P&L. Repeated entries from one contract must not be interpreted as independent contracts.

A filtered SCALP-2 lane has the same economics as its retained control trades. A positive unconditional average from filtering does not establish a prospective advantage; review the omitted trades and lost coverage. Paired net differences use only both-exit cases and are explicitly conditional.

The live audit does not export full raw quote paths or contract first-observation timestamps. This reviewer can verify the frozen identity and consistency of exported evidence, but cannot independently prove every causal entry or cutoff eligibility from those endpoints. Preserve raw source evidence separately for any later certification audit.

A future certification window needs its own explicit manifest and prospective freeze. No current result can automatically promote a policy.
