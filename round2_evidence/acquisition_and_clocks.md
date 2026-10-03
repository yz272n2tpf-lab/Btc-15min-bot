# Acquisition and real clock prerequisites — 29 September 2026

Status: BLOCKED. This package is an offline evidence contract and consumer, not a continuously materialized live acquisition service. No platform resource was provisioned and no native/common-export endpoint was polled. No production service, volume, branch, variable or scheduler was changed.

## Exact acquisition boundary

The already-identified common observer's original one-record gzip members preserve parsed protected state. Its `read_source`, `observe_forever`, `append_record` and `export_chunk` implementation is included as a reference. The original member is not original HTTP response bytes. Collector request/receipt labels are not native source/receipt/publication witnesses. Its summary stdout is not the member payload.

The required missing component is an independently operated materializer of **already completed original members** and the original run manifest. It must retain bytes unchanged, bind service/deployment/build/run/epoch/stream and byte offsets/member sequence, authenticate its route and signing principal, and make immutable replicas continuously available outside the observer's execution and storage demand path. A hash proves content integrity, not upstream identity. HMAC sealing in the frozen adapter proves only the configured signer's statement; the real acquirer and its premises remain unqualified.

Minimum acceptable behavior: no native GET, duplicate protected evaluation, native callback, native lifecycle serialization/fsync, observer/exporter request, shared-file polling or consumer-driven lock; no ACK or retry pressure into the observer; consumer absence cannot slow production. Local spool/queue limits and overflow must yield explicit loss/gaps without changing native/common behavior. Exact continuity must survive runtime epochs; no automatic skipped offset acceptance. A new stream needs a new signed manifest and explicit discontinuity. All certificates, original manifests, peer/route evidence and original member hashes must be retained.

A provider-managed continuously updated file replica or host-level bounded immutable-member mirror could satisfy the boundary **if the provider can demonstrate these properties and the demand isolation**. No such Railway facility was found or attested. A process reading the same volume, a sidecar, stdout redirection, an S3 upload loop or a downstream polling exporter is not automatically independent. Merely buying a bucket does not solve source materialization.

## Platform evidence, without repeating the old exporter experiment

The read-only Railway control-plane snapshot shows the existing common service, one `iad` replica, a `/data` volume, its repository branch and start command. It supplies no continuously detached copy route or clock attestation. Configuration is not proof of the currently running commit; the historical collector reference remains separately identified.

| Official capability checked | Result for this prerequisite |
|---|---|
| Railway volume reference | One volume per service and no volume replicas; no documented second read-only live mount with independent demand. |
| Volume backups | Scheduled daily/weekly/monthly snapshots, not a continuous original-member feed. |
| Logging | No platform log-drain setting. Existing stdout lacks complete member bytes; user-side forwarding would add work. The documented rate limit can discard log lines. |
| Storage bucket | S3-compatible sink, not an existing file materializer. No object versioning or object lock is currently supported. Application identity plus hashes alone do not create provider-enforced immutability. |
| Point-in-time recovery | Database-specific PostgreSQL/MySQL logging, not an arbitrary gzip journal mirror; enabling it creates resources and redeploys. |

These observations exclude the documented facilities as a presently qualified solution. They do not prove dedicated or enterprise infrastructure necessary. An ordinary external collector might be sufficient once a suitable provider-side copy primitive is proven, but it cannot originate missing native witnesses or complete lifecycle events.

## Real clocks: required generator and invalidation

The frozen `btc15_external_clock_guard_v1.Bound` and its interval predicates are reused unchanged. `clock_receipts.py` is only an authenticated offline certificate receiver; its live mode deliberately refuses admission with `LIVE_CLOCK_PRODUCER_NOT_QUALIFIED`. Synthetic zero-error fixtures are never real clock certificates.

A feasible live producer must be operated in, or independently attest, each actual timestamp domain: selected source/owner, native protected generation/consumption, parity, collector request/receipt, detached acquirer, consumer activation/consumption/current availability and actual display exposure. UTC-looking labels do not establish a common oscillator or epoch. An exchange source clock requires its own genuine witness/bound, or the source-time predicate remains unavailable.

The monitor needs authenticated time-reference identity, bounded reference error/asymmetry, offset-error evidence, a justified worst-case rate/drift bound (not an RMS estimate), timestamp-read uncertainty, reference and validity labels, signer/runtime identity, monitor sequence, clock epoch and certificate ID/hash. Paired original UTC and suspension-aware elapsed-time readings must be retained; do not shift original event labels. Certificates include evidence identifiers for every bound premise. A chrony tracking report alone cannot attest all these facts. Its documented absolute offset plus root dispersion plus half root delay expression is conditional on the reference assumptions and does not alone prove a worst-case drift bound.

Monitor at least every second and issue certificates with validity no longer than five seconds **only when the measured/attested premises justify that lifetime**; this is a capture-health setting, not a native cadence or BRTI threshold change. A monitor heartbeat miss, reference loss, certificate expiry, clock step, rate-bound violation, restart/boot-ID change, unknown suspension, or ambiguous domain binding invalidates the epoch/certificate. A new runtime/clock epoch cannot inherit an old certificate. Receivers persist certificates and revocations with original evidence and require the full event interval to lie inside validity. No reconnect may retroactively qualify a gap.

No real host/clock monitor, authenticated reference measurement or maximum-rate attestation was supplied by the available Railway control-plane surface. This mission has therefore generated **zero live-qualified clock certificates**. A monitor in a different container cannot certify an unbound producer domain merely by being on the same platform.

Use the existing interval guard at admission and every exposure. If any feasible time crosses BRTI <=5 seconds, ordering, rollover, FINAL confirmation/protection or availability boundary, return UNAVAILABLE and retain origins. Never convert BRTI age to a source timestamp. The unchanged +/-400 ms false-HOLD regression is a mandatory gate.

## Complete event producers are also a prerequisite

The common snapshot can preserve whole protected EARLY/FINAL and owner/V8.1/serial objects as emitted. It cannot be certified as every native evaluation, every rejected gate, every exchange quote/size/sequence, every SCALP lifecycle/BRTI evaluation, or a complete scheduled-contract catalog. All absent fields are explicitly unavailable in the producer map. The future event-audit port validates explicit upstream IDs; it does not create those IDs or infer accepted BUYs, FINAL links or SCALP exits.

Required producer work must expose existing evaluation facts without strategy changes and must respect the no-native-callback/no-native-persistence boundary. If the facts are not already externalized, this package cannot solve that by reconstructing them from later states. Identify a genuinely passive supported export seam for each missing producer, then qualify its demand and exact event completeness before integration.

## Costs and stop condition

New resources created: none. Incremental recurring cost incurred: **$0/month**. No deployment or Round-2 start boundary exists. No budget approval is requested for an unproven mechanism.

Current ordinary Railway list rates checked: CPU $20/vCPU-month; RAM $10/GB-month; volume $0.15/GB-month; service egress $0.05/GB; bucket storage $0.015/GB-month. Bucket operations and bucket egress are free, while uploads from a service can incur service egress. These are unit rates, **not an exact implementation quote**. Capacity, throughput and a valid provider copy facility are unknown, so a truthful exact incremental monthly total is unavailable. Never reuse an old illustrative cost range as an approved design.

Once the technical copy/clock/producer paths exist, provide the concrete ordinary service/bucket configuration, caps/region/retention/identity, measured byte volume, exact expected recurring cost and rollback for approval before provisioning. Rollback must detach only the new evidence consumer/materializer and revoke its credentials; strategy and existing observer remain untouched. Dedicated or enterprise resources have not been justified.

## Official sources checked

- https://docs.railway.com/volumes/reference
- https://docs.railway.com/volumes/backups
- https://docs.railway.com/observability/logs
- https://docs.railway.com/storage-buckets
- https://docs.railway.com/volumes/point-in-time-recovery
- https://docs.railway.com/pricing/plans
- https://chrony-project.org/doc/4.6.1/chronyc.html
