# Two-clock installation contract — not deployed

Activate only after Chat approves the final tested commit. `railway.json`, the current start command and production variables remain unchanged by this branch. `railway.information-candidate.json` is a reviewable optional configuration; it is not the active Railway configuration. No orders exist in this integration.

## Controlled installation

Use the exact qualified commit recorded in the final integration evidence. Preserve the production `/data` volume, existing credentials/source URLs, `PORT=8080`, all existing feature flags, single replica, region, healthcheck and V8.1 separate deployment. Set **only** `BTC15_ENABLE_INFORMATION_EXPORT=1` for this optional integration and use the candidate start command. If Railway retains a service-level start-command override, explicitly replace that override with the candidate command; adding a file alone does not activate it. Do not change the repository source branch to this audit branch without separate deployment approval.

The startup command still inventories/preserves evidence before launching the application. The installer locks `/tmp/btc15-two-clock.lock`, installs the exact existing dashboard payload/PR36 fixes and V8.1 inline diagnostic script, then adds a separate information panel. It changes only child path constants in generated copies of the original dashboard/full-validation/parity/Rescue supervisors. Those modules' executable logic is unchanged. The native leaf uses the accepted single read observer on the original PR36 AST. Root supervises an optional information worker using the existing restart/backoff behavior. SIGTERM terminates/reaps both process groups; no strategy state is written by this root or worker.

The original owner remains the only writer of histories, candles, persistence, event/profit state, cooldown/repeat gates, rollover, source state, journal/scoring and strategy CSVs. The original Rescue, parity, FINAL shadow collector and prospective observer remain connected. V8.1 remains its separately deployed owner, reached through the unchanged inline script. `Core NOT_LINKED`, `FINAL shadow_only=True`, `shadow_protection_used_as_action=False` and all undefined lifecycle policies remain unchanged.

## Routes, leases and bounds

| Surface | Boundary |
|---|---|
| Original `/dashboard_state.json`, native cards, fair-input journal, `/health` | Original implementation/authority; no information object is merged into it. |
| Public `/information`, `/information/frame/<64 hex>`, `/information/schema` | Closed informational schema. No entry/advice/lifecycle routes. Exact frame lookup has no latest fallback. Unknown paths and queries fail. HTTP methods other than GET do not perform work. |
| `/information/view.js`, `/information/panel.js` | Dedicated display assets. Only `btc15-information-*` DOM nodes are written. Native callbacks are never called. |
| Loopback `127.0.0.1:8766` | Read-only native input and health export. No public route forwards these paths. Ports are internal to this single replica. |
| Loopback `127.0.0.1:8767` | Separate inference/API process. Existing owner reads only; no authenticated BRTI/Kalshi/Coinbase requests are added. |

The worker polls input at 250ms intervals (at least 50ms rest after an overrun), evaluates only genuine source novelty, and checks native health both before and after inference. A separate sampler reads health at most four times/second. API reads revalidate the retained original source bundle against that sampler's **original observed timestamp** and one-second maximum lease. Reads cannot renew the lease or trigger native polls. Owner invalidation is observable on the next successful sampler read, bounded by the old lease if the sampler stalls; it is not a zero-latency revocation guarantee. Every display deadline is still bounded by original BRTI source time +5s, BTC +10s, quote +6s and contract close. No grace extends these deadlines.

The public proxy permits four in-flight requests, sustained 20 requests/second and a maximum burst of 20. Excess traffic gets explicit unavailable status. Slow worker responses time out after 400ms. Native routes retain a single request slot and socket timeout. The page polls every 500ms with a 700ms abort, counts full HTTP RTT against source freshness, and expires locally every 100ms. Tab/page lifecycle events invalidate captured tokens. A fresh request nonce echoed in a response header prevents an old cached/serialized HTTP response from being branded as a new fetch. Tokens are never persisted; an old deserialized token fails the adapter's page-local identity check.

The worker has one logical CPU affinity, nice +10, single numerical-library thread configuration, 2GiB address-space ceiling and 128 open-file ceiling. These limits apply only to its process. Information memory retains 32 exact byte frames, each bounded at 3MiB; the native anchor allows at most 32 completed rows and 4096 existing ticks. The quote owner retains its original 2MiB proof bound/rebase policy. No information file accumulates on `/data`; no informational observations enter native scoring. HTTP logs distinguish the `/information` namespace; response `authority` is always `INFORMATIONAL_READ_ONLY`.

## Rollback

Restore production commit **3e552065e34a0a402bc3ca4598b57dff1f1c6e77**, tree **586f8cfd635d6ed817c63202cdec0b8bcc454e0c**, deployment **f82466d0-70ab-4779-a0fd-58832ad31513**, and the exact original service start command saved in `TWO_CLOCK_INTEGRATION_PRODUCTION_CONTEXT_20260925.json`. Remove the optional export flag and optional candidate configuration selection. Keep `/data` and all existing source/model configuration. No information schema migration, strategy state rewrite or data deletion is needed. Verify the existing `/health` and dashboard/native telemetry chain. Leave V8.1 commit **b05723ec622f901a05402ecf27f4d33505753ef1** and deployment **4105da0a-e5a2-4a76-8abc-242b0bab5ad8** unchanged.

The connected EARLY/Core/FINAL product lifecycle remains unfinished exactly as mapped in `TWO_CLOCK_LIFECYCLE_SPEC_20260925.md`. This installation does not authorize any of those policies or solve actionable publication expiry.
