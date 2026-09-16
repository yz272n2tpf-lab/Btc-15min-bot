# BTC15 Scalp Coverage Rescue V1 — Prospective Forward Freeze

**Prospective cutoff:** `2026-09-16T05:00:21Z`  
**Local equivalent:** `2026-09-16 01:00:21 EDT`  
**Rule freeze:** `SCALP_COVERAGE_RESCUE_V1_FROZEN.md`  
**CI-gated branch commit immediately before cutoff:** `a0c0781c5d139406ae3520201ee70926b46c9ac2`  
**Mode:** SHADOW ONLY / SIGNAL ONLY / NO ORDERS / NO AUTO-PROMOTION

## Prospective inclusion

Only contracts whose **first passive tape observation is at or after 2026-09-16T05:00:21Z** may enter the forward denominator, and they must later be proven fully observed from >=840 seconds left through <=60 seconds left.

Any contract already underway at the cutoff is excluded. Historical/development data before this timestamp cannot contribute to prospective qualification.

## Frozen scorer comparison

The forward service reports, side by side:

- unchanged baseline
- Coverage Rescue V1
- baseline + rescue union
- incremental contracts added by rescue
- +5c / +10c / +20c on scoreable signals
- <=50c affordable contract coverage
- entry ask and timing
- missing-RESULT PATH reconciliation counts
- unresolved scoring records

## Certification gate

No certification decision before:

- >=100 fully observed post-cutoff contracts, and
- >=8 scoreable Rescue V1 signals.

Then manual-review PASS requires all frozen gates in `SCALP_COVERAGE_RESCUE_V1_FROZEN.md`, including >=90% union true coverage and preservation of scalp quality/economics.

The rule is not to be retuned using results from this forward window. If it fails, the result is frozen as a failed prospective version before any V2 research begins.
