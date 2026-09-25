# Integrated completion — Gate 1 BLOCKED before runtime implementation

Parent qualified contract: `9b5b02744d8e31307516efb5a33c5190d8c74e90`,
tree `446b1daa9893332397ff2142fe78cd9d555e13c4`. SIGNAL ONLY / NO ORDERS.

## One blocker

The qualified V2 contract still conflates the frozen PR36 strategy identity with
the deployed producer runtime identity. Its context has a closed field set and
requires `runtime_commit == 3e552065e34a0a402bc3ca4598b57dff1f1c6e77`.
Its normalized common validation also pins the native runtime to that commit.
There is no supported separate capture-build/strategy identity binding.

The preserved capture scope requires native/source-owner hooks and a new,
explicitly identified PR36-derived instrumentation release. It expressly forbids
mislabeling that new deployed commit as PR36. The integrated mission also requires
the qualified V2 adapter/replay to remain unchanged at Gate 3. These requirements
cannot all be met by the current closed V2 contract.

This is a gap in the previously prepared V2 contract, **not a newly discovered
strategy defect**, an authentication issue or a need for ladder tuning. The V2
report already noted the need for separate instrumentation build qualification;
that remaining prerequisite has not been implemented. A changed build cannot be
made compatible by relabeling its identity, ignoring unknown metadata, adding an
unvalidated sidecar label, or weakening the runtime check. Leaving a PR36 strategy
file byte-identical does not make a new instrumented deployment the PR36 commit.

## Focused proof

The new `test_capture_release_identity_gate.py` uses only synthetic January 2020
fixtures and the unchanged V2 adapter. No live source/outcome is selected.

| Truthful attempted representation | Actual rejection |
|---|---|
| Non-PR36 producer build in context `runtime_commit` | `PR36_CONTEXT_REQUIRED` |
| Distinct `strategy_commit=PR36` plus actual runtime, or `capture_build_commit` alongside the PR36 baseline | `SCHEMA_FIELDS` |
| Rewrite only normalized native runtime identity | `NORMALIZED_EVIDENCE_MISMATCH` |

The known local V2 checkpoint SHA is used only as a concrete non-PR36 identity
in the counterexample. It is **not** claimed to be a runtime capture release or
a deployment. The new tests pass by demonstrating correct current rejection;
they do not qualify a workaround. Existing 40 tests/code remain unchanged.

## Mission disposition

- Gate 1: BLOCKED at producer-identity representation preflight. No runtime capture
  patch, bounded writer, or enabled/disabled full-native equivalence is claimed.
- Gate 2: NOT RUN; no deployment/restart/configuration mutation.
- First authentic lifecycle: NOT RUN; no fabricated origin/linkage.
- Continuous ladder scoring: NOT RUNNING (new requested connected run not started).
- Two-clock live acceptance: NOT RUN. Gate 1's explicit stop condition applies;
  previous cost/live prerequisites are not re-investigated or bypassed.
- Continuous through-Wednesday test: NOT RUNNING. Existing collectors were neither
  stopped nor reconfigured; no claim is made that they now provide the requested
  connected lifecycle/scoring completeness.

Production/rollback identity remains PR36
`3e552065e34a0a402bc3ca4598b57dff1f1c6e77`. Two-clock candidate remains
`06261dbfbe6d8336a6886a4f2b349f33b06b6202`, unmodified and undeployed by this task.
No Railway operation, authentication troubleshooting, model/threshold/feature
change, scoring, tuning, order, merge or production branch update occurred.
Live production health/rollback deployment availability were not re-probed: no
production mutation reached a gate requiring that read.

## Exact correction required before resumption

Authorize a narrowly versioned producer-identity contract extension that preserves
historical V1/V2, records **both** the frozen strategy baseline and actual deployed
capture-build identity, and requires an explicit qualified build manifest proving
that build's capture-only/native-equivalence status. No arbitrary build whitelist
or caller-supplied baseline label is sufficient. Requalify that extension, then
resume passive capture preparation and the existing deployment gates. This changes
the mission's current unchanged-V2 requirement; it must not be silently done here.

## Preservation

This local checkpoint adds only the focused counterexample tests and this report
plus machine-readable disposition. The recovery package retains the qualified V2
checkpoint, all local ladder history, immutable V1 sources, full focused tests and
exact resume instructions. Authenticated GitHub publication is confined to a new
audit branch containing the recovery ZIP/manifest and failure report; the ZIP's Git
bundle preserves exact local commits. A connector-created archive commit has its
own identity and must not be described as the exact original local source commit.
