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

21 tests cover mixed refresh snapshots, identity drift, duplicate observations, tampered evidence, altered exit timestamps despite equal counts, false readiness, exact paired arithmetic, missing outcomes, coverage denominators, all controls, rendering, offline replay and non-overwriting archives.

## Interpretation limits

The overall 100-contract / 100-signal floor permits manual review only; it does not establish lane-specific sample sufficiency. Comparisons show opportunity and distinct-contract counts. They do not claim independent observations, statistical significance, confidence intervals or total portfolio P&L. Repeated entries from one contract must not be interpreted as independent contracts.

A filtered SCALP-2 lane has the same economics as its retained control trades. A positive unconditional average from filtering does not establish a prospective advantage; review the omitted trades and lost coverage. Paired net differences use only both-exit cases and are explicitly conditional.

The live audit does not export full raw quote paths or contract first-observation timestamps. This reviewer can verify the frozen identity and consistency of exported evidence, but cannot independently prove every causal entry or cutoff eligibility from those endpoints. Preserve raw source evidence separately for any later certification audit.

A future certification window needs its own explicit manifest and prospective freeze. No current result can automatically promote a policy.
