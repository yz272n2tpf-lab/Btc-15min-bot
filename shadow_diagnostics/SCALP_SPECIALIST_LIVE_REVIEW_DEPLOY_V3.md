# BTC15 Scalp Specialist Live Review V3 — Isolated Railway Plan

**Research only | signal only | no orders | no production writes**

V3 launches the read-only review surface with the full scalp research stack:

- Specialist Union V2 quality + coverage rescue
- contract-zone map
- normalized Kalshi lead/lag fingerprint
- specialist-lane complementarity / overlap
- multi-objective Pareto frontier across hit rate, true coverage, affordable coverage, entry price and earliness

It does not merge PR #4 and does not modify the production bot, FINAL, EARLY, or the existing scalp collector.

## Service

- Railway project: existing BTC15 project
- Environment: production environment, separate service
- Proposed service name: `scalp-specialist-review-v3`
- GitHub repo: `yz272n2tpf-lab/Btc-15min-bot`
- Branch: `shadow-diagnostic-pack-v1`
- Start command:

```text
python -u shadow_diagnostics/scalp_specialist_union_live_review_v3.py
```

- Health path: `/health`
- Health timeout: 60 seconds
- Restart policy: `NEVER` for the first review run so failures remain visible
- Volume: none; the service is read-only and recomputes from the source export

## Variables

Non-secret:

```text
PYTHONUNBUFFERED=1
SCALP_SPECIALIST_REVIEW_POLL_SEC=300
SCALP_PATH_EXPORT_URL=https://scalp-move-shadow-v1-production.up.railway.app/research/path-export
```

Secret/reference:

```text
SCALP_PATH_EXPORT_TOKEN=<reference the existing scalp-move-shadow-v1 PATH_EXPORT_TOKEN>
```

Never copy the token into chat or source control. Prefer a Railway variable reference to the collector's existing value.

No Kalshi trading key is required by the V3 review service.

## Expected startup

```text
BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3 START | READ ONLY | POLL=300s | SIGNAL ONLY | NO ORDERS
```

## Expected `/state` additions

In addition to the V2 review snapshot, V3 reports:

- `multiobjective_pareto`
  - non-dominated validation configurations only
  - +10c conversion
  - true contract coverage
  - <=50c affordable true coverage
  - average entry ask
  - average minutes remaining
- `lane_complementarity`
  - unique contract contribution from each lane
  - pairwise lane overlap
  - all non-empty specialist-lane subset combinations

These diagnostics do not choose or certify a production rule.

## Fail-closed states

Do not interpret a research result if the service reports:

- `FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE`
- `FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR`
- missing source SHA
- zero fully observed contracts
- source export authentication failure
- any order-capable behavior

## Review discipline

1. Read the real-tape snapshot once as discovery evidence.
2. Do not retune from HOLDOUT.
3. Do not merge a rule merely because it appears on the Pareto frontier.
4. If a promising rule is identified, freeze it into a new version.
5. Evaluate that frozen rule on a newly untouched forward window.
6. Keep scalp movement utility separate from FINAL settlement accuracy.

The V3 research question is:

> Which non-dominated combination of specialist scalp logic, quality filtering and coverage rescue improves executable +10c movement while preserving high true contract coverage, useful <=50c coverage and early enough entries—and is the edge concentrated in measurable BTC/BRTI lead versus Kalshi repricing lag?
