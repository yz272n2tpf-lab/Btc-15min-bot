#!/usr/bin/env python3
"""
BTC15 numeric Flip Risk historical calibration gate V1.

READ ONLY | RESEARCH ONLY | NO BOT CHANGES | NO ORDERS

This scorer executes the already-frozen historical calibration validator, then
checks only the acceptance criteria predeclared in
BTC15_FLIP_RISK_NUMERIC_VALIDATION_FREEZE_20260915.md.

PASS authorizes only a future read-only shadow numeric-display validation.
It never changes EARLY, SCALP, FINAL, LOCK, PASS, entry, protection, or exit.
"""
from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss

SOURCE = Path("kalshi_flip_probability_calibration_validation.py")
ECE_MAX = 0.05
MAX_BIN_ERROR = 0.10
MIN_RELIABILITY_BIN_N = 20
MIN_MAX_ERROR_BIN_N = 30
MIN_STAY90_ACTUAL = 0.90
MIN_BLOCKS_TIE_OR_IMPROVE = 2

print("=== BTC15 FLIP RISK CALIBRATION GATE V1 ===", flush=True)
print("Frozen criteria only | historical OOS only | shadow-display authority at most | NO ORDERS", flush=True)

ns = runpy.run_path(str(SOURCE), run_name="__flip_calibration_gate_source__")
oos = ns.get("oos")
label_ok = ns.get("label_ok")

if oos is None or len(oos) == 0:
    raise RuntimeError("frozen calibration validator produced no OOS rows")

required = {
    "block", "elapsed", "flip", "raw_flip_prob", "flip_prob", "stay_prob",
    "current_side", "final_side", "ticker",
}
missing = required - set(oos.columns)
if missing:
    raise RuntimeError(f"missing frozen OOS columns: {sorted(missing)}")

# Integrity checks that are directly observable from the frozen OOS artifact.
settlement_label_consistency = bool(label_ok is not None and bool(label_ok.all()))
minutes_1_14 = set(int(x) for x in oos["elapsed"].dropna().unique()) == set(range(1, 15))
blocks_present = set(int(x) for x in oos["block"].dropna().unique()) == {1, 2, 3}
finite_probs = bool(
    np.isfinite(oos["raw_flip_prob"].to_numpy(dtype=float)).all()
    and np.isfinite(oos["flip_prob"].to_numpy(dtype=float)).all()
    and ((oos["flip_prob"] >= 0.0) & (oos["flip_prob"] <= 1.0)).all()
)

raw_agg = float(brier_score_loss(oos["flip"], oos["raw_flip_prob"]))
cal_agg = float(brier_score_loss(oos["flip"], oos["flip_prob"]))
aggregate_brier_ok = cal_agg <= raw_agg + 1e-12

block_rows = []
block_tie_or_improve = 0
for block in (1, 2, 3):
    q = oos[oos["block"] == block]
    if len(q) == 0:
        raise RuntimeError(f"missing untouched block {block}")
    raw = float(brier_score_loss(q["flip"], q["raw_flip_prob"]))
    cal = float(brier_score_loss(q["flip"], q["flip_prob"]))
    ok = cal <= raw + 1e-12
    block_tie_or_improve += int(ok)
    block_rows.append((block, len(q), raw, cal, ok))
blocks_ok = block_tie_or_improve >= MIN_BLOCKS_TIE_OR_IMPROVE

bins = [
    (0.00, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.30),
    (0.30, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 0.70),
    (0.70, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 1.001),
]
reliability = []
for lo, hi in bins:
    q = oos[(oos["flip_prob"] >= lo) & (oos["flip_prob"] < hi)]
    n = len(q)
    if n >= MIN_RELIABILITY_BIN_N:
        actual = float(q["flip"].mean())
        stated = float(q["flip_prob"].mean())
        err = abs(actual - stated)
        reliability.append({
            "lo": lo, "hi": min(hi, 1.0), "n": n,
            "actual": actual, "stated": stated, "abs_error": err,
        })

if not reliability:
    raise RuntimeError("no populated reliability bins")

ece_den = sum(r["n"] for r in reliability)
ece = sum(r["n"] * r["abs_error"] for r in reliability) / ece_den
ece_ok = ece <= ECE_MAX + 1e-12

max_bins = [r for r in reliability if r["n"] >= MIN_MAX_ERROR_BIN_N]
max_bin_error = max((r["abs_error"] for r in max_bins), default=float("nan"))
max_bin_ok = bool(max_bins) and max_bin_error <= MAX_BIN_ERROR + 1e-12

# The freeze said actual flip frequency should generally rise with stated risk.
# A non-decreasing sequence is a transparent, stricter diagnostic and does not
# weaken the frozen criteria if it passes.
actual_seq = [r["actual"] for r in reliability]
reliability_monotonic = all(
    actual_seq[i] <= actual_seq[i + 1] + 1e-12
    for i in range(len(actual_seq) - 1)
)

stay90 = oos[oos["stay_prob"] >= 0.90]
if len(stay90):
    stay90_actual = float((stay90["current_side"] == stay90["final_side"]).mean())
    stay90_stated = float(stay90["stay_prob"].mean())
else:
    stay90_actual = float("nan")
    stay90_stated = float("nan")
stay90_ok = bool(len(stay90)) and stay90_actual >= MIN_STAY90_ACTUAL - 1e-12

hard_integrity_ok = bool(
    settlement_label_consistency and minutes_1_14 and blocks_present and finite_probs
)

passed = bool(
    hard_integrity_ok
    and aggregate_brier_ok
    and blocks_ok
    and reliability_monotonic
    and ece_ok
    and max_bin_ok
    and stay90_ok
)

print("\n=== MACHINE-SCORED FROZEN GATE ===")
print(f"OOS snapshots: {len(oos)} | contracts: {oos['ticker'].nunique()}")
print(f"Aggregate raw Brier: {raw_agg:.6f}")
print(f"Aggregate calibrated Brier: {cal_agg:.6f}")
print(f"Aggregate Brier tie/improve: {aggregate_brier_ok}")
for block, n, raw, cal, ok in block_rows:
    print(f"Block {block} | n={n} | raw={raw:.6f} | calibrated={cal:.6f} | tie/improve={ok}")
print(f"Blocks tie/improve: {block_tie_or_improve}/3 | required>={MIN_BLOCKS_TIE_OR_IMPROVE} | pass={blocks_ok}")

print("\n=== RELIABILITY GATE ===")
for r in reliability:
    print(
        f"Flip {r['lo']:.0%}-{r['hi']:.0%} | n={r['n']} | "
        f"actual={r['actual']:.4f} | stated={r['stated']:.4f} | "
        f"abs_error={r['abs_error']:.4f}"
    )
print(f"Weighted absolute calibration error: {ece:.6f} | limit={ECE_MAX:.3f} | pass={ece_ok}")
print(f"Max bin abs error (n>={MIN_MAX_ERROR_BIN_N}): {max_bin_error:.6f} | limit={MAX_BIN_ERROR:.3f} | pass={max_bin_ok}")
print(f"Actual flip frequency non-decreasing across populated bins: {reliability_monotonic}")

print("\n=== STAY >=90% GATE ===")
print(
    f"n={len(stay90)} | actual stay={stay90_actual:.6f} | "
    f"avg stated stay={stay90_stated:.6f} | required>={MIN_STAY90_ACTUAL:.2f} | pass={stay90_ok}"
)

print("\n=== HARD INTEGRITY ===")
print(f"Settlement-label consistency: {settlement_label_consistency}")
print(f"Minutes 1-14 represented: {minutes_1_14}")
print(f"Untouched blocks 1/2/3 represented: {blocks_present}")
print(f"Finite bounded probabilities: {finite_probs}")
print("Future-data guard / chronological split / historical-only calibration: enforced by frozen source; source completed without exception")

status = "HISTORICAL_GATE_PASS_SHADOW_ONLY" if passed else "HISTORICAL_GATE_FAIL"
print("\n=== DECISION ===")
print(f"FLIP_RISK_GATE_STATUS={status}")
print(f"PASS={passed}")
print("AUTHORITY=SHADOW_NUMERIC_DISPLAY_VALIDATION_ONLY" if passed else "AUTHORITY=KEEP_NUMERIC_FLIP_RISK_HIDDEN")
print("PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False")

raise SystemExit(0 if passed else 2)
