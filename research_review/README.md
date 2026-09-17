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

93 regression tests cover snapshot integrity/comparisons (21), longitudinal history (6), extra execution costs (15), the causal-audit harness (12), decision/omission accounting (16), and checkpoint packaging/replay (23). They include mixed refresh snapshots, identity drift, duplicate observations, tampered evidence, altered exit timestamps despite equal counts, false readiness, exact paired arithmetic, missing outcomes, coverage denominators, all controls, rendering, offline replay and non-overwriting archives.

## Single-snapshot checkpoint pack

`nextgen_v2_checkpoint.py` runs one coherent capture through all five review tools and saves a self-contained evidence pack. Only the existing reviewer contacts the live service, using read-only GET requests; every market report then uses the exact same saved bundle. The synthetic mechanism audit remains separate engineering evidence, never additional market observations. This combined command needs the repository's pinned dependencies because it also runs that audit; it never starts a collector loop.

Pass only accepted chronological histories, not a directory glob that could include drafts:

```bash
python research_review/nextgen_v2_checkpoint.py capture \
  --history research_review/captures/accepted_checkpoint/bundle.json \
    research_review/captures/20260916T225513444136Z/bundle.json \
    research_review/captures/20260916T233157908004Z/bundle.json \
    research_review/captures/20260916T234900184881Z/bundle.json \
    research_review/captures/20260916T235948995478Z/bundle.json \
  --output research_review/checkpoints/new_checkpoint
```

Use `--bundle path/to/bundle.json` for an entirely offline build. `verify` is always offline and does not modify the saved pack:

```bash
python research_review/nextgen_v2_checkpoint.py verify research_review/checkpoints/20260917T002405Z
```

Each pack contains current and historical bundles, the experiment manifest, comparison/ledger/cost/history/mechanism JSON and Markdown, and a concise `summary.md`. `pack.json` records each artifact's SHA-256, six report-source hashes, the frozen collector identity and exact Python version. `COMPLETE` seals that receipt and is written last. An incomplete write is retained for diagnosis, not overwritten or treated as complete. A new output directory is required even after a partial failure.

Verification rejects missing/extra files, symlinks, unsafe inventory paths, duplicate JSON keys, non-finite values, changed tool code/runtime, mismatched hashes or safety flags. It then regenerates every report and checks exact bytes, including provenance. Inputs are canonicalized so JSON object ordering cannot change report order after saving. Fixed input/file/pack size bounds apply; the largest aggregate pack is 256 MiB. Verify old packs using their recorded report-code revision and Python runtime if the tooling later changes.

Hashes and replay are reproducibility checks, **not signatures, trustworthy-clock proof, independent live-tape validation or prospective certification**. A consistently fabricated input cannot be ruled out by hashing it. The completion marker certifies only that files were written, never that a trading policy passed. The command creates no schedule or background monitor and never selects a winner.

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

## Synthetic causal and boundary audit

`nextgen_v2_causal_audit.py` first verifies that the local frozen source fingerprint matches the accepted manifest. It then imports the unchanged core functions and runs 6,952 deterministic checks over 40 generated quote paths plus hand-specified boundary cases. The source fingerprint is checked again at completion. Nothing is deployed, no polling loop is started, and no live data is fetched by this command.

```bash
python research_review/nextgen_v2_causal_audit.py \
  --output research_review/causal_audits/reproduced_pinned_run
```

This uses the repository's pinned dependencies, like the regression tests. A new directory is required. `audit.json` records the source fingerprint, seed, group counts, failures, and limitations; `audit.md` is readable. The saved first run is `causal_audits/first_pinned_run/`.

Checks cover strong/weak confirmation; two-event evidence; exact 30-second, 5-second-gap, chase-price and pullback-window boundaries; unknown safety flags; bad clocks and quotes; SCALP-2 membership; prefixes; changed future suffixes; poisoned outcome labels; duplicate events; event-time order; pre-entry peak exclusion; input immutability; and independent +5-cent-arm/4-cent-giveback exit arithmetic. Twelve harness tests demonstrate detection of deliberately injected in-memory look-ahead, changed exits, source drift, and input mutation, and preserve existing audit files.

Passing is **mechanism evidence only**. Synthetic clean event-time prefixes do not validate received-time ordering, provider corrections, candidate-feature construction, serial-opportunity construction, raw live paths, or prospective cutoff eligibility. The audit preserves V1 Watch clock/exec_gain semantics. It is not a market-performance, execution-feasibility or certification pass.

## Per-opportunity decision ledger

`nextgen_v2_decision_ledger.py` is a separate, offline diagnostic built from the existing `/state` and `/audit` bundle. It does not modify or invoke the older V1 coverage-gap ledger, which requires different input features. The V2 ledger matches contract/candidate/opportunity IDs, includes every family-anchor opportunity, and distinguishes both actions, experiment-only actions, control-only actions, and neither. Its 28 comparisons reconcile to the appropriate family denominator; SCALP-2 applies only to opportunity #2.

```bash
python research_review/nextgen_v2_decision_ledger.py \
  research_review/captures/20260916T235948995478Z/bundle.json \
  --output research_review/decision_ledgers/reproduced_checkpoint
```

The new output directory contains complete `ledger.json` evidence plus `ledger.md`, a summary with the first 40 experiment/anchor detail rows in deterministic order. Only Markdown detail is capped; JSON retains all records. It has no network calls, new policy, live alert, order handling or promotion behavior.

Accepted entries retain their exported reasons, prices and delays. Missing entries are explicitly `NO_ENTRY_RECORDED` with `NOT_EXPORTED` reasons; the tool does not invent confirmation failures, timeout causes or price rejection explanations. Missing reasons on existing records are also explicit. Warning presence is tracked separately from entry presence, so a missing warning cannot be mistaken for a skipped trade. Unknown outcomes, missing fee scores, and observed zero net are different states.

Control-only positive/negative fee-net exits are labeled hindsight observations, not missed-win/avoided-loss claims. All values retain the fixed-exit and fixed-fee replay assumptions. Quiet contracts remain in total counts, but their individual IDs cannot be reconstructed from the current audit export. The standalone saved ledger uses the coherent 23:59:48 UTC checkpoint; the newer checkpoint pack has its own ledger on its shared 00:24:35 UTC bundle. This ledger command itself never reads live endpoints.

## Interpretation limits

The overall 100-contract / 100-signal floor permits manual review only; it does not establish lane-specific sample sufficiency. Comparisons show opportunity and distinct-contract counts. They do not claim independent observations, statistical significance, confidence intervals or total portfolio P&L. Repeated entries from one contract must not be interpreted as independent contracts.

A filtered SCALP-2 lane has the same economics as its retained control trades. A positive unconditional average from filtering does not establish a prospective advantage; review the omitted trades and lost coverage. Paired net differences use only both-exit cases and are explicitly conditional.

The live audit does not export full raw quote paths or contract first-observation timestamps. This reviewer can verify the frozen identity and consistency of exported evidence, but cannot independently prove every causal entry or cutoff eligibility from those endpoints. Preserve raw source evidence separately for any later certification audit.

A future certification window needs its own explicit manifest and prospective freeze. No current result can automatically promote a policy.
