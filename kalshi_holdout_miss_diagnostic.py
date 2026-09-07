from pathlib import Path
import csv
import numpy as np
import pandas as pd

LOG = Path("kalshi_live_fair_value_shadow_log.csv")
SETTLED = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI HOLDOUT MISS DIAGNOSTIC ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not LOG.exists():
    raise SystemExit(f"ERROR: {LOG} not found")
if not SETTLED.exists():
    raise SystemExit(f"ERROR: {SETTLED} not found")

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
with LOG.open(newline="") as f:
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

df = pd.DataFrame(rows)

for c in [
    "elapsed_min","remaining_min","distance_target",
    "raw_flip_prob","flip_prob","stay_prob",
    "fair_up","fair_down","fair_preferred",
    "preferred_ask","edge"
]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df["timestamp_utc"] = pd.to_datetime(
    df["timestamp_utc"], utc=True, errors="coerce"
)

df = (
    df.dropna(
        subset=[
            "timestamp_utc","ticker","remaining_min",
            "distance_target","preferred_side","fair_preferred"
        ]
    )
    .sort_values(["ticker","timestamp_utc"])
    .reset_index(drop=True)
)

official = pd.read_csv(SETTLED)
official = official[
    official["official_side"].isin(["UP","DOWN"])
][["ticker","official_side"]].drop_duplicates("ticker")

work = df.merge(official, on="ticker", how="inner").copy()

work["correct"] = work["preferred_side"] == work["official_side"]
work["signed_distance"] = np.where(
    work["preferred_side"] == "UP",
    work["distance_target"],
    -work["distance_target"],
)

g = work.groupby("ticker", sort=False)
work["fair_change_1"] = g["fair_preferred"].diff()
work["fair_change_2"] = g["fair_preferred"].diff(2)
work["fair_change_3"] = g["fair_preferred"].diff(3)
work["dist_change_1"] = g["signed_distance"].diff()
work["dist_change_2"] = g["signed_distance"].diff(2)

work["same_side_prev"] = (
    work["preferred_side"] == g["preferred_side"].shift(1)
)

# Count preferred-side flips within each contract.
work["side_flip"] = (
    work["preferred_side"] != g["preferred_side"].shift(1)
)
work.loc[g.cumcount() == 0, "side_flip"] = False

contract_times = (
    work.groupby("ticker")["timestamp_utc"]
    .min()
    .sort_values()
)

ordered = contract_times.index.tolist()
cut = int(len(ordered) * 0.60)
hold_ticks = set(ordered[cut:])

hold = work[work["ticker"].isin(hold_ticks)].copy()
early = hold[
    (hold["remaining_min"] >= 8.0)
    & (hold["remaining_min"] <= 12.0)
].copy()

print("Official settled contracts:", len(ordered))
print("Untouched holdout contracts:", len(hold_ticks))
print("8-12 minute holdout rows:", len(early))
print()

# Simple baseline that previously generalized best.
qual = early[
    (early["fair_preferred"] >= 0.80)
    & (early["signed_distance"] > 0)
].copy()

first = (
    qual.sort_values(["ticker","timestamp_utc"])
        .groupby("ticker", as_index=False)
        .head(1)
)

qualified_ticks = set(first["ticker"])
noqual_ticks = hold_ticks - qualified_ticks

wins = first[first["correct"]].copy()
misses = first[~first["correct"]].copy()

print("=== BASELINE HOLDOUT ===")
print(
    f"First >=80% supported call: "
    f"{len(first)}/{len(hold_ticks)} contracts | "
    f"coverage={len(first)/len(hold_ticks):.1%} | "
    f"accuracy={first['correct'].mean():.1%}"
)
print("Correct qualifying calls:", len(wins))
print("Wrong qualifying calls:", len(misses))
print("No qualifying call:", len(noqual_ticks))
print()

# Contract-level summaries before 8 minutes remaining.
summaries = []

for ticker in sorted(hold_ticks):
    c = hold[hold["ticker"] == ticker].sort_values("timestamp_utc").copy()
    e = c[
        (c["remaining_min"] >= 8.0)
        & (c["remaining_min"] <= 12.0)
    ].copy()

    if e.empty:
        continue

    final_side = c["official_side"].iloc[0]

    max_fair_idx = e["fair_preferred"].idxmax()
    maxrow = e.loc[max_fair_idx]

    summaries.append({
        "ticker": ticker,
        "official_side": final_side,
        "qualified80": ticker in qualified_ticks,
        "first80_correct": (
            bool(first[first["ticker"] == ticker]["correct"].iloc[0])
            if ticker in qualified_ticks else np.nan
        ),
        "max_fair_8_12": e["fair_preferred"].max(),
        "mean_fair_8_12": e["fair_preferred"].mean(),
        "mean_abs_distance": e["distance_target"].abs().mean(),
        "max_abs_distance": e["distance_target"].abs().max(),
        "mean_signed_distance": e["signed_distance"].mean(),
        "side_flips_8_12": int(e["side_flip"].sum()),
        "positive_support_pct": float((e["signed_distance"] > 0).mean()),
        "mean_fair_change_1": e["fair_change_1"].mean(),
        "max_fair_change_1": e["fair_change_1"].max(),
        "min_fair_change_1": e["fair_change_1"].min(),
        "mean_dist_change_1": e["dist_change_1"].mean(),
        "max_fair_preferred_side": maxrow["preferred_side"],
        "max_fair_correct": maxrow["preferred_side"] == final_side,
    })

summary = pd.DataFrame(summaries)

def show_group(name, frame):
    print(f"=== {name} ===")
    if frame.empty:
        print("None")
        print()
        return
    cols = [
        "mean_fair_8_12",
        "max_fair_8_12",
        "mean_abs_distance",
        "max_abs_distance",
        "mean_signed_distance",
        "side_flips_8_12",
        "positive_support_pct",
        "mean_fair_change_1",
        "mean_dist_change_1",
    ]
    for c in cols:
        print(f"{c:24s}: {frame[c].mean():.4f}")
    print("contracts:", len(frame))
    print()

good = summary[
    (summary["qualified80"] == True)
    & (summary["first80_correct"] == True)
]
bad = summary[
    (summary["qualified80"] == True)
    & (summary["first80_correct"] == False)
]
noq = summary[
    summary["qualified80"] == False
]

show_group("CORRECT >=80% SUPPORTED CALLS", good)
show_group("WRONG >=80% SUPPORTED CALLS", bad)
show_group("NO >=80% SUPPORTED CALL", noq)

print("=== WRONG QUALIFYING CONTRACT DETAILS ===")
if bad.empty:
    print("None")
else:
    for _, r in bad.iterrows():
        print(
            r["ticker"],
            "| winner=", r["official_side"],
            "| mean fair=", f"{r['mean_fair_8_12']:.1%}",
            "| max fair=", f"{r['max_fair_8_12']:.1%}",
            "| mean abs dist=", f"${r['mean_abs_distance']:.2f}",
            "| flips=", int(r["side_flips_8_12"]),
            "| supported pct=", f"{r['positive_support_pct']:.1%}",
        )
print()

print("=== NO-QUALIFIER CONTRACT DETAILS ===")
if noq.empty:
    print("None")
else:
    for _, r in noq.iterrows():
        print(
            r["ticker"],
            "| winner=", r["official_side"],
            "| max fair=", f"{r['max_fair_8_12']:.1%}",
            "| mean abs dist=", f"${r['mean_abs_distance']:.2f}",
            "| flips=", int(r["side_flips_8_12"]),
            "| supported pct=", f"{r['positive_support_pct']:.1%}",
            "| max-fair-side-correct=", bool(r["max_fair_correct"]),
        )
print()

# Try a SMALL, predeclared diagnostic grid only.
# This is not a free-form optimizer; it checks a few intuitive filters
# against the same untouched holdout to see what characteristics matter.
tests = [
    ("BASELINE", 0.80, 0, None, None),
    ("DIST_20", 0.80, 20, None, None),
    ("DIST_40", 0.80, 40, None, None),
    ("PERSIST_1", 0.80, 0, 1, None),
    ("NO_FAST_DROP", 0.80, 0, None, -0.02),
    ("DIST20_PERSIST1", 0.80, 20, 1, None),
    ("DIST20_NO_FAST_DROP", 0.80, 20, None, -0.02),
]

print("=== DIAGNOSTIC FILTER CHECKS ON HOLDOUT ===")
for name, fairmin, distmin, persist, maxdrop in tests:
    mask = (
        (early["fair_preferred"] >= fairmin)
        & (early["signed_distance"] >= distmin)
    )
    if persist == 1:
        mask &= early["same_side_prev"]
    if maxdrop is not None:
        mask &= early["fair_change_1"].fillna(0) >= maxdrop

    q = (
        early.loc[mask]
        .sort_values(["ticker","timestamp_utc"])
        .groupby("ticker", as_index=False)
        .head(1)
    )

    if len(q):
        print(
            f"{name:20s} | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"coverage={len(q)/len(hold_ticks):.1%} | "
            f"contracts={len(q)}/{len(hold_ticks)}"
        )

summary.to_csv(
    "kalshi_holdout_miss_diagnostic_contracts.csv",
    index=False,
)

print()
print("=== FILE CREATED ===")
print("kalshi_holdout_miss_diagnostic_contracts.csv")
print()
print("=== IMPORTANT ===")
print("This script diagnoses the untouched holdout; it does NOT fit a new model.")
print("No rule has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== DIAGNOSTIC COMPLETE ===")
