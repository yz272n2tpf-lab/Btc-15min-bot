# Integrity hardening verification

Branch: `evidence-integrity-reconciler-v1`

Starting commit: `4f02bdf9ffeae5c7db91b5ad6b3be79baebc9f2a`

Main comparison commit: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`

Authority: `integrity/VERIFICATION_FAILURE_REMEDIATION_V1.md` (unchanged).

## Verification results

- All **14 Python files** under `integrity/` compiled with `py_compile`,
  `doraise=True`: 14 passed, 0 failed.
- Complete unittest discovery: **62 tests passed**, 0 failures, 0 errors,
  0 skipped. Includes the original 34 tests and 28 new regression tests.
- AST comparison against the starting commit confirmed all 34 original test
  methods and assertions are unchanged. Only the reconciler's clean fixture was
  extended with the newly mandatory per-feed coverage facts.
- The full operational/evidence PASS/FAIL/UNKNOWN truth table passed all nine
  combinations. Existing PARTIAL classification tests also remain passing.
- Independent adversarial runner: **7 of 7 finding groups passed**. It imports
  no unittest fixtures and exercises the actual CLIs in subprocesses.
- The same runner was executed against the exact starting commit in an isolated
  temporary copy: all seven original exploits reproduced. Both versions passed
  the clean positive control, preventing an always-reject result from counting
  as successful hardening.
- `git diff --check` passed. All branch differences from main, and every new or
  modified worktree path, were restricted to `integrity/`.

| Finding | Adversarial result |
| --- | --- |
| 1. Source overwrite | PASS: 10 CLI overlap cases rejected before output creation; source bytes unchanged. Regression tests additionally cover all six bundle filenames against logs, manifests and policies, aliases, symlinks, hard links, existing outputs and exclusive creation. |
| 2. Invalid numbers | PASS: 40 direct/aggregate NaN, positive infinity, negative infinity and negative measurement cases blocked. Regression tests also exercise parsed logs, invalid policy limits, booleans and malformed values. |
| 3. Feed coverage | PASS: one sample among 169 path observations fails separately for Kalshi, BRTI and Coinbase. Required coverage includes count, start, end and feed-specific gap. |
| 4. Parity masking | PASS: explicit false plus a zero counter aggregates to one failure and INVALID_FOR_CERT. |
| 5. Counter reset | PASS: timestamp-ordered 1000 -> 1 -> 1840 produces reset metadata, no normal delta and INVALID_FOR_CERT. |
| 6. Feed trouble | PASS: parsed BRTI unclean, direct-BRTI unready and Coinbase timeout evidence each survive normalization and aggregation and produce INVALID_FOR_CERT. |
| 7. Rollover lag | PASS: recorded exact-ticker and combined lags of 35.7 seconds remain 35.7 despite a 1-second inferred lag and produce INVALID_FOR_CERT. |

## Safety review

Reviewed all integrity modules and changed code, plus an AST import scan of the
seven non-test modules. No network client, network mutation, order placement,
production mutation or automatic promotion was introduced. Local subprocess
calls exist only in the synthetic adversarial runner and invoke the two local
integrity CLIs without a shell. Source reads remain read-only; derived writes
are preflighted and use exclusive creation. Tests use synthetic temporary files.

No Railway operation, production operation, service/configuration change,
deployment, evidence reset or modification of real source evidence was performed.

Certification remains strictly:

**Operational Health PASS + Evidence Integrity PASS + CLEAN classification.**

This is development-branch hardening. It does not certify any real contract,
historical evidence, strategy, ladder or V2 experiment. Independent read-only
reverification is the next gate.

## Reproduction

From the repository root:

```sh
python -c 'from pathlib import Path; import py_compile; files=sorted(Path("integrity").rglob("*.py")); [py_compile.compile(str(p), doraise=True) for p in files]; print(len(files), "compiled")'
python -m unittest discover -s integrity -p 'test_*.py' -v
python -m integrity.adversarial_hardening_v1
git diff --check
git diff --name-only 8b7f8b48694364cb8c47456d0ab491b102aa42c0 HEAD
```

## Paths changed by this hardening

- `integrity/EVIDENCE_INTEGRITY_RECONCILER_V1_SPEC.md`
- `integrity/HARDENING_VERIFICATION_V1.md`
- `integrity/adversarial_hardening_v1.py`
- `integrity/evidence_bundle_builder_v1.py`
- `integrity/evidence_integrity_adapter_v1.py`
- `integrity/evidence_integrity_reconciler_v1.py`
- `integrity/measurement_validation_v1.py`
- `integrity/railway_evidence_log_adapter_v1.py`
- `integrity/safe_outputs_v1.py`
- `integrity/test_evidence_integrity_reconciler_v1.py`
- `integrity/test_integrity_hardening_v1.py`
