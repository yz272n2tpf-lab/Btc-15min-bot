# BTC15 Scalp Specialist Live Review V2 — Isolated Railway Plan

**Research only | signal only | no orders | no production writes**

This plan launches the already-built `scalp_specialist_union_live_review_v2.py` as a separate Railway service. It does not merge PR #4 and does not modify the production bot, FINAL, EARLY, or the existing scalp collector.

## Service

- Railway project: existing BTC15 project
- Environment: production environment, separate service
- Proposed service name: `scalp-specialist-review-v2`
- GitHub repo: `yz272n2tpf-lab/Btc-15min-bot`
- Branch: `shadow-diagnostic-pack-v1`
- Start command:

```text
python -u shadow_diagnostics/scalp_specialist_union_live_review_v2.py
```

- Health path: `/health`
- Health timeout: 60 seconds
- Restart policy: `NEVER` for the first review run so any failure is visible
- Volume: none required; service is read-only and recomputes from the source export

## Variables

Required non-secret values:

```text
PYTHONUNBUFFERED=1
SCALP_SPECIALIST_REVIEW_POLL_SEC=300
SCALP_PATH_EXPORT_URL=https://scalp-move-shadow-v1-production.up.railway.app/research/path-export
```

Required secret/reference:

```text
SCALP_PATH_EXPORT_TOKEN=<reference the existing scalp-move-shadow-v1 PATH_EXPORT_TOKEN>
```

Do not copy the token into chat or source control. Prefer a Railway variable reference to the existing collector service value.

No Kalshi trading key is required by the review service. It consumes the existing read-only event export only.

## Expected startup

```text
BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V2 START | READ ONLY | POLL=300s | SIGNAL ONLY | NO ORDERS
```

`GET /health` should return an HTTP 200 document containing:

- `orders: false`
- `shadow_only: true`
- analysis status

After a successful source pull and analysis, `GET /state` should show:

- `status: RESEARCH_SNAPSHOT_READY`
- source SHA / bytes / row count
- full observed contract count
- serial opportunity count
- baseline true coverage and +10c conversion
- specialist lane breakdown
- Specialist Union V2 validation-selected candidate
- Specialist Union V2 untouched holdout result
- normalized Kalshi-lag validation-selected candidate
- normalized Kalshi-lag untouched holdout result
- contract-zone map
- cumulative coverage by 12m / 9m / 6m / 3m / 2m remaining
- `orders: false`
- `automatic_promotion: false`

## Fail-closed states

Do not interpret a result if the service reports:

- `FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE`
- `FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR`
- missing source SHA
- zero full observed contracts
- source export authentication failure
- any order-capable behavior

## Review rule

The first real-tape snapshot is discovery/review evidence, not certification. Any lane/threshold selected after inspecting this dataset must be frozen into a new version and evaluated on a new untouched forward window before promotion.

The purpose of this service is to answer the current research question without contaminating the live collector:

> Can specialist scalp lanes plus quality-gated coverage rescue raise executable +10c conversion while retaining high true contract coverage and useful <=50c entry coverage, and where in the 15-minute contract does that coverage arrive?
