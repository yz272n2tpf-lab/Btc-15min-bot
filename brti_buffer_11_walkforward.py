import pandas as pd
from pathlib import Path

INPUT = Path("brti_calibration_results.csv")
FIXED_BUFFER = 11.0

if not INPUT.exists():
    raise SystemExit(
        "Missing brti_calibration_results.csv. "
        "Run brti_calibration_audit.py first."
    )

df = pd.read_csv(INPUT).copy().reset_index(drop=True)

required = [
    "target_brti",
    "final_brti",
    "target_cb_hl2",
    "final_cb_hl2",
]

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
    train_errors = pd.concat(
        [
            train["target_cb_hl2"] - train["target_brti"],
            train["final_cb_hl2"] - train["final_brti"],
        ],
        ignore_index=True,
    )

    bias = train_errors.mean()

    out = test.copy()

    out["estimated_brti_final"] = (
        out["final_cb_hl2"] - bias
    )

    out["adjusted_gap"] = (
        out["estimated_brti_final"]
        - out["target_brti"]
    )

    out["actual_gap"] = (
        out["final_brti"]
        - out["target_brti"]
    )

    out["proxy_up"] = (
        out["adjusted_gap"] >= 0
    )

    out["actual_up"] = (
        out["actual_gap"] >= 0
    )

    out["correct"] = (
        out["proxy_up"] == out["actual_up"]
    )

    return out, bias


totals = {
    "test": 0,
    "actionable": 0,
    "correct": 0,
    "wrong": 0,
}

print("=== FIXED $11 BRTI WALK-FORWARD VALIDATION ===")
print("Contracts:", len(df))
print("Buffer:", f"${FIXED_BUFFER:.2f}")
print()

for train_frac, test_frac in folds:
    train_end = int(len(df) * train_frac)
    test_end = int(len(df) * test_frac)

    train = df.iloc[:train_end].copy()
    test = df.iloc[train_end:test_end].copy()

    prepared, bias = prepare(train, test)

    actionable = prepared[
        prepared["adjusted_gap"].abs() > FIXED_BUFFER
    ].copy()

    correct = int(actionable["correct"].sum())
    total = len(actionable)
    wrong = total - correct

    accuracy = (
        correct / total
        if total
        else 0.0
    )

    coverage = (
        total / len(test)
        if len(test)
        else 0.0
    )

    totals["test"] += len(test)
    totals["actionable"] += total
    totals["correct"] += correct
    totals["wrong"] += wrong

    print(
        f"{int(train_frac*100)}->{int(test_frac*100)}% | "
        f"train {len(train)} | test {len(test)} | "
        f"train-only bias ${bias:+.2f} | "
        f"actionable {total}/{len(test)} "
        f"({coverage:.1%}) | "
        f"accuracy {accuracy:.3f} | "
        f"wrong {wrong}"
    )

    if wrong:
        print("  Failure details:")
        bad = actionable[~actionable["correct"]]

        for idx, row in bad.iterrows():
            print(
                f"    row {idx} | "
                f"target ${row['target_brti']:,.2f} | "
                f"actual final ${row['final_brti']:,.2f} | "
                f"actual gap ${row['actual_gap']:+.2f} | "
                f"adjusted proxy gap ${row['adjusted_gap']:+.2f}"
            )


print()
print("=== FIXED $11 WALK-FORWARD TOTALS ===")

accuracy = (
    totals["correct"] / totals["actionable"]
    if totals["actionable"]
    else 0.0
)

coverage = (
    totals["actionable"] / totals["test"]
    if totals["test"]
    else 0.0
)

print(
    f"{totals['correct']}/{totals['actionable']} = "
    f"{accuracy:.3f}"
)

print("Wrong:", totals["wrong"])
print("Coverage:", f"{coverage:.1%}")

print()
print("=== COMPARISON TO PRIOR $10 RESULT ===")
print("Prior $10 result: 307/308 = 0.997 | wrong 1 | coverage 92.8%")
print(
    "Use the $11 result above to decide whether the extra "
    "$1 safety margin removes the miss without meaningfully "
    "reducing coverage."
)

print()
print("NO orders placed.")
print("NO changes to bot.py.")
