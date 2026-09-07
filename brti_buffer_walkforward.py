import pandas as pd
from pathlib import Path


# ============================================================
# BRTI BUFFER CHRONOLOGICAL WALK-FORWARD VALIDATION
#
# INPUT:
#   brti_calibration_results.csv
#
# PURPOSE:
#   Validate the BRTI safety buffer on later unseen contracts.
#
# TEST A:
#   Fixed $10 buffer across chronological test folds.
#
# TEST B:
#   On each fold, choose the best buffer using TRAINING DATA ONLY,
#   then evaluate that chosen buffer on the next unseen block.
#
# This avoids selecting a buffer using the same contracts
# we later claim as validation.
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

df = pd.read_csv(INPUT).copy()

required = [
    "target_brti",
    "final_brti",
    "target_cb_hl2",
    "final_cb_hl2",
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise SystemExit(
        f"Missing required columns: {missing}"
    )

# The calibration audit originally sorted contracts chronologically
# before writing this CSV. Preserve that row order here.
df = df.reset_index(drop=True)

candidate_buffers = [
    0.0,
    5.0,
    7.5,
    10.0,
    12.5,
    15.5,
    20.0,
    25.0,
    30.0,
]

fixed_buffer = 10.0


def prepare_with_training_bias(train, test):
    # Estimate Coinbase-HL2 minus BRTI bias using TRAINING DATA ONLY.
    train_errors = pd.concat(
        [
            train["target_cb_hl2"] - train["target_brti"],
            train["final_cb_hl2"] - train["final_brti"],
        ],
        ignore_index=True,
    )

    bias = train_errors.mean()

    out = test.copy()

    out["adjusted_final_proxy"] = (
        out["final_cb_hl2"] - bias
    )

    out["proxy_gap"] = (
        out["adjusted_final_proxy"]
        - out["target_brti"]
    )

    out["actual_up"] = (
        out["final_brti"]
        >= out["target_brti"]
    )

    out["proxy_direction"] = (
        out["proxy_gap"] >= 0
    )

    out["direction_correct"] = (
        out["proxy_direction"]
        == out["actual_up"]
    )

    return out, bias


def evaluate_buffer(prepared, buffer):
    actionable = (
        prepared["proxy_gap"].abs() > buffer
    )

    selected = prepared[actionable]

    if selected.empty:
        return {
            "actionable": 0,
            "correct": 0,
            "wrong": 0,
            "accuracy": None,
            "coverage": 0.0,
        }

    correct = int(
        selected["direction_correct"].sum()
    )

    total = len(selected)
    wrong = total - correct

    return {
        "actionable": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": correct / total,
        "coverage": total / len(prepared),
    }


def choose_buffer_on_train(train):
    # Training-only bias.
    train_prepared, _ = prepare_with_training_bias(
        train,
        train,
    )

    rows = []

    for buffer in candidate_buffers:
        stats = evaluate_buffer(
            train_prepared,
            buffer,
        )

        if stats["actionable"] == 0:
            continue

        rows.append(
            {
                "buffer": buffer,
                **stats,
            }
        )

    results = pd.DataFrame(rows)

    if results.empty:
        return 10.0

    # Quality-first:
    # 1) highest accuracy
    # 2) then highest coverage
    # 3) then smallest buffer
    best = (
        results.sort_values(
            ["accuracy", "coverage", "buffer"],
            ascending=[False, False, True],
        )
        .iloc[0]
    )

    return float(best["buffer"])


print("=== BRTI BUFFER WALK-FORWARD VALIDATION ===")
print("Contracts:", len(df))
print("Fixed candidate buffer:", f"${fixed_buffer:.1f}")

# Expanding-window chronological folds.
folds = [
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]

fixed_totals = {
    "correct": 0,
    "actionable": 0,
    "test": 0,
    "wrong": 0,
}

dynamic_totals = {
    "correct": 0,
    "actionable": 0,
    "test": 0,
    "wrong": 0,
}

print()
print("=== FIXED $10 BUFFER ON UNSEEN FOLDS ===")

for train_end_frac, test_end_frac in folds:
    train_end = int(
        len(df) * train_end_frac
    )

    test_end = int(
        len(df) * test_end_frac
    )

    train = df.iloc[:train_end].copy()
    test = df.iloc[train_end:test_end].copy()

    prepared, bias = prepare_with_training_bias(
        train,
        test,
    )

    stats = evaluate_buffer(
        prepared,
        fixed_buffer,
    )

    fixed_totals["correct"] += stats["correct"]
    fixed_totals["actionable"] += stats["actionable"]
    fixed_totals["wrong"] += stats["wrong"]
    fixed_totals["test"] += len(test)

    acc_text = (
        f"{stats['accuracy']:.3f}"
        if stats["accuracy"] is not None
        else "N/A"
    )

    print(
        f"{int(train_end_frac*100)}->{int(test_end_frac*100)}% | "
        f"train {len(train)} | test {len(test)} | "
        f"train-only bias ${bias:+.2f} | "
        f"actionable {stats['actionable']}/{len(test)} "
        f"({stats['coverage']:.1%}) | "
        f"accuracy {acc_text} | "
        f"wrong {stats['wrong']}"
    )


print()
print("FIXED $10 WALK-FORWARD TOTALS:")

if fixed_totals["actionable"] > 0:
    fixed_acc = (
        fixed_totals["correct"]
        / fixed_totals["actionable"]
    )
else:
    fixed_acc = 0.0

fixed_cov = (
    fixed_totals["actionable"]
    / fixed_totals["test"]
    if fixed_totals["test"]
    else 0.0
)

print(
    f"{fixed_totals['correct']}/"
    f"{fixed_totals['actionable']} = "
    f"{fixed_acc:.3f}"
)

print(
    "Wrong:",
    fixed_totals["wrong"],
)

print(
    "Coverage:",
    f"{fixed_cov:.1%}",
)


print()
print("=== TRAIN-SELECTED BUFFER -> UNSEEN FOLD ===")

chosen_buffers = []

for train_end_frac, test_end_frac in folds:
    train_end = int(
        len(df) * train_end_frac
    )

    test_end = int(
        len(df) * test_end_frac
    )

    train = df.iloc[:train_end].copy()
    test = df.iloc[train_end:test_end].copy()

    chosen = choose_buffer_on_train(train)
    chosen_buffers.append(chosen)

    prepared, bias = prepare_with_training_bias(
        train,
        test,
    )

    stats = evaluate_buffer(
        prepared,
        chosen,
    )

    dynamic_totals["correct"] += stats["correct"]
    dynamic_totals["actionable"] += stats["actionable"]
    dynamic_totals["wrong"] += stats["wrong"]
    dynamic_totals["test"] += len(test)

    acc_text = (
        f"{stats['accuracy']:.3f}"
        if stats["accuracy"] is not None
        else "N/A"
    )

    print(
        f"{int(train_end_frac*100)}->{int(test_end_frac*100)}% | "
        f"chosen on train: ${chosen:.1f} | "
        f"actionable {stats['actionable']}/{len(test)} "
        f"({stats['coverage']:.1%}) | "
        f"accuracy {acc_text} | "
        f"wrong {stats['wrong']}"
    )


print()
print("DYNAMIC WALK-FORWARD TOTALS:")

if dynamic_totals["actionable"] > 0:
    dynamic_acc = (
        dynamic_totals["correct"]
        / dynamic_totals["actionable"]
    )
else:
    dynamic_acc = 0.0

dynamic_cov = (
    dynamic_totals["actionable"]
    / dynamic_totals["test"]
    if dynamic_totals["test"]
    else 0.0
)

print(
    f"{dynamic_totals['correct']}/"
    f"{dynamic_totals['actionable']} = "
    f"{dynamic_acc:.3f}"
)

print(
    "Wrong:",
    dynamic_totals["wrong"],
)

print(
    "Coverage:",
    f"{dynamic_cov:.1%}",
)

print(
    "Buffers chosen by training folds:",
    chosen_buffers,
)


print()
print("=== FINAL VERDICT GUIDE ===")

if (
    fixed_totals["wrong"] == 0
    and fixed_acc >= 0.95
):
    print(
        "FIXED $10 BUFFER: PASSED this chronological "
        "walk-forward test with zero observed wrong-direction "
        "actionable contracts."
    )
else:
    print(
        "FIXED $10 BUFFER: NOT perfect out-of-sample. "
        "Review failures before integration."
    )

if dynamic_totals["wrong"] == 0:
    print(
        "TRAIN-SELECTED BUFFER: zero wrong-direction "
        "actionable contracts across unseen folds."
    )
else:
    print(
        "TRAIN-SELECTED BUFFER: some unseen failures remain."
    )

print()
print(
    "This validates only the Coinbase/BRTI target safety gate."
)

print(
    "It does NOT replace the separate validated 15-minute model."
)

print(
    "NO orders placed."
)

print(
    "NO changes to bot.py."
)
