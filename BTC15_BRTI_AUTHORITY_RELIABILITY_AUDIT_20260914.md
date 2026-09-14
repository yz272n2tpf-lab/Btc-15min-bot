# BTC15 BRTI Authority Reliability Audit — 2026-09-14

**Mode:** INFRASTRUCTURE AUDIT ONLY | SIGNAL ONLY | NO ORDERS  
**Protected FINAL thresholds:** UNCHANGED

## Why this audit exists

During combined-integration work, the live main bot showed repeated HTTP 429 responses from Kalshi's CF Benchmarks BRTI endpoint. The protected FINAL model itself is not being retuned, but the live V4.10 safety gate requires a fresh direct BRTI observation. A stale/missing BRTI can therefore fail closed and suppress an otherwise-qualified FINAL call.

This is an infrastructure/data-availability question, not a model-accuracy question.

## Main bot direct BRTI behavior observed

The main service repeatedly alternated between fresh observations and rate-limit failures. Examples from the live log include:

- Fresh/ready observations around 1–4 seconds old.
- Repeated `HTTPError: 429 Too Many Requests` responses.
- Stale stretches in which the last BRTI aged through 30s, 60s, 100s, and in some periods over 200s while `ready=False`.

A particularly important current-contract stretch occurred around 14:12–14:15 UTC: fresh BRTI was unavailable for several consecutive main-bot cycles even though the market and Coinbase feed continued moving.

Because the live FINAL safety gate currently requires BRTI age <=5 seconds, this can delay/suppress a FINAL signal independently of the protected V4.6 fair/gap/range evidence.

## Resilient generalized collector behavior

The locked generalized SCALP collector uses a resilience/retry path around the same BRTI source.

In the current live integration smoke, its first 251 BRTI samples reported:

- primary_ok: 221 / 251 = 88.0%
- HTTP primary errors: 30
- retry recovery counter: active
- missing: 0

The generalized collector continued to report `BRTI_STATUS PRIMARY_OK` / recovered usable BRTI throughout the observed scalp contract while the main direct call was intermittently stale.

## Protected V8.1 reference behavior

The protected V8.1 isolated service also uses BRTI resilience. A live cumulative checkpoint showed:

- samples: 146,556
- primary_ok: 121,370 = 82.8%
- HTTP errors: 25,186
- missing: 0

This demonstrates that primary endpoint failures are common enough that a resilience layer is materially relevant, while a fail-closed no-missing architecture is achievable without changing signal thresholds.

## Decision

Do **not** weaken or remove the protected BRTI safety gate merely to increase FINAL activity.

Instead:

1. Treat BRTI 429/staleness as an infrastructure reliability bug.
2. Preserve the exact freshness and target-side agreement semantics unless a separately frozen change is justified.
3. Build/test a resilient BRTI acquisition helper that only improves retrieval/retry behavior and never fabricates a price.
4. Shadow-compare resilient observations against direct BRTI before wiring them into protected FINAL authority.
5. Reduce unnecessary duplicate BRTI polling from obsolete diagnostic services where safe.
6. Re-run live FINAL timing verification after BRTI availability is stabilized.

## Acceptance standard

A BRTI infrastructure fix may be accepted only if:

- it uses the same Kalshi CF Benchmarks BRTI source or an explicitly equivalent verified passthrough,
- it never substitutes Coinbase for BRTI authority,
- stale data still fails closed,
- the <=5s freshness requirement is not silently loosened,
- target-side agreement semantics are unchanged,
- protected V4.6 FINAL thresholds remain unchanged,
- and no order-placement capability is introduced.
