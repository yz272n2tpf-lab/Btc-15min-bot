# Information ingress recovery — off-production candidate

Production base: `78b0f64db1e58e8bbeda5cad3df4d381f9dc1133`.
Diagnostic parent: `0a59f0b478065ec0caeb1b4a6da3b55c9fb87840`.
Qualified preview remains `9626115d3e017c235c55eaaae97b09e057992eb2`.
Rejected identity-source candidate `05240279dd5cc9a017240ae2474ee7e564f57100` is not included.

## Root cause and evidence boundary

The frozen native loop initializes `_fair_btc` once, before entering its loop.
Live FAIR subsequently combines that startup cache with `_ec_btc_ticks` using
the existing `frame_at_cut` builder. The tick buffer retains twenty minutes of
source-timestamped and receipt-timestamped observations. Native FAIR can therefore
remain supported after the historical cache is outside the current contract.

`NativeExport.offer()` exports only completed candles between contract open minus
six minutes and the native decision. In later contracts that slice is empty.
`check_anchor()` previously required **at least one completed candle**, regardless
of the genuine rolling tick support. It raised `COMPLETED_BOUND`, causing offer to
clear its anchor. Both native capture and health then failed. The production
service collapsed those failures into `INGRESS_UNAVAILABLE`; downstream identity
correctly returned 503 and the recovered app correctly redacted its fields.

This cause is reproduced with the exact frozen loop and the actual installed
`btc15_information_native_offpath_candidate.NativeExport`, not a mock evaluator:

- Startup candles end at 2020-01-01 00:05Z.
- Current contract opens at 00:15Z; decision is 00:20Z.
- Native FAIR exists and native unified output contains both UP and DOWN rows.
- The original anchor lower bound raises `COMPLETED_BOUND` and leaves no anchor.
- Corrected export publishes the same supported native features and probability.

Read-only production evidence was consistent with this failure: deployment
`eb798d44-1a2c-4181-8d23-62e87333c96a` was SUCCESS, the public information response
was WAIT/INGRESS_UNAVAILABLE with all source fields null, and logs showed ongoing
native FAIR/EARLY calculations well after startup. No live internal exception
trace was available: this is a deterministic source-level reproduction, not a
claim that a production diagnostic was deployed or every other possible ingress
failure was excluded. Healthy live intervals still require a controlled rollout
observation before the production blocker can be declared resolved.

## Minimal correction

`btc15_information_v1.py`: allow the truthful zero-length completed-cache slice.
The upper bound, candle validation, nonempty bounded ticks, causality, exact model
identity, original pure feature builder, and all feature-support checks remain.
No old candle is relabeled, no replacement feed is added, and no synthetic full
candle is introduced. Insufficient rolling support still fails closed.

`btc15_information_service_v1.py`: retain the diagnostic separation of capture,
health and public read failures. Wrap actual health calls explicitly so an
evaluation or journal exception cannot be mislabeled as health failure; those
use `PUBLISH_UNAVAILABLE`. No exception text or credentials reach public output.
Every failure still clears publication or returns a fully redacted WAIT.

No strategy file, model artifact, feature arithmetic, owner, cadence, persistence,
freshness limit, quote provenance, identity projection, recovered UI, cohort code,
cohort file, Railway setting or production branch is changed.

## Regression coverage

`test_btc15_information_ingress_recovery.py` covers the original failure, recovery
across seven later timestamps/contracts, exact feature equality with the frozen
native model, all guard phases, real loopback native HTTP ingress, durable
publication in temporary files, and matching downstream native identity.
Native UP probability matches exactly; DOWN differs at most by existing
complement arithmetic rounding (test bound 1e-15).

Adversarial cases cover missing/gapped tick support, malformed/oversized candles,
empty or noncausal ticks, stale BTC/BRTI, future receipts, quote sequence failure,
owner/ticker/anchor changes, health expiry, lock contention, quote outage,
contract rollover, recovery, evaluation failure and journal failure. Native
snapshots before/after information evaluation remain identical.

`test_btc15_information_ingress_preview.js` runs the exact preview's informational
script from its immutable git commit in a DOM harness. Real synthetic pipeline
frames display numeric flip risk, qualified BRTI and NORMAL/5M/3M phases. Expiry,
WAIT, wrong ticker/schema/nonce, identity 503, orders=true and lifecycle changes
clear those values. Authoritative card sentinels are unchanged. This is execution
coverage of the actual preview script, not an iPad/iPhone visual check.

## Qualification and deployment boundary

Required execution: existing full unittest discovery, the three packaged-runtime
and authority static gates, and the new ingress/preview tests included in discovery.
Use the existing hosted completion workflow with the repository's unchanged
pinned requirements. The final PR execution record must identify the exact SHA.

Initial local engineering evidence: original information suites 80/80; new focused
suite 11/11; packaged static gates 3/3. Initial complete discovery found two import
errors because this local runtime lacked requests; its model library was also
1.8.0 rather than pinned 1.9.0. Those local results alone are not production
qualification. Check the final preserved execution record for resolved results.

No merge, deployment, restart, cohort reset, scoring or ladder tuning is part of
this candidate preparation. Before controlled production use: qualify this exact
candidate under pinned dependencies, preserve the prospective cohort, and retain
the current production SHA as rollback identity. A subsequent authorized rollout
must observe genuinely qualified AVAILABLE intervals, matching identity with nonce
echo, <=5s BRTI, numeric Flip Risk and all guard phases on the recovered device,
plus fail-closed outage/rollover behavior. Do not count synthetic tests or restored
information availability as predictive-performance or cohort evidence.
