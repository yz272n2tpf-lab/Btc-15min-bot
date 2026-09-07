from pathlib import Path
import pandas as pd
import numpy as np

FWD = Path("kalshi_frozen_forward_only_results.csv")
DETAILS = Path("kalshi_3min_distance_drop_full_history_details.csv")

print("=== FROZEN FORWARD MISS DIAGNOSTIC ===")
print("Purpose: diagnose NEW forward misses without changing frozen rules.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not FWD.exists():
    raise SystemExit("ERROR: kalshi_frozen_forward_only_results.csv not found.")

f = pd.read_csv(FWD)

if "correct" in f.columns and f["correct"].dtype != bool:
    f["correct"] = (
        f["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

numeric_cols = [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "initial_signed_distance",
    "three_min_max_distance_drop",
]

for c in numeric_cols:
    if c in f.columns:
        f[c] = pd.to_numeric(f[c], errors="coerce")

print("Forward qualifying calls:", len(f))
print("Correct:", int(f["correct"].sum()))
print("Wrong:", int((~f["correct"]).sum()))
print("Accuracy:", f"{f['correct'].mean():.1%}")
print()

print("=== FORWARD MISSES ===")
miss = f[~f["correct"]].copy()

if miss.empty:
    print("No forward misses found.")
else:
    for _, r in miss.iterrows():
        print(
            r.get("ticker",""),
            "| call=", r.get("call_side",""),
            "| winner=", r.get("official_side",""),
            "| fair=", (
                f"{float(r['initial_fair']):.1%}"
                if pd.notna(r.get("initial_fair", np.nan)) else "NA"
            ),
            "| min_left=", (
                f"{float(r['initial_remaining_min']):.2f}"
                if pd.notna(r.get("initial_remaining_min", np.nan)) else "NA"
            ),
            "| initial_dist=", (
                f"${float(r['initial_distance']):+.2f}"
                if pd.notna(r.get("initial_distance", np.nan)) else "NA"
            ),
            "| 3m_deterioration=", (
                f"${float(r['three_min_max_distance_drop']):.2f}"
                if pd.notna(r.get("three_min_max_distance_drop", np.nan)) else "NA"
            ),
            "| tier=", r.get("tier",""),
        )

print()
print("=== CORRECT VS WRONG SUMMARY ===")

compare_cols = [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "three_min_max_distance_drop",
]

for c in compare_cols:
    if c not in f.columns:
        continue

    good = f[f["correct"]][c].dropna()
    bad = f[~f["correct"]][c].dropna()

    if len(good):
        print(
            c,
            "| GOOD median=", round(float(good.median()), 4),
            "| GOOD min=", round(float(good.min()), 4),
            "| GOOD max=", round(float(good.max()), 4),
        )
    if len(bad):
        print(
            " " * len(c),
            "| BAD  median=", round(float(bad.median()), 4),
            "| BAD  min=", round(float(bad.min()), 4),
            "| BAD  max=", round(float(bad.max()), 4),
        )

print()
print("=== SIMPLE FORWARD-ONLY WARNING SEARCH ===")
print("Diagnostic only. DO NOT install these thresholds from this small sample.")
print()

rows = []

if "initial_fair" in f.columns:
    for cut in [0.80, 0.82, 0.85, 0.88, 0.90]:
        q = f[f["initial_fair"] >= cut]
        if len(q):
            rows.append({
                "rule": f"initial_fair >= {cut:.2f}",
                "n": len(q),
                "acc": q["correct"].mean(),
            })

if "initial_remaining_min" in f.columns:
    for lo, hi in [(8,9),(9,10),(10,11),(11,12)]:
        q = f[
            (f["initial_remaining_min"] >= lo)
            & (f["initial_remaining_min"] < hi)
        ]
        if len(q):
            rows.append({
                "rule": f"{lo}-{hi} min left",
                "n": len(q),
                "acc": q["correct"].mean(),
            })

if "three_min_max_distance_drop" in f.columns:
    for cut in [50,75,100,125,150]:
        warned = f[f["three_min_max_distance_drop"] >= cut]
        clean = f[f["three_min_max_distance_drop"] < cut]
        rows.append({
            "rule": f"3m deterioration >= ${cut}",
            "n": len(warned),
            "acc": warned["correct"].mean() if len(warned) else np.nan,
            "clean_n": len(clean),
            "clean_acc": clean["correct"].mean() if len(clean) else np.nan,
            "mistakes_caught": int((~warned["correct"]).sum()) if len(warned) else 0,
            "good_flagged": int(warned["correct"].sum()) if len(warned) else 0,
        })

if rows:
    r = pd.DataFrame(rows)
    print(r.to_string(index=False))
    r.to_csv("kalshi_frozen_forward_miss_rule_scan.csv", index=False)

if DETAILS.exists():
    d = pd.read_csv(DETAILS)
    if "correct" in d.columns and d["correct"].dtype != bool:
        d["correct"] = (
            d["correct"].astype(str).str.lower()
            .map({"true": True, "false": False})
        )

    if "ticker" in d.columns and "ticker" in f.columns:
        extra_cols = [c for c in d.columns if c not in f.columns and c != "ticker"]
        merged = f.merge(
            d[["ticker"] + extra_cols],
            on="ticker",
            how="left"
        )

        traj_candidates = [
            c for c in merged.columns
            if any(k in c.lower() for k in [
                "30", "60", "90", "2m", "3m",
                "fair_drop", "distance_drop",
                "ratio", "flip"
            ])
        ]

        print()
        print("=== AVAILABLE TRAJECTORY FIELDS FOR FORWARD MISSES ===")
        print(", ".join(traj_candidates[:40]) if traj_candidates else "No extra trajectory fields found.")

        merged[~merged["correct"]].to_csv(
            "kalshi_frozen_forward_miss_details.csv",
            index=False
        )
        merged.to_csv(
            "kalshi_frozen_forward_all_diagnostic.csv",
            index=False
        )

print()
print("=== FILES CREATED ===")
print("kalshi_frozen_forward_miss_rule_scan.csv")
if DETAILS.exists():
    print("kalshi_frozen_forward_miss_details.csv")
    print("kalshi_frozen_forward_all_diagnostic.csv")
print()
print("IMPORTANT: Diagnosis only. Frozen thresholds remain unchanged.")
print("=== DIAGNOSTIC COMPLETE ===")
