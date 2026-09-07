from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path("kalshi_3min_distance_drop_full_history_details.csv")

print("=== KALSHI SAFE / WEAKENING / DANGER TIER VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not SRC.exists():
    raise SystemExit(
        "ERROR: kalshi_3min_distance_drop_full_history_details.csv not found. "
        "Run kalshi_3min_distance_drop_full_history_validator.py first."
    )

df = pd.read_csv(SRC)

df["call_time"] = pd.to_datetime(df["call_time"], utc=True, errors="coerce")

for c in [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "initial_signed_distance",
    "three_min_max_distance_drop",
]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

if df["correct"].dtype != bool:
    df["correct"] = (
        df["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

df = df.dropna(
    subset=["ticker","call_time","correct","three_min_max_distance_drop"]
).sort_values("call_time").reset_index(drop=True)

print("Calls available:", len(df))
print("Overall accuracy:", f"{df['correct'].mean():.1%}")
print()

def assign_tier(drop, safe_cut=100, danger_cut=150):
    if drop < safe_cut:
        return "SAFE"
    if drop < danger_cut:
        return "WEAKENING"
    return "DANGER"

df["tier_100_150"] = df["three_min_max_distance_drop"].apply(
    lambda x: assign_tier(x, 100, 150)
)

def tier_report(data, tier_col, title):
    print(f"=== {title} ===")
    for tier in ["SAFE","WEAKENING","DANGER"]:
        q = data[data[tier_col] == tier]
        if q.empty:
            print(tier, "| n=0")
            continue

        correct = int(q["correct"].sum())
        wrong = len(q) - correct

        print(
            tier,
            "| n=", len(q),
            "| correct=", correct,
            "| wrong=", wrong,
            "| accuracy=", f"{q['correct'].mean():.1%}",
            "| avg_drop=", f"${q['three_min_max_distance_drop'].mean():.2f}",
            "| median_drop=", f"${q['three_min_max_distance_drop'].median():.2f}",
        )
    print()

tier_report(df, "tier_100_150", "FULL HISTORY: CURRENT 100 / 150 TIERS")

split = int(len(df) * 0.60)
train = df.iloc[:split].copy()
hold = df.iloc[split:].copy()

print("Chronological split:")
print("Training calls:", len(train))
print("Holdout calls:", len(hold))
print()

tier_report(train, "tier_100_150", "TRAINING 60%: CURRENT 100 / 150 TIERS")
tier_report(hold, "tier_100_150", "HOLDOUT 40%: CURRENT 100 / 150 TIERS")

print("=== BOUNDARY SEARCH ===")

rows = []

safe_cuts = [50, 75, 90, 100, 110, 125]
danger_cuts = [125, 140, 150, 160, 175, 200]

for safe_cut in safe_cuts:
    for danger_cut in danger_cuts:
        if danger_cut <= safe_cut:
            continue

        tier_col = f"tier_{safe_cut}_{danger_cut}"
        df[tier_col] = df["three_min_max_distance_drop"].apply(
            lambda x: assign_tier(x, safe_cut, danger_cut)
        )

        train[tier_col] = train["three_min_max_distance_drop"].apply(
            lambda x: assign_tier(x, safe_cut, danger_cut)
        )

        hold[tier_col] = hold["three_min_max_distance_drop"].apply(
            lambda x: assign_tier(x, safe_cut, danger_cut)
        )

        for scope_name, data in [
            ("FULL", df),
            ("TRAIN", train),
            ("HOLDOUT", hold),
        ]:
            safe = data[data[tier_col] == "SAFE"]
            weak = data[data[tier_col] == "WEAKENING"]
            danger = data[data[tier_col] == "DANGER"]

            rows.append({
                "scope": scope_name,
                "safe_cut": safe_cut,
                "danger_cut": danger_cut,
                "safe_n": len(safe),
                "safe_accuracy": safe["correct"].mean() if len(safe) else np.nan,
                "weak_n": len(weak),
                "weak_accuracy": weak["correct"].mean() if len(weak) else np.nan,
                "danger_n": len(danger),
                "danger_accuracy": danger["correct"].mean() if len(danger) else np.nan,
                "danger_wrong_rate": (
                    1.0 - danger["correct"].mean()
                    if len(danger) else np.nan
                ),
            })

res = pd.DataFrame(rows)

# Rank only holdout configs. Favor:
# high SAFE accuracy, low DANGER accuracy, and enough samples in both.
h = res[res["scope"] == "HOLDOUT"].copy()

h["score"] = (
    h["safe_accuracy"].fillna(0) * 100
    + h["danger_wrong_rate"].fillna(0) * 80
    + np.minimum(h["safe_n"], 20) * 0.5
    + np.minimum(h["danger_n"], 5) * 1.0
)

h = h.sort_values(
    ["score","safe_accuracy","danger_wrong_rate","safe_n"],
    ascending=[False, False, False, False]
).reset_index(drop=True)

print("Top holdout boundary combinations:")
for _, r in h.head(12).iterrows():
    print(
        f"SAFE < ${int(r['safe_cut'])} | DANGER >= ${int(r['danger_cut'])}",
        "| safe_n=", int(r["safe_n"]),
        "| safe_acc=", (
            f"{r['safe_accuracy']:.1%}"
            if pd.notna(r["safe_accuracy"]) else "N/A"
        ),
        "| weak_n=", int(r["weak_n"]),
        "| weak_acc=", (
            f"{r['weak_accuracy']:.1%}"
            if pd.notna(r["weak_accuracy"]) else "N/A"
        ),
        "| danger_n=", int(r["danger_n"]),
        "| danger_acc=", (
            f"{r['danger_accuracy']:.1%}"
            if pd.notna(r["danger_accuracy"]) else "N/A"
        ),
    )

print()
print("=== CURRENT 100 / 150 HOLDOUT DETAILS ===")

for _, r in hold.iterrows():
    print(
        r["ticker"],
        "| tier=", r["tier_100_150"],
        "| correct=", bool(r["correct"]),
        "| call=", r["call_side"],
        "| winner=", r["official_side"],
        "| initial fair=", f"{r['initial_fair']:.1%}",
        "| initial dist=", f"${r['initial_distance']:+.2f}",
        "| 3m deterioration=", f"${r['three_min_max_distance_drop']:.2f}",
    )

df.to_csv(
    "kalshi_safe_weakening_danger_full_details.csv",
    index=False
)

res.to_csv(
    "kalshi_safe_weakening_danger_boundary_results.csv",
    index=False
)

h.to_csv(
    "kalshi_safe_weakening_danger_holdout_ranked.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_safe_weakening_danger_full_details.csv")
print("kalshi_safe_weakening_danger_boundary_results.csv")
print("kalshi_safe_weakening_danger_holdout_ranked.csv")
print()
print("=== IMPORTANT ===")
print("Research validation only.")
print("No tier logic installed into bot.py.")
print("No scalp logic changed.")
print("Signal-only remains intact.")
print()
print("=== TIER VALIDATION COMPLETE ===")
