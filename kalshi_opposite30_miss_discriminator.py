from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path("kalshi_flow_first_baseline_calls_with_warnings.csv")

print("=== KALSHI OPPOSITE-30 MISS DISCRIMINATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not SRC.exists():
    raise SystemExit(
        "ERROR: kalshi_flow_first_baseline_calls_with_warnings.csv not found. "
        "Run kalshi_flow_absorption_warning_validator.py first."
    )

df = pd.read_csv(SRC)
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")

for c in [
    "remaining_min","fair_preferred","distance_target","price_change_30s",
    "flow_imbalance","largest_trade_notional","notional_zscore",
    "book_imbalance","preferred_ask","edge"
]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

if "correct" in df.columns and df["correct"].dtype != bool:
    df["correct"] = df["correct"].astype(str).str.lower().map({"true": True, "false": False})

if "warn_opposite_move" in df.columns and df["warn_opposite_move"].dtype != bool:
    df["warn_opposite_move"] = (
        df["warn_opposite_move"].astype(str).str.lower().map({"true": True, "false": False})
    )

df = df.dropna(subset=[
    "ticker","timestamp_utc","remaining_min","fair_preferred",
    "distance_target","price_change_30s","preferred_side","correct"
]).copy()

df["abs_distance"] = df["distance_target"].abs()
df["model_signed_price_change"] = np.where(
    df["preferred_side"] == "UP",
    df["price_change_30s"],
    -df["price_change_30s"],
)
df["opposite_move_size"] = np.where(
    df["model_signed_price_change"] < 0,
    -df["model_signed_price_change"],
    0.0,
)
df["distance_to_move_ratio"] = np.where(
    df["opposite_move_size"] > 0,
    df["abs_distance"] / df["opposite_move_size"],
    np.nan,
)

warned = df[df["warn_opposite_move"] == True].copy()
mistakes = df[df["correct"] == False].copy()
winners = df[df["correct"] == True].copy()

print("Baseline calls:", len(df))
print("Correct:", len(winners))
print("Wrong:", len(mistakes))
print("Opposite-30 warnings:", len(warned))
print()

def show_rows(title, q):
    print(f"=== {title} ===")
    if q.empty:
        print("NONE")
        print()
        return
    for _, r in q.iterrows():
        print(
            r["ticker"],
            "| correct=", bool(r["correct"]),
            "| call=", r["preferred_side"],
            "| winner=", r["official_side"],
            "| left=", f"{r['remaining_min']:.2f}",
            "| fair=", f"{r['fair_preferred']:.1%}",
            "| dist=", f"${r['distance_target']:+.2f}",
            "| 30s=", f"${r['price_change_30s']:+.2f}",
            "| opp_size=", f"${r['opposite_move_size']:.2f}",
            "| dist/opp=", (
                f"{r['distance_to_move_ratio']:.2f}"
                if pd.notna(r["distance_to_move_ratio"]) else "N/A"
            ),
            "| flow_imb=", (
                f"{r['flow_imbalance']:+.1%}"
                if "flow_imbalance" in r and pd.notna(r["flow_imbalance"]) else "N/A"
            ),
            "| z=", (
                f"{r['notional_zscore']:+.2f}"
                if "notional_zscore" in r and pd.notna(r["notional_zscore"]) else "N/A"
            ),
            "| largest=", (
                f"${r['largest_trade_notional']:,.0f}"
                if "largest_trade_notional" in r and pd.notna(r["largest_trade_notional"]) else "N/A"
            ),
            "| book=", (
                f"{r['book_imbalance']:+.1%}"
                if "book_imbalance" in r and pd.notna(r["book_imbalance"]) else "N/A"
            ),
            "| absorption=", r.get("absorption_label", ""),
            "| flow=", r.get("flow_label", ""),
        )
    print()

show_rows("ALL OPPOSITE-30 WARNING CASES", warned)
show_rows("ALL BASELINE MISSES", mistakes)

print("=== SIMPLE DISCRIMINATOR SEARCH ===")
candidates = []

def eval_rule(name, mask):
    mask = mask.fillna(False)
    flagged = df[mask]
    kept = df[~mask]
    if len(flagged) == 0:
        return
    mistakes_total = len(mistakes)
    mistakes_caught = int((flagged["correct"] == False).sum())
    good_flagged = int((flagged["correct"] == True).sum())
    capture = mistakes_caught / mistakes_total if mistakes_total else np.nan
    false_warn = good_flagged / len(winners) if len(winners) else np.nan
    kept_acc = kept["correct"].mean() if len(kept) else np.nan

    candidates.append({
        "rule": name,
        "flagged": len(flagged),
        "mistakes_caught": mistakes_caught,
        "mistake_capture": capture,
        "good_flagged": good_flagged,
        "false_warning_rate": false_warn,
        "kept_calls": len(kept),
        "kept_accuracy": kept_acc,
    })

opp = df["warn_opposite_move"] == True

for threshold in [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]:
    eval_rule(f"opp30 AND move>={threshold}", opp & (df["opposite_move_size"] >= threshold))

for threshold in [0.80, 0.82, 0.85, 0.88, 0.90]:
    eval_rule(f"opp30 AND fair<={threshold:.2f}", opp & (df["fair_preferred"] <= threshold))

for threshold in [20, 40, 60, 80, 100, 125, 150]:
    eval_rule(f"opp30 AND abs_dist<={threshold}", opp & (df["abs_distance"] <= threshold))

for threshold in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
    eval_rule(
        f"opp30 AND dist/move<={threshold}",
        opp & (df["distance_to_move_ratio"] <= threshold)
    )

if "flow_imbalance" in df.columns:
    for threshold in [0.25, 0.50, 0.60, 0.70]:
        eval_rule(
            f"opp30 AND abs(flow_imb)>={threshold:.2f}",
            opp & (df["flow_imbalance"].abs() >= threshold)
        )

if "notional_zscore" in df.columns:
    for threshold in [0.0, 0.5, 1.0, 1.5, 2.0]:
        eval_rule(
            f"opp30 AND z>={threshold:.1f}",
            opp & (df["notional_zscore"] >= threshold)
        )

res = pd.DataFrame(candidates)

if res.empty:
    print("No candidate rules generated.")
else:
    res["score"] = (
        res["mistake_capture"].fillna(0) * 100
        - res["false_warning_rate"].fillna(1) * 50
        + res["kept_accuracy"].fillna(0) * 10
    )
    res = res.sort_values(
        ["score","mistake_capture","false_warning_rate","kept_accuracy"],
        ascending=[False, False, True, False]
    ).reset_index(drop=True)

    print("Top candidate rules:")
    for _, r in res.head(12).iterrows():
        print(
            r["rule"],
            "| flagged=", int(r["flagged"]),
            "| mistakes=", int(r["mistakes_caught"]),
            "| capture=", f"{r['mistake_capture']:.1%}",
            "| good_flagged=", int(r["good_flagged"]),
            "| false_warn=", f"{r['false_warning_rate']:.1%}",
            "| kept=", int(r["kept_calls"]),
            "| kept_acc=", f"{r['kept_accuracy']:.1%}",
        )

df.to_csv("kalshi_opposite30_baseline_call_details.csv", index=False)
if not res.empty:
    res.to_csv("kalshi_opposite30_candidate_rules.csv", index=False)

print()
print("=== IMPORTANT ===")
print("Diagnostic discriminator search only.")
print("No rule installed into bot.py.")
print("No scalp logic changed.")
print("Signal-only remains intact.")
print()
print("=== FILES CREATED ===")
print("kalshi_opposite30_baseline_call_details.csv")
if not res.empty:
    print("kalshi_opposite30_candidate_rules.csv")
print()
print("=== DISCRIMINATOR COMPLETE ===")
