from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path("kalshi_confirmation_failure_audit_details.csv")

print("=== KALSHI CONFIRMATION MATRIX VALIDATOR ===")
print("Purpose: find earliest confirmation checkpoint that catches CLEAN misses with minimal winner loss.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not SRC.exists():
    raise SystemExit("Missing kalshi_confirmation_failure_audit_details.csv")

d = pd.read_csv(SRC)

required = ["ticker","correct","call_side","initial_fair","initial_signed_distance"]
for c in required:
    if c not in d.columns:
        raise SystemExit(f"Missing required column: {c}")

# Normalize booleans safely
if d["correct"].dtype != bool:
    d["correct"] = d["correct"].astype(str).str.lower().map({"true":True,"false":False})

winners = d[d["correct"] == True].copy()
misses = d[d["correct"] == False].copy()

print("CLEAN sample:", len(d))
print("Winners:", len(winners))
print("Misses:", len(misses))
print()

minutes = [2,3,4,5,6]
distance_thresholds = [10,15,20,25,30]
fair_thresholds = [0.00,0.025,0.05,0.075,0.10]

rows = []

for minute in minutes:
    dist_col = f"{minute}m_distance_gain"
    fair_col = f"{minute}m_fair_gain"

    if dist_col not in d.columns or fair_col not in d.columns:
        continue

    for dthr in distance_thresholds:
        # Failure of distance confirmation alone
        warn = pd.to_numeric(d[dist_col], errors="coerce") < dthr
        flagged = d[warn]
        caught = flagged[flagged["correct"] == False]
        good_flagged = flagged[flagged["correct"] == True]
        kept = d[~warn]

        rows.append({
            "minute": minute,
            "distance_threshold": dthr,
            "fair_mode": "NONE",
            "fair_threshold": np.nan,
            "warned": len(flagged),
            "misses_caught": len(caught),
            "total_misses": len(misses),
            "good_flagged": len(good_flagged),
            "kept": len(kept),
            "kept_accuracy": kept["correct"].mean() if len(kept) else np.nan,
            "rule": f"{minute}m distance_gain < +${dthr}"
        })

        # Distance failure PLUS fair not strengthening enough
        for fthr in fair_thresholds:
            fair_vals = pd.to_numeric(d[fair_col], errors="coerce")
            dist_vals = pd.to_numeric(d[dist_col], errors="coerce")

            # warn only when BOTH confirmation dimensions are weak
            warn_both = (dist_vals < dthr) & (fair_vals < fthr)
            flagged = d[warn_both]
            caught = flagged[flagged["correct"] == False]
            good_flagged = flagged[flagged["correct"] == True]
            kept = d[~warn_both]

            rows.append({
                "minute": minute,
                "distance_threshold": dthr,
                "fair_mode": "AND",
                "fair_threshold": fthr,
                "warned": len(flagged),
                "misses_caught": len(caught),
                "total_misses": len(misses),
                "good_flagged": len(good_flagged),
                "kept": len(kept),
                "kept_accuracy": kept["correct"].mean() if len(kept) else np.nan,
                "rule": f"{minute}m dist_gain < +${dthr} AND fair_gain < {fthr:.3f}"
            })

            # warn when EITHER confirmation dimension is weak
            warn_either = (dist_vals < dthr) | (fair_vals < fthr)
            flagged = d[warn_either]
            caught = flagged[flagged["correct"] == False]
            good_flagged = flagged[flagged["correct"] == True]
            kept = d[~warn_either]

            rows.append({
                "minute": minute,
                "distance_threshold": dthr,
                "fair_mode": "OR",
                "fair_threshold": fthr,
                "warned": len(flagged),
                "misses_caught": len(caught),
                "total_misses": len(misses),
                "good_flagged": len(good_flagged),
                "kept": len(kept),
                "kept_accuracy": kept["correct"].mean() if len(kept) else np.nan,
                "rule": f"{minute}m dist_gain < +${dthr} OR fair_gain < {fthr:.3f}"
            })

r = pd.DataFrame(rows)

# Ranking:
# 1) catch all misses
# 2) fewest good winners flagged
# 3) earliest minute
# 4) highest kept accuracy
r["catch_all"] = r["misses_caught"] == r["total_misses"]
r["capture_rate"] = np.where(r["total_misses"] > 0, r["misses_caught"] / r["total_misses"], np.nan)

ranked = r.sort_values(
    ["catch_all","good_flagged","minute","kept_accuracy","warned"],
    ascending=[False,True,True,False,True]
).reset_index(drop=True)

print("=== TOP CANDIDATES ===")
top = ranked.head(30)
print(
    top[
        ["rule","misses_caught","total_misses","good_flagged","warned","kept","kept_accuracy"]
    ].to_string(index=False)
)
print()

print("=== CATCH-ALL CANDIDATES ONLY ===")
catch = ranked[ranked["catch_all"]].copy()
if catch.empty:
    print("No candidate caught every CLEAN miss.")
else:
    print(
        catch.head(40)[
            ["rule","good_flagged","warned","kept","kept_accuracy"]
        ].to_string(index=False)
    )
print()

print("=== EARLIEST BEST CANDIDATE BY MINUTE ===")
for minute in minutes:
    g = ranked[(ranked["minute"] == minute) & ranked["catch_all"]]
    if g.empty:
        print(f"{minute}m | no rule caught all misses")
    else:
        x = g.iloc[0]
        print(
            f"{minute}m | {x['rule']} | good_flagged={int(x['good_flagged'])} "
            f"| warned={int(x['warned'])} | kept={int(x['kept'])} "
            f"| kept_acc={x['kept_accuracy']:.1%}"
        )
print()

# Show what the best few rules do contract-by-contract
best_rules = ranked.head(5)

print("=== BEST RULE FLAG DETAILS ===")
for i, row in best_rules.iterrows():
    minute = int(row["minute"])
    dthr = float(row["distance_threshold"])
    fair_mode = str(row["fair_mode"])
    fthr = row["fair_threshold"]

    dist_col = f"{minute}m_distance_gain"
    fair_col = f"{minute}m_fair_gain"

    dist_vals = pd.to_numeric(d[dist_col], errors="coerce")
    fair_vals = pd.to_numeric(d[fair_col], errors="coerce")

    if fair_mode == "NONE":
        mask = dist_vals < dthr
    elif fair_mode == "AND":
        mask = (dist_vals < dthr) & (fair_vals < float(fthr))
    else:
        mask = (dist_vals < dthr) | (fair_vals < float(fthr))

    flagged = d.loc[mask, ["ticker","correct","call_side","initial_fair",dist_col,fair_col]].copy()

    print()
    print(f"RULE {i+1}: {row['rule']}")
    print(flagged.to_string(index=False) if len(flagged) else "No flagged calls.")

out_csv = Path("kalshi_confirmation_matrix_results.csv")
ranked.to_csv(out_csv, index=False)

print()
print("Saved:", out_csv)
print("=== MATRIX VALIDATION COMPLETE ===")
print("Research only. No rule installed.")
