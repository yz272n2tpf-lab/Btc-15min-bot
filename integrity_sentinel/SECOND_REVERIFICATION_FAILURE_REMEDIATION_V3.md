# Sentinel V1 Second Independent Reverification Failure — Remediation V3

Status: MANDATORY BEFORE ANY DEPLOYMENT.

Authorized branch: `integrity-sentinel-recorder-v1` only.
Verified failing head: `81d93ddea66dd08b72260edc90d37df1d87641f0`.
Hardened reconciler base: `850c8d870ee6b639bb51df8603cc35e8149229cc`.
Production main: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.

This document is the remediation authority for the single deployment blocker reproduced by the second independent read-only reverification. It does not authorize deployment, Railway mutation, evidence reset, a certification window, provider polling, strategy changes, orders, or trading.

Permanent rule:

**Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence.**

The Sentinel is a recorder/provenance system and has no authority to certify evidence.

## Blocking finding — Early/Final watchdog unhealthy state is ignored

### Independent reproduction

The second independent read-only reverification reproduced four false-health cases in which a required Early or Final membership source returned an otherwise successful HTTP/JSON response containing an explicit nested watchdog health failure (`watchdog.healthy=false`). Sentinel still returned `/health` 200 and top-level `/state.ok=true`.

This is a deployment blocker because an explicitly dead or stale required source worker can be masked by an otherwise reachable service endpoint.

The durability and redirect remediations passed independent reverification and must not regress.

### Root cause to verify

At failing head `81d93d...`, `_payload_failures()` inspects the root payload plus selected `live`, `health`, and `source_health` objects. It does not inspect the deployed Early/Final `watchdog` health object, so explicit `watchdog.healthy=false` is omitted from `source_failures` and source health may incorrectly remain true.

Do not fix this by special-casing only one synthetic object shape without verifying the actual deployed Early and Final state schema.

### Required behavior

1. Required Early and Final membership sources must fail health whenever their explicit watchdog reports an unhealthy/dead/stale/error state.
2. At minimum, explicit `watchdog.healthy is False` must make the source unhealthy in that cycle.
3. Watchdog state must be checked wherever it is explicitly exposed in the supported deployed state envelope, including the verified Early/Final structure. If the actual supported schema permits watchdog under root or `live`, both must be handled deterministically.
4. Explicit negative watchdog facts must be preserved in the immutable source observation envelope and surfaced in `source_failures`/public source status; they must not be erased by successful HTTP status, valid JSON, membership extraction, or later unrelated healthy fields in the same payload.
5. A required source with an explicit watchdog failure must cause `/health` 503 and top-level `/state.ok=false`.
6. An ordinary later cycle with an explicitly healthy watchdog may restore operational source health only if all other existing health requirements also pass; historical negative evidence remains preserved in the ledger.
7. Missing watchdog must not be invented as healthy. Preserve existing fail-closed rules: if the source contract/schema otherwise lacks required health evidence, do not manufacture PASS.
8. A contradictory watchdog object (for example `healthy=false` together with another nested flag that appears healthy) must fail closed. Explicit negative evidence dominates.
9. Malformed watchdog values (wrong type for `healthy`, invalid nested status/state fields, malformed age fields where supported) must not become healthy by coercion.
10. This remediation must not weaken any existing source failure detection, control attestation, disk/ledger protection, redirect protection, durability markers, contract-agreement gate, membership extraction, Kalshi/Coinbase UNKNOWN behavior, or no-orders/no-certification invariants.

### Mandatory regression tests

Use temporary/synthetic fixtures only and do not contact providers.

For both `early_membership` and `final_membership`, independently test at least:

- root `watchdog: {healthy: false}`;
- supported nested `live.watchdog: {healthy: false}` if present in deployed schema;
- watchdog stale/dead/error status forms actually exposed by the deployed code;
- `watchdog.healthy=true` positive control;
- contradictory watchdog fields with one explicit negative fact;
- malformed `healthy` values such as `0`, `1`, string, null, list, object;
- successful HTTP 200 + valid membership records + unhealthy watchdog;
- healthy HTTP/service wrapper + unhealthy watchdog;
- prior healthy cycle followed by unhealthy watchdog cycle;
- unhealthy cycle followed by later genuinely healthy cycle, confirming health can recover while the prior negative observation remains in the append-only ledger.

Every explicit watchdog-negative case must produce:

- immutable observation retained;
- source status `ok=false`;
- a stable reason in `source_failures` identifying the watchdog failure;
- `/health` 503;
- `/state.ok=false`.

### Deployed-schema verification

Before committing the fix, inspect the source code or preserved payload fixtures for the currently frozen Early and Final scorecard services and document the exact watchdog location and field names used. Do not infer or rename fields that are not present.

### Required regression suite after fix

1. Compile every `.py` under `integrity_sentinel/`.
2. Run every Sentinel unit/regression test.
3. Run all hardened `integrity/` tests.
4. Run `python -m integrity.adversarial_hardening_v1`.
5. Run `python -m integrity_sentinel.adversarial_hardening_v1`.
6. Run `python -m integrity_sentinel.adversarial_remediation_v2`.
7. Add a dedicated V3 watchdog adversarial probe module and execute it independently of unit-test fixtures.
8. Re-run the prior second-reverification false-health matrix, especially required-source outage/staleness, HTTP-200 explicit failure, membership failure, recorder failure, disk/ledger failure, control mismatch, contract disagreement, unresolved durability marker, and Early/Final watchdog failure.
9. Confirm the V2 durability and redirect reproductions still pass unchanged.
10. Confirm all changes remain under `integrity_sentinel/` only.
11. Confirm `integrity/` and production `main` remain unchanged.
12. Confirm no Railway, production, evidence, cutoff, certification-window, provider-polling, strategy, order, or trading action occurred.

## Limitations not resolved by this V3 remediation

These remain explicit and must not be weakened or hidden:

- Kalshi provider-specific freshness: INSUFFICIENT / missing facts UNKNOWN.
- Coinbase provider-specific freshness: INSUFFICIENT / missing facts UNKNOWN.
- Healthy recorder operation requires an independently captured control-plane snapshot matching the frozen manifest.
- Coordinated replacement/rollback of all local provenance still requires an external trusted witness.
- Five-minute offline load tests do not establish long-run capacity; longer separately authorized capacity testing remains required.

Passing V3 remediation means only:

`READY FOR THIRD INDEPENDENT READ-ONLY REVERIFICATION`

It does not authorize deployment or certification.
