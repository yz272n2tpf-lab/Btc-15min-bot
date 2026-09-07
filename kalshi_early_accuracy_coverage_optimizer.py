from pathlib import Path
import csv
import numpy as np
import pandas as pd

LOG = Path("kalshi_live_fair_value_shadow_log.csv")
SETTLED = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI EARLY ACCURACY / COVERAGE OPTIMIZER ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

if not LOG.exists():
    raise SystemExit(f"ERROR: {LOG} not found")
if not SETTLED.exists():
    raise SystemExit(
        f"ERROR: {SETTLED} not found. Run kalshi_official_settlement_validator.py first."
    )

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

if "official_side" not in official.columns:
    raise SystemExit("ERROR: settlement file missing official_side column")

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

# Dynamics
g = work.groupby("ticker", sort=False)
work["fair_change_1"] = g["fair_preferred"].diff()
work["fair_change_2"] = g["fair_preferred"].diff(2)
work["dist_change_1"] = g["signed_distance"].diff()

work["same_side_1"] = (
    work["preferred_side"] == g["preferred_side"].shift(1)
)
work["same_side_2"] = (
    work["same_side_1"]
    & (work["preferred_side"] == g["preferred_side"].shift(2))
)
work["same_side_3"] = (
    work["same_side_2"]
    & (work["preferred_side"] == g["preferred_side"].shift(3))
)

# We are optimizing the useful early window only.
early = work[
    (work["remaining_min"] >= 8.0)
    & (work["remaining_min"] <= 12.0)
].copy()

if early.empty:
    raise SystemExit("ERROR: no 8-12 minute rows")

# Chronological contract split.
contract_times = (
    work.groupby("ticker")["timestamp_utc"]
    .min()
    .sort_values()
)

ordered = contract_times.index.tolist()
cut = int(len(ordered) * 0.60)

train_ticks = set(ordered[:cut])
hold_ticks = set(ordered[cut:])

train = early[early["ticker"].isin(train_ticks)].copy()
hold = early[early["ticker"].isin(hold_ticks)].copy()

print("Official settled contracts:", len(ordered))
print("Training contracts (first 60%):", len(train_ticks))
print("Untouched holdout contracts (last 40%):", len(hold_ticks))
print()

def first_calls(frame, mask):
    q = frame.loc[mask].copy()
    if q.empty:
        return q
    return (
        q.sort_values(["ticker","timestamp_utc"])
         .groupby("ticker", as_index=False)
         .head(1)
    )

def stats(frame, mask, denom):
    first = first_calls(frame, mask)
    if first.empty:
        return 0, 0.0, np.nan
    n = first["ticker"].nunique()
    coverage = n / denom if denom else 0.0
    accuracy = float(first["correct"].mean())
    return n, coverage, accuracy

# Search rule family.
fair_thresholds = [0.75,0.78,0.80,0.82,0.84,0.85,0.86,0.88,0.90]
min_signed_distances = [0, 10, 20, 30, 50, 75]
persistences = [0, 1, 2, 3]
max_deteriorations = [0.00, -0.01, -0.02, -0.03, -0.05]
require_dist_strengthening = [False, True]

candidates = []

for fair_min in fair_thresholds:
    for dist_min in min_signed_distances:
        for persist in persistences:
            for max_det in max_deteriorations:
                for dist_strength in require_dist_strengthening:

                    mask = (
                        (train["fair_preferred"] >= fair_min)
                        & (train["signed_distance"] >= dist_min)
                        & (train["fair_change_1"].fillna(0) >= max_det)
                    )

                    if persist == 1:
                        mask &= train["same_side_1"]
                    elif persist == 2:
                        mask &= train["same_side_2"]
                    elif persist == 3:
                        mask &= train["same_side_3"]

                    if dist_strength:
                        mask &= train["dist_change_1"].fillna(0) >= 0

                    n, cov, acc = stats(train, mask, len(train_ticks))

                    # We need a meaningful number of independent contracts.
                    if n < 12:
                        continue

                    candidates.append({
                        "fair_min": fair_min,
                        "dist_min": dist_min,
                        "persist": persist,
                        "max_det": max_det,
                        "dist_strength": dist_strength,
                        "train_n": n,
                        "train_coverage": cov,
                        "train_accuracy": acc,
                    })

cand = pd.DataFrame(candidates)

if cand.empty:
    raise SystemExit("ERROR: no candidate rules survived minimum sample size")

# Select rules from TRAIN only.
# Tier A: at least 85% train accuracy, maximize coverage.
# Tier B: at least 88% train accuracy, maximize coverage.
# Tier C: at least 90% train accuracy, maximize coverage.
selected = []

for label, target_acc in [
    ("BALANCED_85", 0.85),
    ("STRONG_88", 0.88),
    ("ELITE_90", 0.90),
]:
    q = cand[cand["train_accuracy"] >= target_acc].copy()
    if q.empty:
        continue

    q = q.sort_values(
        ["train_coverage","train_accuracy","train_n"],
        ascending=[False, False, False],
    )

    best = q.iloc[0].to_dict()
    best["label"] = label
    best["target_acc"] = target_acc
    selected.append(best)

# Also pick highest training accuracy among rules with >=50% coverage.
q50 = cand[cand["train_coverage"] >= 0.50].copy()
if not q50.empty:
    q50 = q50.sort_values(
        ["train_accuracy","train_coverage","train_n"],
        ascending=[False, False, False],
    )
    best = q50.iloc[0].to_dict()
    best["label"] = "MAX_ACC_AT_50_COVERAGE"
    best["target_acc"] = np.nan
    selected.append(best)

print("=== TRAINING-ONLY RULE SELECTION ===")

def make_mask(frame, r):
    m = (
        (frame["fair_preferred"] >= r["fair_min"])
        & (frame["signed_distance"] >= r["dist_min"])
        & (frame["fair_change_1"].fillna(0) >= r["max_det"])
    )

    p = int(r["persist"])
    if p == 1:
        m &= frame["same_side_1"]
    elif p == 2:
        m &= frame["same_side_2"]
    elif p == 3:
        m &= frame["same_side_3"]

    if bool(r["dist_strength"]):
        m &= frame["dist_change_1"].fillna(0) >= 0

    return m

results = []

for r in selected:
    tm = make_mask(train, r)
    hm = make_mask(hold, r)

    tn, tcov, tacc = stats(train, tm, len(train_ticks))
    hn, hcov, hacc = stats(hold, hm, len(hold_ticks))

    row = {
        "label": r["label"],
        "fair_min": r["fair_min"],
        "dist_min": r["dist_min"],
        "persist": int(r["persist"]),
        "max_det": r["max_det"],
        "dist_strength": bool(r["dist_strength"]),
        "train_contracts": tn,
        "train_coverage": tcov,
        "train_accuracy": tacc,
        "holdout_contracts": hn,
        "holdout_coverage": hcov,
        "holdout_accuracy": hacc,
    }
    results.append(row)

    print()
    print(r["label"])
    print(
        "Rule:",
        f"fair>={r['fair_min']:.0%},",
        f"signed_distance>={r['dist_min']:.0f},",
        f"persistence={int(r['persist'])},",
        f"fair_change_1>={r['max_det']:+.0%},",
        f"distance_strengthening={bool(r['dist_strength'])}",
    )
    print(
        "TRAIN:",
        f"accuracy={tacc:.1%}",
        f"coverage={tcov:.1%}",
        f"contracts={tn}/{len(train_ticks)}",
    )
    if hn:
        print(
            "HOLDOUT:",
            f"accuracy={hacc:.1%}",
            f"coverage={hcov:.1%}",
            f"contracts={hn}/{len(hold_ticks)}",
        )
    else:
        print("HOLDOUT: no qualifying contracts")

# Baselines on same split
print()
print("=== SIMPLE THRESHOLD BASELINES ON HOLDOUT ===")
for threshold in [0.80,0.85,0.90]:
    hm = (
        (hold["fair_preferred"] >= threshold)
        & (hold["signed_distance"] > 0)
    )
    hn, hcov, hacc = stats(hold, hm, len(hold_ticks))
    if hn:
        print(
            f"fair>={threshold:.0%} + supported side | "
            f"accuracy={hacc:.1%} | "
            f"coverage={hcov:.1%} | "
            f"contracts={hn}/{len(hold_ticks)}"
        )

res = pd.DataFrame(results)
res.to_csv(
    "kalshi_early_accuracy_coverage_optimizer_results.csv",
    index=False,
)

# Candidate table saved for future inspection, but selection above remains
# training-only.
cand.sort_values(
    ["train_accuracy","train_coverage"],
    ascending=[False,False],
).to_csv(
    "kalshi_early_accuracy_coverage_candidate_rules.csv",
    index=False,
)

print()
print("=== FILES CREATED ===")
print("kalshi_early_accuracy_coverage_optimizer_results.csv")
print("kalshi_early_accuracy_coverage_candidate_rules.csv")
print()
print("=== IMPORTANT ===")
print("Rule selection used ONLY the first 60% of contracts.")
print("The last 40% was untouched until final evaluation.")
print("No selected rule has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== OPTIMIZATION COMPLETE ===")
