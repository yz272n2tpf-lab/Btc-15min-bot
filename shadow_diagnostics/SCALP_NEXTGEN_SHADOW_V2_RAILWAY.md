# Railway deployment specification — scalp-nextgen-shadow-v2

Apply only after one service slot is available.

- Project: `noble-warmth`
- Environment: `production`
- Service: `scalp-nextgen-shadow-v2`
- Repository: `yz272n2tpf-lab/Btc-15min-bot`
- Branch: `scalp-nextgen-shadow-v2`
- Start command: `python shadow_diagnostics/test_scalp_nextgen_shadow_v2.py && exec python -u shadow_diagnostics/scalp_nextgen_shadow_v2.py`
- Healthcheck: `/health`
- Healthcheck timeout: `120`
- Restart policy: `ON_FAILURE`, maximum 3 retries
- Volume: none
- Replicas: one
- Cutoff: `2026-09-16T19:50:00+00:00`

Required variables:

- `PYTHONUNBUFFERED=1`
- `SCALP_NEXTGEN_V2_CUTOFF_UTC=2026-09-16T19:50:00+00:00`
- `SCALP_NEXTGEN_V2_POLL_SEC=180`
- `SCALP_PATH_EXPORT_URL` copied by Railway reference from the existing read-only shadow source
- `SCALP_PATH_EXPORT_TOKEN` copied by Railway reference from the existing read-only shadow source

Deployment acceptance:

1. Build succeeds from the exact V2 branch.
2. `/health` returns the V2 version and `orders:false`.
3. Startup log contains `FOUR INDEPENDENT SHADOW LANES | NO ORDERS`.
4. State reports the prospective cutoff exactly.
5. All four result families exist independently.
6. `runtime_integrity.all_checks_pass` is true and all Watch lanes report the identical frozen Exit count.
7. No volume is attached and no production or frozen service is modified.
