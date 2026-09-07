from pathlib import Path
import csv
import json
import time
import urllib.request
import urllib.error
import numpy as np
import pandas as pd

LOG = Path("kalshi_live_fair_value_shadow_log.csv")

LIVE_BASE = "https://external-api.kalshi.com/trade-api/v2/markets/"
HIST_BASE = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"

print("=== KALSHI OFFICIAL SETTLEMENT VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not LOG.exists():
    raise SystemExit(f"ERROR: {LOG} not found")

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
            row = dict(zip(OLD_HEADER, vals))
            row["raw_flip_prob"] = ""
            row["probability_sanity"] = "OLD_SCHEMA"
            rows.append(row)

if not rows:
    raise SystemExit("ERROR: no usable live rows found")

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
            "preferred_side","fair_preferred"
        ]
    )
    .sort_values(["ticker","timestamp_utc"])
    .reset_index(drop=True)
)

def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def get_market(ticker):
    errors = []
    for base in (LIVE_BASE, HIST_BASE):
        try:
            payload = fetch_json(base + ticker)
            market = payload.get("market", payload)
            if isinstance(market, dict) and market.get("ticker"):
                return market, None
        except Exception as e:
            errors.append(str(e))
    return None, " | ".join(errors)

tickers = (
    df[["ticker"]]
    .drop_duplicates()
    .sort_values("ticker")["ticker"]
    .tolist()
)

print("Contracts found in live log:", len(tickers))
print("Checking official Kalshi results...")
print()

official = []
for i, ticker in enumerate(tickers, start=1):
    market, err = get_market(ticker)

    if market is None:
        official.append({
            "ticker": ticker,
            "status": "FETCH_ERROR",
            "result": "",
            "official_side": "",
            "settlement_ts": "",
            "error": err or "",
        })
        print(f"[{i:3d}/{len(tickers)}] {ticker}: FETCH ERROR")
        continue

    result = str(market.get("result") or "").lower().strip()
    status = str(market.get("status") or "").lower().strip()
    settlement_ts = str(market.get("settlement_ts") or "")

    if result == "yes":
        side = "UP"
    elif result == "no":
        side = "DOWN"
    else:
        side = ""

    official.append({
        "ticker": ticker,
        "status": status,
        "result": result,
        "official_side": side,
        "settlement_ts": settlement_ts,
        "error": "",
    })

    label = side if side else "NOT SETTLED/NO RESULT"
    print(f"[{i:3d}/{len(tickers)}] {ticker}: {status} / {label}")

    # Be gentle with the public endpoint.
    time.sleep(0.05)

official_df = pd.DataFrame(official)

official_df.to_csv(
    "kalshi_official_settlement_check.csv",
    index=False,
)

settled = official_df[
    official_df["official_side"].isin(["UP","DOWN"])
].copy()

print()
print("=== OFFICIAL SETTLEMENT COVERAGE ===")
print("Contracts in log:", len(tickers))
print("Official results obtained:", len(settled))
print(
    "Coverage:",
    f"{(len(settled)/len(tickers)):.1%}" if tickers else "N/A"
)
print(
    "UP / DOWN:",
    int((settled["official_side"] == "UP").sum()),
    "/",
    int((settled["official_side"] == "DOWN").sum()),
)
print()

if settled.empty:
    raise SystemExit(
        "No official settled results were returned yet. "
        "Re-run later or inspect kalshi_official_settlement_check.csv."
    )

work = df.merge(
    settled[["ticker","official_side"]],
    on="ticker",
    how="inner",
)

work["correct"] = (
    work["preferred_side"] == work["official_side"]
)

work["signed_distance"] = np.where(
    work["preferred_side"] == "UP",
    work["distance_target"],
    -work["distance_target"],
)

work["same_side_prev"] = (
    work["preferred_side"]
    == work.groupby("ticker")["preferred_side"].shift(1)
)

work["fair_change_1"] = (
    work.groupby("ticker")["fair_preferred"].diff()
)

print("=== OVERALL OFFICIAL DIRECTIONAL ACCURACY ===")
print(
    "All scored live snapshots:",
    f"{work['correct'].mean():.1%}",
    f"(n={len(work)})"
)
print()

# Time buckets
bins = [
    (12, 15),
    (10, 12),
    (8, 10),
    (6, 8),
    (4, 6),
    (2, 4),
    (0, 2),
]

print("=== OFFICIAL ACCURACY BY TIME REMAINING ===")
for lo, hi in bins:
    q = work[
        (work["remaining_min"] >= lo)
        & (work["remaining_min"] < hi)
    ]
    if len(q):
        print(
            f"{lo:>2}-{hi:<2} min left | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"rows={len(q):4d} | "
            f"contracts={q['ticker'].nunique():3d}"
        )
print()

early = work[
    (work["remaining_min"] >= 8.0)
    & (work["remaining_min"] <= 12.0)
].copy()

print("=== OFFICIAL 8-12 MIN FAIR THRESHOLDS ===")
for threshold in [0.70,0.75,0.80,0.85,0.90,0.92,0.95]:
    q = early[early["fair_preferred"] >= threshold]
    if len(q):
        print(
            f"Fair >= {threshold:.0%} | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"rows={len(q):3d} | "
            f"contracts={q['ticker'].nunique():2d}"
        )
print()

# Research quality tiers.
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

print("=== OFFICIAL QUALITY-TIER SNAPSHOT RESULTS ===")
for tier in [
    "RAW",
    "CANDIDATE",
    "SUPPORTED",
    "HIGH_QUALITY",
    "EARLY_LOCK_RESEARCH",
]:
    q = early[early["quality_tier"] == tier]
    if len(q):
        print(
            f"{tier:20s} | "
            f"accuracy={q['correct'].mean():.1%} | "
            f"rows={len(q):3d} | "
            f"contracts={q['ticker'].nunique():2d}"
        )
print()

# First qualifying call per contract.
tier_order = [
    "CANDIDATE",
    "SUPPORTED",
    "HIGH_QUALITY",
    "EARLY_LOCK_RESEARCH",
]

print("=== FIRST QUALIFYING OFFICIAL CALL PER CONTRACT ===")
denom = settled["ticker"].nunique()

for tier in tier_order:
    min_idx = tier_order.index(tier)

    accepted = early[
        early["quality_tier"].map(
            lambda x: (
                tier_order.index(x) >= min_idx
                if x in tier_order else False
            )
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
            f"accuracy={first['correct'].mean():.1%} | "
            f"contracts={len(first):2d}/{denom} | "
            f"coverage={len(first)/denom:.1%}"
        )
print()

# Chronological holdout based only on contracts with official outcomes.
contract_times = (
    work.groupby("ticker")["timestamp_utc"]
    .min()
    .sort_values()
)

ordered_ticks = contract_times.index.tolist()
cut = int(len(ordered_ticks) * 0.60)
holdout_ticks = set(ordered_ticks[cut:])

holdout = early[
    early["ticker"].isin(holdout_ticks)
].copy()

print("=== OFFICIAL CHRONOLOGICAL HOLDOUT: LAST 40% ===")
print("Holdout contracts:", len(holdout_ticks))

for threshold in [0.80,0.85,0.90]:
    q = holdout[
        (holdout["fair_preferred"] >= threshold)
        & (holdout["signed_distance"] > 0)
    ].copy()

    first = (
        q.sort_values(["ticker","timestamp_utc"])
        .groupby("ticker", as_index=False)
        .head(1)
    )

    if len(first):
        print(
            f"First fair >= {threshold:.0%} supported call | "
            f"accuracy={first['correct'].mean():.1%} | "
            f"n={len(first)}"
        )
print()

print("=== FILE CREATED ===")
print("kalshi_official_settlement_check.csv")
print()
print("=== IMPORTANT ===")
print("These scores use Kalshi's returned market result field.")
print("No thresholds have been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== VALIDATION COMPLETE ===")
