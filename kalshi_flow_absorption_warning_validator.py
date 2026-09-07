from pathlib import Path
import pandas as pd
import numpy as np

MATCHED = Path("kalshi_flow_matched_snapshots.csv")

print("=== KALSHI FLOW ABSORPTION WARNING VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not MATCHED.exists():
    raise SystemExit(
        "ERROR: kalshi_flow_matched_snapshots.csv not found. "
        "Run kalshi_flow_outcome_matcher_validator.py first."
    )

df = pd.read_csv(MATCHED)
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")

for c in [
    "remaining_min","fair_preferred","distance_target","flow_imbalance",
    "largest_trade_notional","notional_zscore","price_change_30s",
    "trades_ge_1m","book_imbalance"
]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

for c in ["correct"]:
    if c in df.columns and df[c].dtype != bool:
        df[c] = df[c].astype(str).str.lower().map({"true": True, "false": False})

df = df.dropna(
    subset=[
        "timestamp_utc","ticker","remaining_min","fair_preferred",
        "distance_target","preferred_side","official_side","correct"
    ]
).copy()

early = df[
    (df["remaining_min"] >= 8.0)
    & (df["remaining_min"] <= 12.0)
].copy()

early["signed_distance"] = np.where(
    early["preferred_side"] == "UP",
    early["distance_target"],
    -early["distance_target"],
)

baseline = early[
    (early["fair_preferred"] >= 0.80)
    & (early["signed_distance"] > 0)
].copy()

first = (
    baseline.sort_values(["ticker","timestamp_utc"])
    .groupby("ticker", as_index=False)
    .head(1)
)

print("Matched contracts in 8-12 min zone:", early["ticker"].nunique())
print("Baseline first >=80% supported calls:", len(first))
if len(first):
    print("Baseline accuracy:", f"{first['correct'].mean():.1%}")
print()

if first.empty:
    raise SystemExit("No baseline calls available in matched flow sample.")

first["absorption_flag"] = first["absorption_label"].astype(str) != "NONE"
first["abnormal_label_flag"] = first["flow_label"].astype(str).str.contains(
    "ABNORMAL|MILLION_PLUS|IMBALANCE", regex=True, na=False
)
first["strong_imbalance_flag"] = first["flow_imbalance"].abs() >= 0.50
first["high_notional_flag"] = first["notional_zscore"] >= 2.0
first["million_plus_flag"] = first["trades_ge_1m"].fillna(0) > 0

first["model_signed_price_change"] = np.where(
    first["preferred_side"] == "UP",
    first["price_change_30s"],
    -first["price_change_30s"],
)
first["weak_followthrough_5"] = first["model_signed_price_change"] <= 5.0
first["opposite_30s_move"] = first["model_signed_price_change"] < 0

first["warn_absorption"] = first["absorption_flag"]
first["warn_abnormal_weak"] = first["abnormal_label_flag"] & first["weak_followthrough_5"]
first["warn_strongimb_weak"] = first["strong_imbalance_flag"] & first["weak_followthrough_5"]
first["warn_highnotional_weak"] = first["high_notional_flag"] & first["weak_followthrough_5"]
first["warn_opposite_move"] = first["opposite_30s_move"]

warning_cols = [
    ("ABSORPTION", "warn_absorption"),
    ("ABNORMAL + WEAK FOLLOWTHROUGH", "warn_abnormal_weak"),
    ("STRONG IMBALANCE + WEAK FOLLOWTHROUGH", "warn_strongimb_weak"),
    ("HIGH NOTIONAL + WEAK FOLLOWTHROUGH", "warn_highnotional_weak"),
    ("OPPOSITE 30s PRICE MOVE", "warn_opposite_move"),
]

print("=== WARNING PERFORMANCE AT FIRST BASELINE CALL ===")
rows = []

for label, col in warning_cols:
    warned = first[first[col] == True].copy()
    clean = first[first[col] != True].copy()

    mistakes = first[first["correct"] == False]
    caught = mistakes[mistakes[col] == True]

    correct_calls = first[first["correct"] == True]
    good_flagged = correct_calls[correct_calls[col] == True]

    warned_acc = warned["correct"].mean() if len(warned) else np.nan
    clean_acc = clean["correct"].mean() if len(clean) else np.nan
    miss_capture = len(caught) / len(mistakes) if len(mistakes) else np.nan
    false_warning_rate = len(good_flagged) / len(correct_calls) if len(correct_calls) else np.nan

    rows.append({
        "warning": label,
        "warned_n": len(warned),
        "warned_accuracy": warned_acc,
        "clean_n": len(clean),
        "clean_accuracy": clean_acc,
        "baseline_mistakes": len(mistakes),
        "mistakes_caught": len(caught),
        "mistake_capture_rate": miss_capture,
        "correct_calls_flagged": len(good_flagged),
        "false_warning_rate": false_warning_rate,
    })

    print()
    print(label)
    print("Warned calls:", len(warned), "| accuracy:",
          f"{warned_acc:.1%}" if len(warned) else "N/A")
    print("Clean calls:", len(clean), "| accuracy:",
          f"{clean_acc:.1%}" if len(clean) else "N/A")
    print("Mistakes caught:", f"{len(caught)}/{len(mistakes)}",
          "| capture:", f"{miss_capture:.1%}" if len(mistakes) else "N/A")
    print("Good calls incorrectly flagged:",
          f"{len(good_flagged)}/{len(correct_calls)}",
          "| false-warning:",
          f"{false_warning_rate:.1%}" if len(correct_calls) else "N/A")

print()
print("=== 90-SECOND PRE-CALL WARNING WINDOW ===")
pre_rows = []

for _, call in first.iterrows():
    t = call["timestamp_utc"]
    ticker = call["ticker"]

    window = early[
        (early["ticker"] == ticker)
        & (early["timestamp_utc"] <= t)
        & (early["timestamp_utc"] >= t - pd.Timedelta(seconds=90))
    ].copy()

    any_abs = (window["absorption_label"].astype(str) != "NONE").any()

    model_signed = np.where(
        window["preferred_side"] == "UP",
        window["price_change_30s"],
        -window["price_change_30s"],
    )

    any_abnormal_weak = (
        window["flow_label"].astype(str).str.contains(
            "ABNORMAL|MILLION_PLUS|IMBALANCE", regex=True, na=False
        )
        & (model_signed <= 5.0)
    ).any()

    any_opp = (model_signed < 0).any()

    pre_rows.append({
        "ticker": ticker,
        "correct": bool(call["correct"]),
        "pre90_absorption": bool(any_abs),
        "pre90_abnormal_weak": bool(any_abnormal_weak),
        "pre90_opposite_move": bool(any_opp),
    })

pre = pd.DataFrame(pre_rows)

for label, col in [
    ("PRE90 ABSORPTION", "pre90_absorption"),
    ("PRE90 ABNORMAL + WEAK", "pre90_abnormal_weak"),
    ("PRE90 OPPOSITE MOVE", "pre90_opposite_move"),
]:
    warned = pre[pre[col] == True]
    clean = pre[pre[col] != True]
    mistakes = pre[pre["correct"] == False]
    caught = mistakes[mistakes[col] == True]
    correct_calls = pre[pre["correct"] == True]
    good_flagged = correct_calls[correct_calls[col] == True]

    print()
    print(label)
    print("Warned:", len(warned), "| warned acc:",
          f"{warned['correct'].mean():.1%}" if len(warned) else "N/A")
    print("Clean:", len(clean), "| clean acc:",
          f"{clean['correct'].mean():.1%}" if len(clean) else "N/A")
    print("Mistakes caught:", f"{len(caught)}/{len(mistakes)}")
    print("Good calls flagged:", f"{len(good_flagged)}/{len(correct_calls)}")

pd.DataFrame(rows).to_csv(
    "kalshi_flow_absorption_warning_results.csv",
    index=False
)
first.to_csv(
    "kalshi_flow_first_baseline_calls_with_warnings.csv",
    index=False
)
pre.to_csv(
    "kalshi_flow_pre90_warning_calls.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_flow_absorption_warning_results.csv")
print("kalshi_flow_first_baseline_calls_with_warnings.csv")
print("kalshi_flow_pre90_warning_calls.csv")
print()
print("=== IMPORTANT ===")
print("This is a WARNING-layer test only.")
print("No warning has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== WARNING VALIDATION COMPLETE ===")
