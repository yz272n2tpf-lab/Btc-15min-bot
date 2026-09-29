# BTC15 unified Round-2 evidence infrastructure — offline candidate

**Decision: C — BLOCKED; EXACT TECHNICAL PREREQUISITE.** No live acquisition, real clock monitor, complete lane event feed, hosted qualification, deployment or prospective start is claimed.

This isolated additive package preserves the frozen native/lifecycle/admission candidates. It is evidence-only and has no producer callback, HTTP client, order facility or automatic lifecycle invocation. Existing files are unchanged. The recorder's `RECORDED_PARTIAL` receipt is not availability, guidance, native admission or qualification.

## Files and exact roles

- `schema.json`: Draft 2020-12 schema, including producer/path bindings and mandatory null/unavailable semantics.
- `producer_map.json` and `.csv`: 363 fields; SHARED 171, EARLY 47, FINAL 47, SCALP 98. Shared primitives occur once in the contract; lanes reference their original IDs.
- `requirements_crosswalk.json` and `.csv`: 362 individual terms from the prior specifications, including explicit missing-producer requirements. Immutable historical origin fields never map to the current FINAL state.
- `contract.py`: deterministic schema and map generator. An existing source path means a parsed field may be observed; it does not prove freshness, completeness or live admission.
- `capture.py`: bounded consumer-only archive of original gzip member bytes and signed envelopes; unchanged frozen member parser/signature validation; exact run/build/offset/sequence checks; transactional immutable records, duplicate/conflict handling and local quota. No producer I/O. `initialize` is explicit and never auto-recreates missing state.
- `clock_receipts.py`: authenticated synthetic certificate receiver over the unchanged interval guard. It is not an offset/drift measurement system; live mode is blocked.
- `chronology.py`: offline audit of explicitly supplied immutable origin/event IDs, owner links, FINAL ready/not-ready distinction, lifecycle transition continuity and exact later BID arithmetic. It never constructs a trade or a future outcome. Its serial checks are completeness checks for recorded policy evidence, not a replacement SCALP policy. Ambiguous/overlapping or incomplete ownership is rejected from this qualified audit; original raw records must remain in the archive as unavailable evidence.
- `protocol.json`: fixed future 21-day development, 14-day validation and 21-day unseen-final blocks, with counts, metrics and completeness gates. Start is null. Capture alone does not discover or authorize a new EARLY candidate.
- `qualification_manifest.json`: pins, hosted requirements, failure matrix and explicit unstarted status.
- `acquisition_and_clocks.md`: exact unresolved prerequisites and verified platform facts/cost limits.
- `test_round2.py`: synthetic schema, identity, replay/gap, byte integrity, storage, abrupt-crash, clock, ownership and chronology controls.
- `run_controls.py`: preserved frozen tests in isolated processes; direct invocation for assertion-only scripts, unittest invocation for unittest modules. No assertions or frozen sources are edited.
- `references/`: earlier EARLY/FINAL/SCALP requirements and historical common-observer source reference. These are requirements/provenance, not new native authority.

## Recovery and reproduction

The outer review archive contains the unchanged base bundle, an incremental candidate bundle/patch, raw test logs, V1/V2 support controls, required SCALP test inputs, and exact original preview Git objects needed by a frozen test. Clone `BTC15_External_Admission_Base.bundle`; fetch `BTC15_Unified_Round2_Increment.bundle` and checkout its candidate branch. Import the content-addressed preview objects using `evidence/import_preview_objects.py` from the clone's root (all three hashes are checked before use). Never replace a frozen fixture by a convenient current file.

Use the runtime pins in `qualification_manifest.json`. Install `jsonschema==4.26.0` and the pinned transitive versions in `test_requirements.txt` into a separate test-only directory/environment; do not alter the native environment. The full frozen model/runtime remains unchanged.

From the cloned repository root:

```sh
python -B -m round2_evidence.contract
python -B -m round2_evidence.requirements_crosswalk
python -B -m unittest round2_evidence.test_round2 -v
python -B round2_evidence/run_controls.py --python /absolute/pinned/python --output /absolute/review/frozen_controls
python -B round2_evidence/run_controls.py --python /absolute/pinned/python --output /absolute/review/v1v2_controls --support /absolute/review/support_v2/offline
node test_btc15_directional_signal_view.js
python -B /absolute/review/scalp_controls/verify.py
```

The information-preview JavaScript control consumes generated JSON via stdin and is executed by the unchanged information ingress Python test; standalone invocation without its fixture is invalid. Initial invocation/fixture failures and their corrected reruns are retained. No failure was suppressed or assertion weakened.

The copy of the SCALP verifier writes its own `results/verification.json`; the original research package was not changed. No historical strategy investigation or optimization was repeated. The preserved verifier was rerun solely as a required chronology/adversarial gate.

## Failure and trust limits

A failing consumer returns UNAVAILABLE and does not advance its cursor or mutate any native/manager origin. Mid-transaction death rolls back; restart resumes the original exact member boundary. Missing state is never silently recreated. Bounded backlog is not silently skipped. Errors/WAIT observations remain archived; missing fields stay null. Real producer disappearance/network loss and hosted storage/CPU isolation still require the blocked hosted exercise. Offline tests prove local fault behavior and absence of a wired feedback interface, not physical platform noninterference.

No live source clocks are fabricated from BRTI age. No `_two_final_*` startup values are substituted for protected FINAL. A projection of a snapshot is not a full exchange quote/event stream. Retirement is not EXIT; shadow protection is not user guidance. No source certificate, fill or completed delivery witness is invented.
