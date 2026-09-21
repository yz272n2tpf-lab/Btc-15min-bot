# BTC15 Protected EARLY Tier-1 7–10m Forward Audit Freeze

**FROZEN BEFORE CLEAN VALIDATION START**  
**SIGNAL ONLY | NO ORDERS | READ ONLY**

## Validation boundary

- Clean development pool: contracts completed before **2026-09-21T02:45:00Z**.
- Buffer/excluded contract: contract spanning **02:45:00Z–03:00:00Z**.
- Untouched forward validation begins with contracts starting **2026-09-21T03:00:00Z** (11:00 PM ET on 2026-09-20).

Do not use any post-boundary contract to tune or change this study.

## Authority rule — unchanged

Protected Tier-1 EARLY remains exactly:

- preferred ASK <=45c
- preferred fair >=75%
- edge >=8 percentage points
- 2–10 minutes remaining
- absolute exact target gap >=$25
- first qualifying row per contract

No production threshold changes.

## Forward study slice

For validation reporting only, score protected Tier-1 calls whose **first protected call occurs with 7.0–10.0 minutes remaining**.

Primary success metric:
**official Kalshi final settlement side matches protected EARLY side.**

Also report:
- actual ASK
- 25–35c rate
- <=50c rate
- minutes remaining
- UP/DOWN balance
- eligible-contract coverage

No +5/+10 excursion metric determines pass/fail.

## Historical development context only

On the already-examined 199-contract cache:

- protected Tier-1 overall: 36/38 = 94.74%
- protected Tier-1 calls at 7–10m: **13/14 = 92.86%**
- 7–10m average ASK: **37.29c**
- 7–10m average time remaining: **9.14m**
- 5/14 entries were in the 25–35c band

These numbers are development context only and do not count toward forward validation.

## Sequential forward gate

- At 10 settled qualifying calls:
  - <=8 correct: fail/scratch the 7–10m confidence claim.
  - 9/10: continue unchanged.
  - 10/10: continue unchanged to 15.
- At 15 settled qualifying calls:
  - require >=14/15 = **93.33%** to support the 93–95% target range provisionally.
  - 13/15 or worse: fail the target.
- No threshold edits are allowed between checkpoints.

A pass supports only the exact protected Tier-1 7–10m slice. It does not authorize weakening EARLY or changing FINAL/SCALP.

## Guardrails

- Clean validation is not used for candidate creation.
- FINAL unchanged.
- SCALP unchanged.
- Production/BRTI/Kalshi plumbing unchanged.
- No auto-promotion.
- SIGNAL ONLY / NO ORDERS.
