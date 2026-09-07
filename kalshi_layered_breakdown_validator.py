from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path("kalshi_extended_trajectory_full_history_details.csv")

print("=== KALSHI LAYERED BREAKDOWN VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Testing pre-specified layered trajectory rules.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not SRC.exists():
    raise SystemExit(
        "ERROR: kalshi_extended_trajectory_full_history_details.csv not found. "
        "Run kalshi_extended_trajectory_full_history_validator.py first."
    )

df = pd.read_csv(SRC)

if df["correct"].dtype != bool:
    df["correct"] = (
        df["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

df["call_time"] = pd.to_datetime(df["call_time"], utc=True, errors="coerce")

for c in ["drop_4m", "drop_5m", "drop_6m"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df = df.dropna(
    subset=["call_time", "correct", "drop_4m", "drop_5m", "drop_6m"]
).sort_values("call_time").reset_index(drop=True)

print("Calls:", len(df))
print("Baseline accuracy:", f"{df['correct'].mean():.1%}")
print("Total misses:", int((~df["correct"]).sum()))
print()

# Pre-specified layered candidates based on prior separate validation.
candidates = [
    {
        "name": "LAYER_A",
        "early_col": "drop_4m",
        "early_cut": 100,
        "late_col": "drop_6m",
        "late_cut": 85,
    },
    {
        "name": "LAYER_B",
        "early_col": "drop_5m",
        "early_cut": 100,
        "late_col": "drop_6m",
        "late_cut": 85,
    },
    {
        "name": "LAYER_C",
        "early_col": "drop_4m",
        "early_cut": 100,
        "late_col": "drop_6m",
        "late_cut": 100,
    },
]

def evaluate(frame, cfg):
    early = frame[cfg["early_col"]] >= cfg["early_cut"]
    late = frame[cfg["late_col"]] >= cfg["late_cut"]

    # Sequential states:
    # CLEAN = no early or late warning
    # EARLY_ONLY = early warning but no late confirmation
    # LATE_ONLY = no early warning, but late confirmation
    # CONFIRMED = both early and late
    state = np.select(
        [
            early & late,
            early & ~late,
            ~early & late,
        ],
        [
            "CONFIRMED_DANGER",
            "EARLY_WARNING_ONLY",
            "LATE_DANGER_ONLY",
        ],
        default="CLEAN"
    )

    tmp = frame.copy()
    tmp["state"] = state

    total_misses = int((~tmp["correct"]).sum())
    total_good = int(tmp["correct"].sum())

    # Any warning at either stage
    warned = tmp[tmp["state"] != "CLEAN"]
    clean = tmp[tmp["state"] == "CLEAN"]

    caught = int((~warned["correct"]).sum()) if len(warned) else 0
    good_flagged = int(warned["correct"].sum()) if len(warned) else 0

    result = {
        "calls": len(tmp),
        "baseline_accuracy": tmp["correct"].mean(),
        "total_misses": total_misses,
        "warned": len(warned),
        "mistakes_caught": caught,
        "capture": caught / total_misses if total_misses else np.nan,
        "good_flagged": good_flagged,
        "false_warn_rate": good_flagged / total_good if total_good else np.nan,
        "clean_n": len(clean),
        "clean_accuracy": clean["correct"].mean() if len(clean) else np.nan,
    }

    return tmp, result

split = int(len(df) * 0.60)
train = df.iloc[:split].copy()
hold = df.iloc[split:].copy()

print("Chronological split:")
print("Train:", len(train))
print("Holdout:", len(hold))
print("Holdout baseline accuracy:", f"{hold['correct'].mean():.1%}")
print()

summary_rows = []

for cfg in candidates:
    print("===", cfg["name"], "===")
    print(
        f"EARLY: {cfg['early_col']} >= ${cfg['early_cut']} | "
        f"LATE: {cfg['late_col']} >= ${cfg['late_cut']}"
    )

    for scope_name, frame in [
        ("FULL", df),
        ("TRAIN", train),
        ("HOLDOUT", hold),
    ]:
        tmp, r = evaluate(frame, cfg)

        summary_rows.append({
            "candidate": cfg["name"],
            "scope": scope_name,
            **r,
        })

        print(
            scope_name,
            "| warned=", r["warned"],
            "| caught=", f"{r['mistakes_caught']}/{r['total_misses']}",
            "| capture=", f"{r['capture']:.1%}" if pd.notna(r["capture"]) else "NA",
            "| good_flagged=", r["good_flagged"],
            "| false_warn=", f"{r['false_warn_rate']:.1%}" if pd.notna(r["false_warn_rate"]) else "NA",
            "| clean_n=", r["clean_n"],
            "| clean_acc=", f"{r['clean_accuracy']:.1%}" if pd.notna(r["clean_accuracy"]) else "NA",
        )

        if scope_name == "HOLDOUT":
            print("  HOLDOUT STATE BREAKDOWN:")
            for state in [
                "CLEAN",
                "EARLY_WARNING_ONLY",
                "LATE_DANGER_ONLY",
                "CONFIRMED_DANGER",
            ]:
                q = tmp[tmp["state"] == state]
                if len(q):
                    print(
                        "   ",
                        state,
                        "| n=", len(q),
                        "| correct=", int(q["correct"].sum()),
                        "| wrong=", int((~q["correct"]).sum()),
                        "| accuracy=", f"{q['correct'].mean():.1%}",
                    )

    print()

print("=== HOLDOUT CALL DETAILS FOR LAYER_A ===")

layer_a = candidates[0]
hold_a, _ = evaluate(hold, layer_a)

for _, r in hold_a.iterrows():
    print(
        r["ticker"],
        "| state=", r["state"],
        "| correct=", bool(r["correct"]),
        "| call=", r.get("call_side", ""),
        "| winner=", r.get("official_side", ""),
        "| 4m_drop=", f"${float(r['drop_4m']):.2f}",
        "| 6m_drop=", f"${float(r['drop_6m']):.2f}",
    )

summary = pd.DataFrame(summary_rows)
summary.to_csv("kalshi_layered_breakdown_summary.csv", index=False)
hold_a.to_csv("kalshi_layered_breakdown_holdout_details.csv", index=False)

print()
print("=== FILES CREATED ===")
print("kalshi_layered_breakdown_summary.csv")
print("kalshi_layered_breakdown_holdout_details.csv")
print()
print("IMPORTANT:")
print("Research validation only.")
print("No layered rule installed into bot.py.")
print("No scalp logic changed.")
print("Signal-only remains intact.")
print()
print("=== LAYERED BREAKDOWN VALIDATION COMPLETE ===")
