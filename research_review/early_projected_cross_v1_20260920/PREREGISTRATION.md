# BTC15 EARLY Projected Cross V1 — preregistration

**Status:** FROZEN BEFORE SCORING  
**Mode:** READ-ONLY RESEARCH | SIGNAL ONLY | NO ORDERS

## Objective

Predict the official final UP/DOWN settlement side early enough to buy the eventual winner while it is still <=50c.

Primary metric: official Kalshi settlement-direction accuracy.

## Development source

`subminute_early_dataset_v1.csv` only. Historical development evidence; not a new untouched holdout.

The post-fix clean validation window remains untouched.

## Candidate: EARLY_PROJECTED_CROSS_V1

Scan both sides chronologically; emit at most one call per contract, earliest qualifying timestamp.

A side qualifies only when:

1. **7.0 to 10.0 minutes** remain.
2. Actual side ASK is **<=50c**.
3. The side is still behind the exact target: `btc_gap_side < 0`.
4. Side-aligned BTC momentum is positive over **15s, 30s and 60s**.
5. 30-second projected time to target is <= **90 seconds**:
   `t30 = -btc_gap_side / (btc_move_30s_side / 30)`.
6. 60-second projected time to target is <= **120 seconds**:
   `t60 = -btc_gap_side / (btc_move_60s_side / 60)`.
7. Current 15-second speed is at least **75%** of 30-second speed, to reject sharp deceleration:
   `btc_move_15s_side / 15 >= 0.75 * (btc_move_30s_side / 30)`.
8. Kalshi has not already repriced by more than **10c over 30 seconds**:
   `ask_move_30s <= 0.10`.
9. Missing/non-finite values fail closed.

If both sides qualify at exactly the same timestamp, choose the side with the shorter `t30`; exact ties produce no call.

No model fair threshold, no settlement label leakage, no post-entry excursion and no target-cross confirmation are used.

## Frozen advancement gate

Advance only if ALL are true:
- >=10 calls
- overall official settlement accuracy >=93%
- each chronological half >=90% accuracy where >=4 calls exist
- contract coverage >=10%
- every entry <=50c
- average ASK <=40c
- average minutes remaining >=7.0
- both UP and DOWN represented

If it fails, record rejection. Do not adjust thresholds after seeing results.

## Guardrails

FINAL unchanged. SCALP unchanged. Production/BRTI/Kalshi plumbing unchanged. Clean validation untouched. SIGNAL ONLY / NO ORDERS.
