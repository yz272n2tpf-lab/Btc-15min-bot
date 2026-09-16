# Railway deployment — scalp-nextgen-shadow-v2

Status: prepared and tested locally; **not deployed**. Do not merge this branch into main or any frozen collector branch.

Project `noble-warmth` (`baea4e22-d004-4434-b2c5-81a7fbc05086`), environment `production` (`61775c5d-c583-4dfc-af41-f25578856fd9`). Repository `yz272n2tpf-lab/Btc-15min-bot`, branch `scalp-nextgen-shadow-v2`. Create only the new service of that name, one replica, no shared volume.

## Service slot

The read-only September 16 check still found 50 services. The only authorized deletion is failed legacy `v81-30-45-live-feed` (`52a489b0-b87f-4e04-a16e-19ae721098f6`), after another check that `v81-30-45-live-feed-v2` (`afd8f1f0-65f6-46f0-a79b-ef582f35293f`) is SUCCESS/active. Approval is already present in this Work thread. No other service may be removed, edited or restarted.

The direct connected tools do not expose deletion; Railway Agent returned its usage-limit error. User plans to delete the legacy service on returning home. No deletion was performed in this milestone. After deletion, verify 49 services and replacement health before creating the combined shadow service.

## Branch configuration

The branch's root `railway.json` now explicitly starts the V2 tests and V2 server, so a new service cannot accidentally fall back to the production bot entry point:

`python shadow_diagnostics/test_scalp_nextgen_shadow_v2.py && exec python -u shadow_diagnostics/scalp_nextgen_shadow_v2.py`

Healthcheck `/health`, timeout 120 seconds; ON_FAILURE, maximum 3 retries. This branch-only configuration validates against the [official Railway configuration schema](https://docs.railway.com/config-as-code/reference). Frozen branch configurations remain unchanged.

Required variables on the NEW service only:

- `PYTHONUNBUFFERED=1`
- `SCALP_NEXTGEN_V2_POLL_SEC=180`
- `SCALP_NEXTGEN_V2_EXPECTED_CODE_SHA256=ec18e01e3c50cd3e52142e1451e28d985bbceeb1c602404d0aad6c51a20689c1`
- `SCALP_NEXTGEN_V2_CUTOFF_UTC`: a new explicit UTC boundary after successful deployment acceptance; do not reuse `19:50Z` or any pre-R2 sample.
- `SCALP_PATH_EXPORT_URL` and `SCALP_PATH_EXPORT_TOKEN`: Railway variable references to the existing read-only export configuration; do not print secrets or add trading credentials.

Initial creation can run without activation variables: liveness succeeds, analysis fails closed, and no export polling occurs. Set the new service's variables together before its activation deployment. Choose a future cutoff with enough time to verify that deployment before the cutoff arrives; if it is missed, move the still-unstarted window forward. Record the exact code commit, fingerprint, cutoff, deployment ID and window ID before admitting observations. No volume is required: results replay the source export. Export retention bounds evidence availability; archive the read-only audit/source metadata at review milestones.

## Acceptance

1. Correct new service, source branch/commit and V2-only start command; no production command or shared volume.
2. All 27 startup tests pass using pinned requirements; build and runtime logs succeed.
3. `/health` is process liveness only. `/ready` must return 200 after successful source analysis; 503 means activation, freshness, or scoring is not healthy.
4. `/state` contains all four families and 24 total policy lanes, exact activation cutoff, code fingerprint, window ID, source SHA, safety flags and passing runtime integrity. Zero eligible observations is valid before the cutoff/first completed contracts.
5. Every Watch lane has identical per-opportunity exit time/gain; `/audit` provides the records. Retention and missing outcomes remain visible.
6. Confirm the source timestamp is fresh, then recheck health and logs after another poll. Source errors must clear scores and return 503 readiness.
7. Re-read frozen control deployment IDs and verify they are unchanged. No orders, production changes or automatic promotion.

Do not call V2 deployed or healthy until those checks actually pass on Railway.
