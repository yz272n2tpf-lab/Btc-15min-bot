import pandas as pd
from pathlib import Path

INPUT = Path("brti_calibration_results.csv")
FIXED_BUFFER = 10.0

if not INPUT.exists():
    raise SystemExit("Missing brti_calibration_results.csv")

df = pd.read_csv(INPUT).copy().reset_index(drop=True)

required = ["target_brti", "final_brti", "target_cb_hl2", "final_cb_hl2"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

folds = [
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]

def prepare(train, test):
    errors = pd.concat(
        [
            train["target_cb_hl2"] - train["target_brti"],
            train["final_cb_hl2"] - train["final_brti"],
        ],
        ignore_index=True,
    )
    bias = errors.mean()

    x = test.copy()
    x["estimated_brti_final"] = x["final_cb_hl2"] - bias
    x["adjusted_gap"] = x["estimated_brti_final"] - x["target_brti"]
    x["actual_gap"] = x["final_brti"] - x["target_brti"]
    x["proxy_up"] = x["adjusted_gap"] >= 0
    x["actual_up"] = x["actual_gap"] >= 0
    x["correct"] = x["proxy_up"] == x["actual_up"]
    x["abs_adjusted_gap"] = x["adjusted_gap"].abs()
    return x, bias

failures = []

print("=== BRTI $10 WALK-FORWARD FAILURE AUDIT ===")
print("Purpose: isolate every unseen wrong-direction case.")
print()

for train_frac, test_frac in folds:
    train_end = int(len(df) * train_frac)
    test_end = int(len(df) * test_frac)

    train = df.iloc[:train_end].copy()
    test = df.iloc[train_end:test_end].copy()
    prepared, bias = prepare(train, test)

    actionable = prepared[prepared["abs_adjusted_gap"] > FIXED_BUFFER]
    wrong = actionable[~actionable["correct"]].copy()

    print(
        f"Fold {int(train_frac*100)}->{int(test_frac*100)}% | "
        f"bias ${bias:+.2f} | actionable {len(actionable)} | wrong {len(wrong)}"
    )

    for idx, row in wrong.iterrows():
        record = {
            "fold": f"{int(train_frac*100)}->{int(test_frac*100)}%",
            "row_index": idx,
            "training_bias": bias,
            "target_brti": row["target_brti"],
            "final_brti": row["final_brti"],
            "target_cb_hl2": row["target_cb_hl2"],
            "final_cb_hl2": row["final_cb_hl2"],
            "estimated_brti_final": row["estimated_brti_final"],
            "adjusted_gap": row["adjusted_gap"],
            "actual_gap": row["actual_gap"],
            "distance_outside_10": row["abs_adjusted_gap"] - FIXED_BUFFER,
        }

        # Preserve useful identifying/time columns if present.
        for c in [
            "ticker", "event_ticker", "close_time", "expiration_time",
            "created_time", "open_time", "date", "datetime"
        ]:
            if c in row.index:
                record[c] = row[c]

        failures.append(record)

print()
print("=== FAILURE DETAILS ===")

if not failures:
    print("No failures found.")
else:
    fdf = pd.DataFrame(failures)

    for n, row in fdf.iterrows():
        print(f"\nFAILURE #{n+1}")
        print("Fold:", row["fold"])
        print("Original row index:", row["row_index"])

        for c in [
            "ticker", "event_ticker", "close_time", "expiration_time",
            "created_time", "open_time", "date", "datetime"
        ]:
            if c in row.index and pd.notna(row[c]):
                print(f"{c}: {row[c]}")

        print(f"Training-only bias: ${row['training_bias']:+.2f}")
        print(f"Kalshi BRTI target: ${row['target_brti']:,.2f}")
        print(f"Actual BRTI final: ${row['final_brti']:,.2f}")
        print(f"Actual final-vs-target gap: ${row['actual_gap']:+.2f}")
        print(f"Coinbase HL2 final: ${row['final_cb_hl2']:,.2f}")
        print(f"Estimated BRTI final: ${row['estimated_brti_final']:,.2f}")
        print(f"Adjusted proxy-vs-target gap: ${row['adjusted_gap']:+.2f}")
        print(
            "Distance beyond $10 gate:",
            f"${row['distance_outside_10']:+.2f}"
        )

    fdf.to_csv("brti_buffer_failures.csv", index=False)
    print("\nSaved: brti_buffer_failures.csv")

print()
print("=== BUFFER SENSITIVITY ON THE FAILURE(S) ===")

if failures:
    fdf = pd.DataFrame(failures)
    for buffer in [10.0, 10.5, 11.0, 12.0, 12.5, 15.5]:
        survivors = (fdf["adjusted_gap"].abs() > buffer).sum()
        print(
            f"Buffer ${buffer:4.1f} | "
            f"wrong failures still actionable: {survivors}/{len(fdf)}"
        )

print()
print("NO orders placed.")
print("NO changes to bot.py.")
