import pandas as pd
from pathlib import Path

INPUT = Path("brti_calibration_results.csv")

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

buffers = [10.5, 11.0, 11.5, 12.0, 12.5]

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
    out["estimated_brti_final"] = out["final_cb_hl2"] - bias
    out["adjusted_gap"] = out["estimated_brti_final"] - out["target_brti"]
    out["actual_gap"] = out["final_brti"] - out["target_brti"]
    out["proxy_up"] = out["adjusted_gap"] >= 0
    out["actual_up"] = out["actual_gap"] >= 0
    out["correct"] = out["proxy_up"] == out["actual_up"]

    return out, bias

totals = {
    b: {"test": 0, "actionable": 0, "correct": 0, "wrong": 0}
    for b in buffers
}

print("=== BRTI BUFFER NEIGHBORHOOD WALK-FORWARD ===")
print("Contracts:", len(df))
print("Buffers tested:", buffers)
print()

for train_frac, test_frac in folds:
    train_end = int(len(df) * train_frac)
    test_end = int(len(df) * test_frac)

    train = df.iloc[:train_end].copy()
    test = df.iloc[train_end:test_end].copy()
    prepared, bias = prepare(train, test)

    print(
        f"Fold {int(train_frac*100)}->{int(test_frac*100)}% | "
        f"train {len(train)} | test {len(test)} | "
        f"train-only bias ${bias:+.2f}"
    )

    for buffer in buffers:
        actionable = prepared[prepared["adjusted_gap"].abs() > buffer].copy()

        total = len(actionable)
        correct = int(actionable["correct"].sum())
        wrong = total - correct
        accuracy = correct / total if total else 0.0
        coverage = total / len(test) if len(test) else 0.0

        totals[buffer]["test"] += len(test)
        totals[buffer]["actionable"] += total
        totals[buffer]["correct"] += correct
        totals[buffer]["wrong"] += wrong

        print(
            f"  ${buffer:4.1f} | "
            f"{total}/{len(test)} actionable "
            f"({coverage:.1%}) | "
            f"accuracy {accuracy:.3f} | "
            f"wrong {wrong}"
        )

    print()

print("=== WALK-FORWARD TOTALS BY BUFFER ===")

summary = []

for buffer in buffers:
    t = totals[buffer]
    accuracy = t["correct"] / t["actionable"] if t["actionable"] else 0.0
    coverage = t["actionable"] / t["test"] if t["test"] else 0.0

    print(
        f"${buffer:4.1f} | "
        f"{t['correct']}/{t['actionable']} = "
        f"{accuracy:.3f} | "
        f"wrong {t['wrong']} | "
        f"coverage {coverage:.1%}"
    )

    summary.append(
        {
            "buffer": buffer,
            "correct": t["correct"],
            "actionable": t["actionable"],
            "accuracy": accuracy,
            "wrong": t["wrong"],
            "coverage": coverage,
        }
    )

res = pd.DataFrame(summary)

print()
print("=== STABILITY VERDICT ===")

zero_wrong = res[res["wrong"] == 0].copy()

if zero_wrong.empty:
    print("No tested buffer achieved zero wrong cases.")
else:
    best_zero_wrong = zero_wrong.sort_values(
        ["coverage", "buffer"],
        ascending=[False, True],
    ).iloc[0]

    print("Zero-wrong buffers:", list(zero_wrong["buffer"]))
    print(
        "Highest-coverage zero-wrong buffer:",
        f"${best_zero_wrong['buffer']:.1f}",
    )
    print("Coverage:", f"{best_zero_wrong['coverage']:.1%}")
    print("Accuracy:", f"{best_zero_wrong['accuracy']:.3f}")

print()
print(
    "Interpretation: if multiple neighboring buffers produce zero wrong "
    "cases, the threshold is stable rather than a single lucky cutoff."
)
print()
print("NO orders placed.")
print("NO changes to bot.py.")
