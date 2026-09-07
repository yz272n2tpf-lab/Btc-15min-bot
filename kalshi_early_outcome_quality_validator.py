from pathlib import Path
import csv
import numpy as np
import pandas as pd

LOG = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI EARLY 15-MIN OUTCOME QUALITY VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not LOG.exists():
    raise SystemExit(f"ERROR: {LOG} not found")

# The live log may contain rows from both the old and calibration-fixed schemas.
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
    header = next(reader, None)

    for vals in reader:
        if len(vals) == len(NEW_HEADER):
            rows.append(dict(zip(NEW_HEADER, vals)))
        elif len(vals) == len(OLD_HEADER):
            row = dict(zip(OLD_HEADER, vals))
            row["raw_flip_prob"] = ""
            row["probability_sanity"] = "OLD_SCHEMA"
            rows.append(row)

if not rows:
    raise SystemExit("ERROR: no usable rows found")

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

# ------------------------------------------------------------
# PROVISIONAL CONTRACT OUTCOME
#
# Only score a contract if its final captured snapshot is within
# 54 seconds of expiration and >= $10 from target.
#
# This is intentionally conservative but is still PROVISIONAL.
# Official Kalshi settlement remains the final verification step.
# ------------------------------------------------------------

last = (
    df.sort_values("timestamp_utc")
      .groupby("ticker", as_index=False)
      .tail(1)
      .copy()
)

scoreable = last[
    (last["remaining_min"] <= 0.90)
    & (last["distance_target"].abs() >= 10.0)
].copy()

scoreable["final_side"] = np.where(
    scoreable["distance_target"] > 0,
    "UP",
    "DOWN",
)

outcomes = scoreable[
    ["ticker","final_side"]
].drop_duplicates("ticker")

work = df.merge(outcomes, on="ticker", how="inner").copy()

work["correct"] = (
    work["preferred_side"] == work["final_side"]
)

# Preferred-side signed target distance:
# positive means BTC is currently on the same target side as our call.
work["signed_distance"] = np.where(
    work["preferred_side"] == "UP",
    work["distance_target"],
    -work["distance_target"],
)

work["fair_change_1"] = (
    work.groupby("ticker")["fair_preferred"].diff()
)

work["fair_change_3"] = (
    work.groupby("ticker")["fair_preferred"].diff(3)
)

work["signed_distance_change_1"] = (
    work.groupby("ticker")["signed_distance"].diff()
)

# Count same preferred side across consecutive observations.
work["same_side_prev"] = (
    work["preferred_side"]
    == work.groupby("ticker")["preferred_side"].shift(1)
)

work["same_side_2prev"] = (
    work["same_side_prev"]
    & (
        work["preferred_side"]
        == work.groupby("ticker")["preferred_side"].shift(2)
    )
)

# Main development zone.
early = work[
    (work["remaining_min"] >= 8.0)
    & (work["remaining_min"] <= 12.0)
].copy()

print("Usable live rows:", len(df))
print("Contracts in log:", df["ticker"].nunique())
print("Provisionally scoreable contracts:", outcomes["ticker"].nunique())
print("8-12 minute rows:", len(early))
print()

if early.empty:
    raise SystemExit("No 8-12 minute observations available.")

print("=== BASELINE 8-12 MINUTES REMAINING ===")
print(
    "All observations:",
    f"{early['correct'].mean():.1%}",
    f"(n={len(early)})",
)
print()

print("=== FAIR-PROBABILITY THRESHOLDS ===")
for threshold in [0.70,0.75,0.80,0.85,0.90,0.92,0.95]:
    q = early[early["fair_preferred"] >= threshold]
    if len(q):
        print(
            f"Fair >= {threshold:.0%} | "
            f"rows={len(q):3d} | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"contracts={q['ticker'].nunique():2d}"
        )
print()

# ------------------------------------------------------------
# EARLY QUALITY TIERS
#
# These are VALIDATION tiers, not trading instructions.
#
# Candidate:
#   fair >= 75%
#
# Supported:
#   fair >= 80%
#   current BTC is on preferred target side
#
# High Quality:
#   fair >= 85%
#   current BTC is on preferred target side
#   same side as previous snapshot
#   probability is not deteriorating by >2 points
#
# Early Lock Research:
#   fair >= 90%
#   current BTC is on preferred side
#
# ------------------------------------------------------------

early["quality_tier"] = "RAW"

early.loc[
    early["fair_preferred"] >= 0.75,
    "quality_tier"
] = "CANDIDATE"

early.loc[
    (early["fair_preferred"] >= 0.80)
    & (early["signed_distance"] > 0),
    "quality_tier"
] = "SUPPORTED"

early.loc[
    (early["fair_preferred"] >= 0.85)
    & (early["signed_distance"] > 0)
    & early["same_side_prev"]
    & (early["fair_change_1"].fillna(0) >= -0.02),
    "quality_tier"
] = "HIGH_QUALITY"

early.loc[
    (early["fair_preferred"] >= 0.90)
    & (early["signed_distance"] > 0),
    "quality_tier"
] = "EARLY_LOCK_RESEARCH"

print("=== QUALITY-TIER SNAPSHOT RESULTS ===")
for tier in [
    "RAW","CANDIDATE","SUPPORTED",
    "HIGH_QUALITY","EARLY_LOCK_RESEARCH"
]:
    q = early[early["quality_tier"] == tier]
    if len(q):
        print(
            f"{tier:20s} | "
            f"rows={len(q):3d} | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"contracts={q['ticker'].nunique():2d}"
        )
print()

# ------------------------------------------------------------
# FIRST QUALIFYING CALL PER CONTRACT
# This is the more honest contract-level measurement.
# ------------------------------------------------------------

print("=== FIRST QUALIFYING CALL PER CONTRACT ===")
for tier in [
    "CANDIDATE","SUPPORTED",
    "HIGH_QUALITY","EARLY_LOCK_RESEARCH"
]:
    order = [
        "CANDIDATE","SUPPORTED",
        "HIGH_QUALITY","EARLY_LOCK_RESEARCH"
    ]
    min_idx = order.index(tier)

    accepted = early[
        early["quality_tier"].map(
            lambda x: order.index(x) >= min_idx if x in order else False
        )
    ].copy()

    first = (
        accepted.sort_values(["ticker","timestamp_utc"])
                .groupby("ticker", as_index=False)
                .head(1)
    )

    if len(first):
        print(
            f"{tier:20s} | "
            f"contracts={len(first):2d}/{outcomes['ticker'].nunique()} | "
            f"coverage={len(first)/outcomes['ticker'].nunique():.1%} | "
            f"accuracy={first['correct'].mean():.1%}"
        )
print()

# Chronological holdout: last 40% of scoreable contracts.
contract_times = (
    work.groupby("ticker")["timestamp_utc"]
        .min()
        .sort_values()
)

tickers = contract_times.index.tolist()
cut = int(len(tickers) * 0.60)
holdout_ticks = set(tickers[cut:])

holdout = early[
    early["ticker"].isin(holdout_ticks)
].copy()

print("=== CHRONOLOGICAL HOLDOUT: LAST 40% CONTRACTS ===")
print("Holdout contracts:", len(holdout_ticks))

for threshold in [0.80,0.85,0.90]:
    q = holdout[
        (holdout["fair_preferred"] >= threshold)
        & (holdout["signed_distance"] > 0)
    ]

    first = (
        q.sort_values(["ticker","timestamp_utc"])
         .groupby("ticker", as_index=False)
         .head(1)
    )

    if len(first):
        print(
            f"First fair>={threshold:.0%} supported call | "
            f"n={len(first):2d} | "
            f"accuracy={first['correct'].mean():.1%}"
        )
print()

print("=== IMPORTANT ===")
print("These outcomes are provisional from near-expiration BTC/target position.")
print("Official Kalshi settlement verification remains required before integration.")
print("No thresholds are being installed into bot.py from this test alone.")
print()
print("=== TEST COMPLETE ===")
