from pathlib import Path
import csv
import numpy as np
import pandas as pd

FLOW = Path("flow_test.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
SETTLED = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI FLOW / FINAL-OUTCOME MATCHER VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

for p in [FLOW, LIVE, SETTLED]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p}")

# -----------------------------
# Load flow samples
# -----------------------------
flow = pd.read_csv(FLOW)
flow["timestamp_utc"] = pd.to_datetime(
    flow["timestamp_utc"], utc=True, errors="coerce"
)

num_flow = [
    "mid_price","price_change_30s","trade_count",
    "aggressive_buy_notional","aggressive_sell_notional",
    "total_notional","flow_imbalance","largest_trade_notional",
    "trades_ge_250k","trades_ge_500k","trades_ge_1m",
    "notional_zscore","buy_notional_zscore","sell_notional_zscore",
    "bid_depth_25","ask_depth_25","book_imbalance"
]
for c in num_flow:
    if c in flow.columns:
        flow[c] = pd.to_numeric(flow[c], errors="coerce")

flow = flow.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc")

# -----------------------------
# Load live fair-value log
# mixed old/new schema support
# -----------------------------
OLD_HEADER = [
    "timestamp_utc","ticker","target","elapsed_min","remaining_min",
    "coinbase_close","distance_target","current_side",
    "flip_prob","stay_prob","fair_up","fair_down",
    "preferred_side","fair_preferred",
    "up_bid","up_ask","down_bid","down_ask",
    "preferred_ask","edge","signal_status","entry_status"
]

NEW_HEADER = [
    "timestamp_utc","ticker","target","elapsed_min","remaining_min",
    "coinbase_close","distance_target","current_side",
    "raw_flip_prob","flip_prob","stay_prob","probability_sanity",
    "fair_up","fair_down","preferred_side","fair_preferred",
    "up_bid","up_ask","down_bid","down_ask",
    "preferred_ask","edge","signal_status","entry_status"
]

rows = []
with LIVE.open(newline="") as f:
    reader = csv.reader(f)
    _ = next(reader, None)
    for vals in reader:
        if len(vals) == len(NEW_HEADER):
            rows.append(dict(zip(NEW_HEADER, vals)))
        elif len(vals) == len(OLD_HEADER):
            r = dict(zip(OLD_HEADER, vals))
            r["raw_flip_prob"] = ""
            r["probability_sanity"] = "OLD_SCHEMA"
            rows.append(r)

live = pd.DataFrame(rows)

for c in [
    "elapsed_min","remaining_min","distance_target",
    "raw_flip_prob","flip_prob","stay_prob",
    "fair_up","fair_down","fair_preferred",
    "preferred_ask","edge","coinbase_close"
]:
    live[c] = pd.to_numeric(live[c], errors="coerce")

live["timestamp_utc"] = pd.to_datetime(
    live["timestamp_utc"], utc=True, errors="coerce"
)

live = (
    live.dropna(
        subset=[
            "timestamp_utc","ticker","remaining_min",
            "preferred_side","fair_preferred","distance_target"
        ]
    )
    .sort_values("timestamp_utc")
    .reset_index(drop=True)
)

# -----------------------------
# Official settlements
# -----------------------------
official = pd.read_csv(SETTLED)
official = official[
    official["official_side"].isin(["UP","DOWN"])
][["ticker","official_side"]].drop_duplicates("ticker")

live = live.merge(official, on="ticker", how="inner")
live["correct"] = live["preferred_side"] == live["official_side"]

# -----------------------------
# Match each flow row to nearest live snapshot
# Max 45 seconds apart.
# -----------------------------
matched = pd.merge_asof(
    flow.sort_values("timestamp_utc"),
    live.sort_values("timestamp_utc"),
    on="timestamp_utc",
    direction="nearest",
    tolerance=pd.Timedelta(seconds=45),
    suffixes=("_flow", "_live"),
)

matched = matched.dropna(subset=["ticker"]).copy()

print("Flow samples:", len(flow))
print("Matched to live contract snapshots:", len(matched))
print("Match coverage:", f"{len(matched)/len(flow):.1%}" if len(flow) else "N/A")
print("Matched contracts:", matched["ticker"].nunique())
print()

if matched.empty:
    raise SystemExit("ERROR: no flow rows matched live snapshots")

# Research flags
matched["flow_side"] = np.where(
    matched["flow_imbalance"] >= 0,
    "UP",
    "DOWN"
)

matched["flow_agrees_model"] = (
    matched["flow_side"] == matched["preferred_side"]
)

matched["flow_agrees_winner"] = (
    matched["flow_side"] == matched["official_side"]
)

matched["abnormal_flow"] = (
    matched["flow_label"].astype(str).str.contains(
        "ABNORMAL|MILLION_PLUS|IMBALANCE",
        regex=True,
        na=False
    )
)

matched["absorption_event"] = (
    matched["absorption_label"].astype(str) != "NONE"
)

matched["million_plus"] = (
    pd.to_numeric(matched["trades_ge_1m"], errors="coerce").fillna(0) > 0
)

matched["strong_imbalance"] = (
    matched["flow_imbalance"].abs() >= 0.50
)

matched["high_notional"] = (
    matched["notional_zscore"] >= 2.0
)

# Main early zone
early = matched[
    (matched["remaining_min"] >= 8.0)
    & (matched["remaining_min"] <= 12.0)
].copy()

print("=== MATCHED 8-12 MINUTE ZONE ===")
print("Rows:", len(early))
print("Contracts:", early["ticker"].nunique())
if len(early):
    print("Model snapshot accuracy:", f"{early['correct'].mean():.1%}")
print()

def report(name, q):
    if q.empty:
        print(f"{name:34s} | none")
        return
    print(
        f"{name:34s} | "
        f"rows={len(q):3d} | "
        f"contracts={q['ticker'].nunique():2d} | "
        f"model_acc={q['correct'].mean():.1%} | "
        f"flow_winner_acc={q['flow_agrees_winner'].mean():.1%}"
    )

print("=== FLOW EVENT SNAPSHOT RESULTS ===")
report("All early matched rows", early)
report("Strong imbalance >=50%", early[early["strong_imbalance"]])
report("Abnormal/imbalance label", early[early["abnormal_flow"]])
report("High notional z>=2", early[early["high_notional"]])
report("Million-plus trade present", early[early["million_plus"]])
report("Absorption/reversal flag", early[early["absorption_event"]])
print()

print("=== WHEN FLOW AGREES / DISAGREES WITH MODEL ===")
agree = early[early["flow_agrees_model"]]
disagree = early[~early["flow_agrees_model"]]

if len(agree):
    print(
        "FLOW AGREES MODEL |",
        f"rows={len(agree)} |",
        f"model accuracy={agree['correct'].mean():.1%}"
    )
if len(disagree):
    print(
        "FLOW OPPOSES MODEL |",
        f"rows={len(disagree)} |",
        f"model accuracy={disagree['correct'].mean():.1%}"
    )
print()

# Baseline first >=80% supported call in these matched contracts only
early["signed_distance"] = np.where(
    early["preferred_side"] == "UP",
    early["distance_target"],
    -early["distance_target"],
)

baseline_rows = early[
    (early["fair_preferred"] >= 0.80)
    & (early["signed_distance"] > 0)
].copy()

baseline_first = (
    baseline_rows.sort_values(["ticker","timestamp_utc"])
    .groupby("ticker", as_index=False)
    .head(1)
)

print("=== FIRST >=80% SUPPORTED CALL, FLOW CONTEXT ===")
if baseline_first.empty:
    print("No qualifying baseline calls in this collection window.")
else:
    print(
        "Baseline calls:",
        len(baseline_first),
        "| accuracy:",
        f"{baseline_first['correct'].mean():.1%}"
    )

    bf_agree = baseline_first[baseline_first["flow_agrees_model"]]
    bf_oppose = baseline_first[~baseline_first["flow_agrees_model"]]

    if len(bf_agree):
        print(
            "At baseline call, flow AGREES:",
            f"n={len(bf_agree)} | accuracy={bf_agree['correct'].mean():.1%}"
        )
    if len(bf_oppose):
        print(
            "At baseline call, flow OPPOSES:",
            f"n={len(bf_oppose)} | accuracy={bf_oppose['correct'].mean():.1%}"
        )
print()

# Contract-level flow summary
contract_rows = []

for ticker, c in early.groupby("ticker"):
    winner = c["official_side"].iloc[0]

    buy_total = c["aggressive_buy_notional"].sum()
    sell_total = c["aggressive_sell_notional"].sum()
    denom = buy_total + sell_total
    net_imb = (buy_total - sell_total) / denom if denom > 0 else 0.0

    if net_imb > 0:
        net_side = "UP"
    elif net_imb < 0:
        net_side = "DOWN"
    else:
        net_side = "FLAT"

    contract_rows.append({
        "ticker": ticker,
        "official_side": winner,
        "flow_net_side": net_side,
        "flow_net_correct": net_side == winner,
        "net_flow_imbalance": net_imb,
        "buy_notional": buy_total,
        "sell_notional": sell_total,
        "max_trade": c["largest_trade_notional"].max(),
        "max_abs_imbalance": c["flow_imbalance"].abs().max(),
        "abnormal_events": int(c["abnormal_flow"].sum()),
        "absorption_events": int(c["absorption_event"].sum()),
        "million_plus_events": int(c["million_plus"].sum()),
        "model_snapshot_accuracy": c["correct"].mean(),
    })

contract_summary = pd.DataFrame(contract_rows)

print("=== CONTRACT-LEVEL FLOW SUMMARY ===")
if contract_summary.empty:
    print("None")
else:
    print(
        "Net flow direction matched official winner:",
        f"{contract_summary['flow_net_correct'].mean():.1%}",
        f"(n={len(contract_summary)})"
    )
    print()
    for _, r in contract_summary.iterrows():
        print(
            r["ticker"],
            "| winner=", r["official_side"],
            "| net flow=", r["flow_net_side"],
            "| flow correct=", bool(r["flow_net_correct"]),
            "| net imb=", f"{r['net_flow_imbalance']:+.1%}",
            "| max trade=", f"${r['max_trade']:,.0f}",
            "| max abs imb=", f"{r['max_abs_imbalance']:.1%}",
            "| abnormal=", int(r["abnormal_events"]),
            "| absorption=", int(r["absorption_events"]),
            "| $1m+=", int(r["million_plus_events"]),
        )

matched.to_csv(
    "kalshi_flow_matched_snapshots.csv",
    index=False
)

contract_summary.to_csv(
    "kalshi_flow_contract_summary.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_flow_matched_snapshots.csv")
print("kalshi_flow_contract_summary.csv")
print()
print("=== IMPORTANT ===")
print("This is a small first flow sample, not enough for permanent tuning.")
print("No flow rule has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== FLOW VALIDATION COMPLETE ===")
