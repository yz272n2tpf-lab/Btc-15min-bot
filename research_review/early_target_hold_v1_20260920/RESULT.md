# EARLY_TARGET_HOLD_V1 — development result

**Decision: REJECT. Zero qualifying calls.**

Preregistration commit: `addca89ff21e9bf11edd76ef7fafb909f6d164ba`

Development source: `subminute_early_dataset_v1.csv` (57 settled historical contracts; development evidence only).

No clean post-fix validation data was accessed.

## Result

- Calls: **0 / 57**
- Coverage: **0%**
- No settlement accuracy can be estimated because the frozen rule never qualified.

## Interpretation

The frozen hypothesis required an EARLY side priced <=50c to already be at least $40 ahead of the exact target, to have stayed at least $15 ahead for a full trailing minute, and to show no net cushion erosion with nonnegative 15s/30s momentum.

No historical observation met all conditions.

This supports a mechanical constraint relevant to the desired EARLY economics: by the time a side has a sustained, meaningful target-side cushion, the <=50c opportunity may already have disappeared. A useful cheap EARLY settlement call therefore likely has to identify a future target crossing/hold **before** the side is already safely ahead.

No thresholds were loosened after seeing the result.

SIGNAL ONLY / NO ORDERS.
