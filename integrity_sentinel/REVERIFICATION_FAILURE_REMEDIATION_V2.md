# Sentinel V1 Independent Reverification Failure Remediation V2

Status: MANDATORY BEFORE ANY DEPLOYMENT.

Branch authority: `integrity-sentinel-recorder-v1` only.
Verified failing head: `54ff7a6890a689b87d6bd91f825d230aebfee4d7`.
Hardened reconciler base: `850c8d870ee6b639bb51df8603cc35e8149229cc`.
Production main: `8b7f8b48694364cb8c47456d0ab491b102aa42c0`.

This document is the remediation authority for the two blocking defects reproduced by independent read-only reverification. It does not authorize deployment, Railway mutation, evidence reset, a certification window, strategy changes, direct provider polling, or trading.

Permanent certification rule:

**Operational Health PASS + Evidence Integrity PASS + CLEAN classification = certifiable evidence.**

The Sentinel remains a recorder/provenance system and has no authority to certify evidence.

## Blocking finding 1 — durability-acknowledgment failure is forgotten after restart

### Reproduction

Independent reverification injected failure at the final checkpoint directory `fsync`. The live process became unhealthy, but the ledger row and committed-looking anchor could remain present. A newly constructed recorder then accepted that state as valid. The runtime failure counter was process-local, so a later successful cycle could return `/health` 200.

### Required behavior

1. Any failure in the append durability-acknowledgment sequence after evidence/anchor mutation begins must leave **persistent fail-closed provenance** that survives process restart.
2. Reopen must not accept an append whose prior process failed to obtain the required durability acknowledgment merely because the ledger row and anchor look structurally complete.
3. The persistent failure state must not be auto-cleared by a later ordinary recording cycle or by process restart.
4. Clearing/recovering such a state must require an explicit, separately auditable recovery action; normal recorder startup must not silently repair, truncate, adopt, or discard evidence.
5. `/health` and top-level `/state.ok` must remain false while the persistent durability-failure state is present.
6. `LedgerStatus.chain_valid` (or equivalent public ledger integrity signal) must not report healthy for an unresolved durability-acknowledgment failure.
7. Existing protections for short writes, failed file `fsync`, missing newline, tail deletion, full truncation, missing/modified checkpoint, and write rollback must remain intact.

### Acceptable implementation direction

Use a durable fault/uncertainty marker or equivalent persistent transaction-failure state created as part of the append protocol and retained when final durability acknowledgment fails. The design must be tested across close/reopen/new-runtime construction. Do not rely only on in-memory `_write_failed`, runtime counters, or a current-process exception.

If the mechanism itself cannot durably record the failure, startup must still fail closed rather than infer that the last append was acknowledged.

### Mandatory regression probes

- Inject final checkpoint directory `fsync` failure after ledger bytes and checkpoint replacement have occurred.
- Confirm current process health fails.
- Destroy/reopen the ledger object and construct a fresh runtime.
- Confirm ledger status remains failed and `/health` remains 503 / `ok:false`.
- Run a subsequent otherwise-successful cycle and confirm the persistent failure is **not** automatically cleared.
- Confirm a normal restart does not reset the failure counter/state into health.
- Confirm no evidence is silently truncated, rewritten, or adopted as clean.

## Blocking finding 2 — malformed redirect loses the received HTTP evidence envelope

### Reproduction

A malformed `Location` response caused Requests redirect parsing to raise before the current fetch path retained the returned `Response`. No redirect hop was followed and health failed closed, but the Sentinel lost already-received HTTP status, headers, and body bytes.

### Required behavior

1. The transport must not follow redirects.
2. Redirect parsing must not be allowed to discard a response already received from the approved source URL.
3. For every received response — including malformed `Location` headers — the immutable observation envelope must preserve, when available:
   - configured/request URL;
   - actual response URL;
   - GET method;
   - HTTP status;
   - response headers including raw `Location` value as represented by Requests;
   - body bytes/base64 representation;
   - body byte count and SHA-256;
   - body completeness state;
   - start/completion timestamps and latency;
   - parse outcome/error;
   - transport/validation error type.
4. Redirect/malformed-redirect responses must remain unhealthy and must never cause a second network request.
5. Destination validation must remain fail closed for direct Kalshi, Coinbase, BRTI/provider hosts, non-Railway hosts, HTTP, alternate ports, user-info, fragments, backslashes/control characters, and alternate Railway redirect hops.

### Acceptable implementation direction

Avoid Requests behavior that parses or resolves `Location` before returning the first `Response`. A custom no-redirect `Session`/transport or direct adapter send is acceptable if it preserves TLS/timeout semantics and still permits complete first-response capture. The first response must be recorded before redirect-destination validation determines health.

### Mandatory regression probes

Using an offline/local transport only:

- 301/302 with malformed `Location`.
- 301/302 redirect to direct Kalshi.
- 301/302 redirect to direct Coinbase.
- 301/302 redirect to plain HTTP.
- 301/302 redirect to non-Railway host.
- 301/302 redirect to another otherwise-approved Railway host.

For every case:

- exactly one source request is attempted;
- no redirect hop is followed;
- health fails closed;
- the first response's status, headers and body are retained in the ledger envelope.

## Existing limitations that are NOT fixed by these two remediations

These remain explicit and must not be hidden:

1. **Kalshi provider-specific freshness: INSUFFICIENT.** Missing provider-specific facts remain UNKNOWN and block certification.
2. **Coinbase provider-specific freshness: INSUFFICIENT.** Missing provider-specific facts remain UNKNOWN and block certification.
3. Healthy operation requires a separately captured, independently sourced control-plane snapshot matching the frozen expected manifest.
4. Coordinated rollback/removal of both local ledger and local continuity anchor still requires an external witness for detection.
5. The five-minute synthetic sustained-load run was encouraging but does not establish long-run capacity; growing cycle costs require later soak/capacity validation.

These limitations do not authorize weakening the Sentinel gates.

## Required final verification after remediation

Before any deployment consideration:

1. Compile every `.py` under `integrity_sentinel/`.
2. Run every Sentinel unit/regression test.
3. Run all hardened `integrity/` tests.
4. Run `python -m integrity.adversarial_hardening_v1`.
5. Run `python -m integrity_sentinel.adversarial_hardening_v1`.
6. Independently reproduce both failures above, including fresh-process reopen for the durability case and malformed `Location` envelope retention for the redirect case.
7. Re-run the prior 28 Sentinel adversarial probes and ensure no regression.
8. Confirm all changes remain under `integrity_sentinel/` only.
9. Confirm `integrity/` and production `main` remain unchanged.
10. Confirm no Railway, production, evidence, cutoff, certification-window, direct-provider-polling, strategy, order, or trading action occurred.

Passing remediation means only:

`READY FOR SECOND INDEPENDENT READ-ONLY REVERIFICATION`

It does **not** authorize deployment or certification.