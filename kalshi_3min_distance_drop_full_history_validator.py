from pathlib import Path
import csv
import pandas as pd
import numpy as np

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
SETTLED = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI 3-MIN DISTANCE-DROP FULL-HISTORY VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Testing candidate: 3-minute distance deterioration after first >=80% supported call.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

for p in [LIVE, SETTLED]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p}")

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
    "elapsed_min","remaining_min","distance_target","fair_preferred",
    "fair_up","fair_down","preferred_ask","edge","coinbase_close"
]:
    live[c] = pd.to_numeric(live[c], errors="coerce")

live["timestamp_utc"] = pd.to_datetime(live["timestamp_utc"], utc=True, errors="coerce")
live = live.dropna(subset=[
    "timestamp_utc","ticker","remaining_min","distance_target",
    "preferred_side","fair_preferred"
]).sort_values("timestamp_utc").copy()

official = pd.read_csv(SETTLED)
official = official[
    official["official_side"].isin(["UP","DOWN"])
][["ticker","official_side"]].drop_duplicates("ticker")

live = live.merge(official, on="ticker", how="inner")
live["correct"] = live["preferred_side"] == live["official_side"]

# First >=80% supported call in 8-12 minute zone.
early = live[
    (live["remaining_min"] >= 8.0)
    & (live["remaining_min"] <= 12.0)
].copy()

early["signed_distance"] = np.where(
    early["preferred_side"] == "UP",
    early["distance_target"],
    -early["distance_target"]
)

baseline = early[
    (early["fair_preferred"] >= 0.80)
    & (early["signed_distance"] > 0)
].copy()

first = (
    baseline.sort_values(["ticker","timestamp_utc"])
    .groupby("ticker", as_index=False)
    .head(1)
    .copy()
)

print("Official contracts available:", live["ticker"].nunique())
print("First >=80% supported calls:", len(first))
print("Baseline accuracy:", f"{first['correct'].mean():.1%}" if len(first) else "N/A")
print()

if first.empty:
    raise SystemExit("No qualifying first calls found.")

traj_rows = []

for _, call in first.iterrows():
    ticker = call["ticker"]
    t0 = call["timestamp_utc"]
    call_side = call["preferred_side"]
    init_signed = (
        call["distance_target"]
        if call_side == "UP"
        else -call["distance_target"]
    )

    c = live[
        (live["ticker"] == ticker)
        & (live["timestamp_utc"] >= t0)
        & (live["timestamp_utc"] <= t0 + pd.Timedelta(minutes=3))
    ].sort_values("timestamp_utc").copy()

    if c.empty:
        continue

    c["signed_dist_for_call"] = np.where(
        call_side == "UP",
        c["distance_target"],
        -c["distance_target"]
    )

    c["distance_drop"] = init_signed - c["signed_dist_for_call"]

    traj_rows.append({
        "ticker": ticker,
        "call_time": t0,
        "call_side": call_side,
        "official_side": call["official_side"],
        "correct": bool(call["correct"]),
        "initial_fair": call["fair_preferred"],
        "initial_remaining_min": call["remaining_min"],
        "initial_distance": call["distance_target"],
        "initial_signed_distance": init_signed,
        "three_min_rows": len(c),
        "three_min_max_distance_drop": c["distance_drop"].max(),
        "three_min_min_signed_distance": c["signed_dist_for_call"].min(),
        "three_min_side_flip": bool((c["preferred_side"] != call_side).any()),
    })

traj = pd.DataFrame(traj_rows)

print("Trajectories with 3-minute follow-up:", len(traj))
print()

thresholds = [50, 75, 100, 125, 150, 175, 200, 250]
results = []

print("=== THRESHOLD RESULTS ===")

for threshold in thresholds:
    flagged = traj[traj["three_min_max_distance_drop"] >= threshold]
    clean = traj[traj["three_min_max_distance_drop"] < threshold]

    wrong = traj[traj["correct"] == False]
    good = traj[traj["correct"] == True]

    mistakes_caught = int((flagged["correct"] == False).sum())
    good_flagged = int((flagged["correct"] == True).sum())

    capture = mistakes_caught / len(wrong) if len(wrong) else np.nan
    false_warn = good_flagged / len(good) if len(good) else np.nan
    clean_acc = clean["correct"].mean() if len(clean) else np.nan

    results.append({
        "threshold": threshold,
        "flagged": len(flagged),
        "mistakes_caught": mistakes_caught,
        "mistake_capture": capture,
        "good_flagged": good_flagged,
        "false_warning_rate": false_warn,
        "clean_calls": len(clean),
        "clean_accuracy": clean_acc,
    })

    print(
        f"3m distance_drop >= ${threshold}",
        "| flagged=", len(flagged),
        "| mistakes=", mistakes_caught,
        "| capture=", f"{capture:.1%}" if len(wrong) else "N/A",
        "| good_flagged=", good_flagged,
        "| false_warn=", f"{false_warn:.1%}" if len(good) else "N/A",
        "| clean=", len(clean),
        "| clean_acc=", f"{clean_acc:.1%}" if len(clean) else "N/A",
    )

print()
print("=== $150 CANDIDATE DETAILS ===")
candidate = traj[traj["three_min_max_distance_drop"] >= 150].copy()

if candidate.empty:
    print("No calls flagged.")
else:
    for _, r in candidate.iterrows():
        print(
            r["ticker"],
            "| correct=", bool(r["correct"]),
            "| call=", r["call_side"],
            "| winner=", r["official_side"],
            "| initial fair=", f"{r['initial_fair']:.1%}",
            "| initial dist=", f"${r['initial_distance']:+.2f}",
            "| 3m drop=", f"${r['three_min_max_distance_drop']:.2f}",
            "| 3m flip=", bool(r["three_min_side_flip"]),
        )

print()
print("=== CHRONOLOGICAL HOLDOUT CHECK: LAST 40% OF QUALIFYING CALLS ===")

traj = traj.sort_values("call_time").reset_index(drop=True)
split = int(len(traj) * 0.60)
hold = traj.iloc[split:].copy()

print("Holdout calls:", len(hold))
if len(hold):
    print("Holdout baseline accuracy:", f"{hold['correct'].mean():.1%}")

    flagged = hold[hold["three_min_max_distance_drop"] >= 150]
    clean = hold[hold["three_min_max_distance_drop"] < 150]
    wrong = hold[hold["correct"] == False]
    good = hold[hold["correct"] == True]

    caught = int((flagged["correct"] == False).sum())
    good_flagged = int((flagged["correct"] == True).sum())

    print(
        "$150 rule | flagged=", len(flagged),
        "| mistakes_caught=", f"{caught}/{len(wrong)}",
        "| good_flagged=", f"{good_flagged}/{len(good)}",
        "| clean_acc=", f"{clean['correct'].mean():.1%}" if len(clean) else "N/A",
    )

traj.to_csv("kalshi_3min_distance_drop_full_history_details.csv", index=False)
pd.DataFrame(results).to_csv(
    "kalshi_3min_distance_drop_full_history_results.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_3min_distance_drop_full_history_details.csv")
print("kalshi_3min_distance_drop_full_history_results.csv")
print()
print("=== IMPORTANT ===")
print("Research validation only.")
print("No rule installed into bot.py.")
print("No scalp logic changed.")
print("Signal-only remains intact.")
print()
print("=== FULL-HISTORY VALIDATION COMPLETE ===")
