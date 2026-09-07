import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# BRTI BUFFER + 15-MIN SIGNAL AUDIT
#
# INPUT:
#   brti_calibration_results.csv
#
# PURPOSE:
#   Use the calibration results already created to test
#   whether BRTI uncertainty buffers improve safety around
#   near-target contracts.
#
# CALIBRATION FROM PRIOR AUDIT:
#   Best proxy: HL2
#   Estimated Coinbase minus BRTI bias: about -$3.47
#   90% mismatch buffer: about $12.46
#   95% mismatch buffer: about $15.45
#
# TESTED DECISION ZONES:
#   0   = no buffer
#   10
#   12.5
#   15.5
#   20
#   25
#   30 dollars
#
# A contract is "actionable" only if the adjusted Coinbase
# final proxy is outside the Kalshi target by more than the
# selected buffer.
#
# NO ORDERS.
# NO CHANGES TO bot.py.
# ============================================================


INPUT = Path("brti_calibration_results.csv")

if not INPUT.exists():
    raise SystemExit(
        "Missing brti_calibration_results.csv. "
        "Run brti_calibration_audit.py first."
    )

df = pd.read_csv(INPUT)

required = [
    "target_brti",
    "final_brti",
    "final_cb_hl2",
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise SystemExit(
        f"Missing required columns: {missing}"
    )


# Estimated Coinbase minus BRTI bias from prior audit.
# Recompute directly from this CSV so the test is self-contained.
target_bias = (
    df["target_cb_hl2"] - df["target_brti"]
).mean()

final_bias = (
    df["final_cb_hl2"] - df["final_brti"]
).mean()

combined_bias = pd.concat(
    [
        df["target_cb_hl2"] - df["target_brti"],
        df["final_cb_hl2"] - df["final_brti"],
    ],
    ignore_index=True,
).mean()

all_abs_errors = pd.concat(
    [
        (df["target_cb_hl2"] - df["target_brti"]).abs(),
        (df["final_cb_hl2"] - df["final_brti"]).abs(),
    ],
    ignore_index=True,
)

p90 = all_abs_errors.quantile(0.90)
p95 = all_abs_errors.quantile(0.95)


# Translate Coinbase HL2 toward estimated BRTI.
df["adjusted_final_proxy"] = (
    df["final_cb_hl2"] - combined_bias
)

df["actual_up"] = (
    df["final_brti"] >= df["target_brti"]
)

df["proxy_gap"] = (
    df["adjusted_final_proxy"] - df["target_brti"]
)

df["actual_gap"] = (
    df["final_brti"] - df["target_brti"]
)

df["proxy_direction"] = (
    df["proxy_gap"] >= 0
)

df["direction_correct"] = (
    df["proxy_direction"] == df["actual_up"]
)


print("=== BRTI BUFFER + 15-MIN SIGNAL AUDIT ===")
print("Contracts:", len(df))
print(
    "Recomputed combined Coinbase-HL2 minus BRTI bias:",
    f"${combined_bias:+.2f}",
)
print(
    "90% mismatch buffer:",
    f"${p90:.2f}",
)
print(
    "95% mismatch buffer:",
    f"${p95:.2f}",
)

print()
print("=== BASELINE WITHOUT BUFFER ===")

baseline_acc = df["direction_correct"].mean()

print(
    "All-contract direction agreement:",
    f"{baseline_acc:.3f}",
)


buffers = [
    0.0,
    10.0,
    12.5,
    15.5,
    20.0,
    25.0,
    30.0,
]

results = []

print()
print("=== BUFFER STRESS TEST ===")

for buffer in buffers:
    actionable = (
        df["proxy_gap"].abs() > buffer
    )

    selected = df[actionable].copy()

    if selected.empty:
        continue

    acc = (
        selected["direction_correct"].mean()
    )

    coverage = (
        len(selected) / len(df)
    )

    up_count = int(
        (selected["proxy_direction"] == True).sum()
    )

    down_count = int(
        (selected["proxy_direction"] == False).sum()
    )

    wrong = int(
        (~selected["direction_correct"]).sum()
    )

    print(
        f"BUFFER ${buffer:>4.1f} | "
        f"{len(selected)}/{len(df)} actionable "
        f"({coverage:.1%}) | "
        f"accuracy {acc:.3f} | "
        f"wrong {wrong} | "
        f"UP {up_count} | DOWN {down_count}"
    )

    results.append(
        {
            "buffer": buffer,
            "actionable": len(selected),
            "coverage": coverage,
            "accuracy": acc,
            "wrong": wrong,
            "up": up_count,
            "down": down_count,
        }
    )


print()
print("=== ERROR SURVIVAL BY BUFFER ===")

errors = df[
    ~df["direction_correct"]
].copy()

print(
    "Baseline wrong-direction contracts:",
    len(errors),
)

for buffer in buffers:
    surviving_errors = errors[
        errors["proxy_gap"].abs() > buffer
    ]

    print(
        f"BUFFER ${buffer:>4.1f} | "
        f"wrong contracts still actionable: "
        f"{len(surviving_errors)}"
    )


print()
print("=== NEAR-TARGET DANGER PROFILE ===")

for zone in [10, 15, 20, 30, 50]:
    subset = df[
        df["actual_gap"].abs() <= zone
    ]

    if subset.empty:
        continue

    acc = subset[
        "direction_correct"
    ].mean()

    print(
        f"Actual BRTI final within ${zone}: "
        f"{len(subset)} contracts | "
        f"proxy agreement {acc:.3f}"
    )


print()
print("=== BUFFER QUALITY SCORE ===")

res = pd.DataFrame(results)

if not res.empty:
    # Simple quality-first score:
    # prioritize accuracy, then preserve coverage.
    res["quality_score"] = (
        res["accuracy"] * 0.80
        + res["coverage"] * 0.20
    )

    best = res.sort_values(
        ["accuracy", "coverage"],
        ascending=[False, False],
    ).iloc[0]

    print(
        "Best accuracy-first buffer:",
        f"${best['buffer']:.1f}",
    )

    print(
        "Accuracy:",
        f"{best['accuracy']:.3f}",
    )

    print(
        "Coverage:",
        f"{best['coverage']:.1%}",
    )

    # Also highlight p90/p95 calibrated candidates.
    closest_p90 = res.iloc[
        (res["buffer"] - p90).abs().argmin()
    ]

    closest_p95 = res.iloc[
        (res["buffer"] - p95).abs().argmin()
    ]

    print()
    print("Closest tested buffer to calibrated 90%:")
    print(
        f"${closest_p90['buffer']:.1f} | "
        f"accuracy {closest_p90['accuracy']:.3f} | "
        f"coverage {closest_p90['coverage']:.1%}"
    )

    print("Closest tested buffer to calibrated 95%:")
    print(
        f"${closest_p95['buffer']:.1f} | "
        f"accuracy {closest_p95['accuracy']:.3f} | "
        f"coverage {closest_p95['coverage']:.1%}"
    )


print()
print("=== LIVE-RULE INTERPRETATION ===")

print(
    "This audit does NOT replace the validated 15-min model."
)

print(
    "It only tests a Kalshi-target safety gate:"
)

print(
    "If adjusted BTC/BRTI proxy is too close to the target, "
    "the contract should remain WAIT even if direction looks favorable."
)

print(
    "If the model later reaches strict EARLY_LOCK while the "
    "BRTI-adjusted gap is outside the chosen buffer, both layers agree."
)

print()
print("NO orders placed.")
print("NO changes to bot.py.")

res.to_csv(
    "brti_buffer_signal_results.csv",
    index=False,
)

print(
    "Saved:",
    "brti_buffer_signal_results.csv",
)
