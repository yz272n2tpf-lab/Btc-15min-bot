# BTC15 coordinated integrity rollout checkpoint — 2026-09-24 00:18 UTC

Status: infrastructure/data-integrity candidate deployed and live; full trading-performance certification remains pending elapsed forward evidence. SIGNAL ONLY / NO ORDERS.

## Promoted revisions and rollback points

- V8.1 timestamped-source correction: PR29 head `b05723ec622f901a05402ecf27f4d33505753ef1`; Railway deployment `4105da0a-e5a2-4a76-8abc-242b0bab5ad8` SUCCESS. The service health response states `signal_only=true`, `orders=false`.
- Main immutable-model/publication/accounting release: PR31 merged as `d54321927626529612b7309576d7dc90b84fe224`; Railway deployment `0b2ef3ff-1499-432a-ac70-52b997bb2e26` SUCCESS. PR30 and PR26 ancestry is retained. Previous main deployment `5eb83c64-9329-4cf2-bb7b-6a5b42b222bf` is Railway-rollback-capable.
- No threshold, ladder weight, target, settlement, freshness limit, credential, service deletion or order behavior changed.

## Main restart/model identity

- Startup `READY: YES`.
- Immutable fair-model artifact SHA256: `1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816`.
- Recomputed model-weights SHA256: `95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6`.
- Startup explicitly logged `NO STARTUP FIT`; production loads the frozen artifact and rejects identity mismatch.
- Initial BRTI gate was closed during startup, then 598 retained publication seconds were recovered before normal shared-owner consumption. No traceback was observed.
- Main `/data` remains a 10 GB persistent volume. Clean collector `/data` remains a 50 GB persistent volume.

## First complete post-restart boundary

Contract `KXBTC15M-26SEP232030-30`, official open `2026-09-24T00:15:00Z`:

| Stage | Measured from open |
|---|---:|
| Exact-ticker staged handoff | +1.061 s |
| Official target and BTC ready | +6.156 s |
| Timestamped Kalshi book usable | +6.311 s |
| Contiguous quotes consumed / first source snapshot | +11.268 s |
| Full parity PASS observed | +25.765 s |

Parity reported exact contract, clock delta 0.0 s, target delta $0.00, timestamped WebSocket quote delta 0.0 c and BRTI publication match. BRTI true-source age at parity collection was 3.242 s, within the unchanged 5-second gate. The public main state subsequently had source/display age 0.08 s, within the unchanged 3.5-second publication gate, exact target `$84,345.33`, paired quotes, fresh BRTI and `orders_enabled=false`.

This is **1** complete consecutive contract on the restarted immutable-model identity. Earlier four-contract infrastructure acceptance remains valid historical evidence but is not substituted for the new identity's required consecutive evidence.

## V8.1 quote correction

- At the 00:15 boundary V8.1 failed closed on `OFFICIAL_MARKET_UNAVAILABLE`, then `TIMESTAMPED_QUOTES_UNAVAILABLE`, and accepted the new exact ticker only after a timestamped contiguous book existed.
- Current state carries `V81_TIMESTAMPED_INPUTS_V1`, exact ticker/open/close/target, exchange quote source timestamp/sequence and true BRTI source timestamp/owner epoch; it remains WAIT when no 30–45c setup qualifies.
- No corrected V8.1 entry has qualified since promotion. Therefore no executable stop/profit-protection result is claimed and the pre-correction 40c event remains excluded.
- PR26's exit policies remain prospective hypotheses and `production_connected=false` until a valid provenance-qualified entry/path supplies separated evidence. No arbitrary exit threshold was promoted.

## Shared BRTI and parked execution

- Intended owner deployment `b0ddbbbb-7d7a-43ba-888f-9d7e8c6b3fd8` remained PRIMARY_OK/clean during the rollout. Sampled 00:00–00:06 heartbeats showed source ages 0.586–2.585 s, cumulative one recovered upstream error, zero HTTP 429s, and NO ORDERS. These point samples are not a continuous-availability claim.
- Main and V8.1 consume the shared owner. `scalp-lead-v6-main` redeployed from the main branch but its explicit command remains PARKED, restart policy NEVER, with no live Kalshi polling.
- Persistent clean collector identity remains exactly `clean-source-v2-1s-20260923`, commit `e98576f23e247349b90717aea3a3ad832d409354`, `legacy_shared_http`, 5-second qualification age, signal-only/orders false.

## Evidence preservation and tests

- The clean journal was incrementally exported through byte `84,255,925`. Every range offset/next-offset/SHA256 header was verified; the complete retained prefix passed gzip CRC. It was not mixed with the old five-second run.
- Local main regressions: 201/201 PASS. Completion audit: 29/29 PASS.
- Hosted exact-head runs: main regressions `35936318652` PASS (201/201); V8.1 exit/accounting `35936318647` PASS; artifact preservation `35936318651` PASS with two identical fits and exact reload.

## Frozen-cohort boundary and remaining elapsed gates

- Canonical cohort hash remains `fcc75fdc1ace0f31e959d59f5038cfaa530da6147e0870e5b811246ba2d0163e`.
- The main identity changed at deployment startup near `2026-09-24T00:04:49Z`; pre- and post-restart observations must not be pooled as one runtime/model identity.
- Development ends `2026-09-24T21:15:00Z`; validation ends `2026-09-25T21:15:00Z`; untouched holdout remains sealed until `2026-10-09T21:15:00Z`.
- Remaining evidence gates are: three more consecutive complete post-restart contracts; a provenance-qualified V8.1 entry plus prospective executable ask-to-bid exit path; completed development-only joint ladder/EARLY/FINAL/SCALP analysis; then validation and untouched-holdout evaluation at their fixed ends. No tuning is authorized from the current partial window.

The uncertified historical `263/278` FINAL aggregate is not used as proof. No 93–95% claim is made.
