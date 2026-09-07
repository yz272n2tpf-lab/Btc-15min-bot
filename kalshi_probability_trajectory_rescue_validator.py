from pathlib import Path
import csv
import numpy as np
import pandas as pd

LOG = Path("kalshi_live_fair_value_shadow_log.csv")
SETTLED = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI PROBABILITY TRAJECTORY RESCUE VALIDATOR ===")
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

# Signed fair probability relative to UP:
# >0.5 favors UP, <0.5 favors DOWN.
work["p_up"] = np.where(
    work["preferred_side"] == "UP",
    work["fair_preferred"],
    1.0 - work["fair_preferred"],
)

# Signed distance relative to UP.
work["signed_up_distance"] = work["distance_target"]

# Main early decision window.
early = work[
    (work["remaining_min"] >= 8.0)
    & (work["remaining_min"] <= 12.0)
].copy()

if early.empty:
    raise SystemExit("ERROR: no 8-12 minute observations")

# Chronological split by contract.
contract_times = (
    work.groupby("ticker")["timestamp_utc"]
    .min()
    .sort_values()
)

ordered = contract_times.index.tolist()
cut = int(len(ordered) * 0.60)

train_ticks = set(ordered[:cut])
hold_ticks = set(ordered[cut:])

print("Official settled contracts:", len(ordered))
print("Training contracts:", len(train_ticks))
print("Untouched holdout contracts:", len(hold_ticks))
print()

def baseline_first(frame):
    q = frame[
        (frame["fair_preferred"] >= 0.80)
        & (
            np.where(
                frame["preferred_side"] == "UP",
                frame["distance_target"],
                -frame["distance_target"],
            ) > 0
        )
    ].copy()

    if q.empty:
        return q

    return (
        q.sort_values(["ticker","timestamp_utc"])
         .groupby("ticker", as_index=False)
         .head(1)
    )

def trajectory_features(frame):
    feats = []

    for ticker, c in frame.groupby("ticker"):
        c = c.sort_values("timestamp_utc").copy()
        if len(c) < 3:
            continue

        winner = c["official_side"].iloc[0]

        x = np.arange(len(c), dtype=float)
        p = c["p_up"].to_numpy(dtype=float)
        d = c["signed_up_distance"].to_numpy(dtype=float)

        # Linear path slope through the 8-12 minute window.
        p_slope = np.polyfit(x, p, 1)[0] if len(c) >= 2 else 0.0
        d_slope = np.polyfit(x, d, 1)[0] if len(c) >= 2 else 0.0

        first_half = c.iloc[:max(1, len(c)//2)]
        second_half = c.iloc[len(c)//2:]

        # Dominant side across the window.
        up_share = float((c["p_up"] > 0.5).mean())
        if up_share > 0.5:
            traj_side = "UP"
            dominant_share = up_share
        elif up_share < 0.5:
            traj_side = "DOWN"
            dominant_share = 1.0 - up_share
        else:
            # Tie -> use final reading in window.
            traj_side = "UP" if c["p_up"].iloc[-1] >= 0.5 else "DOWN"
            dominant_share = 0.5

        # Trajectory strength relative to chosen side.
        if traj_side == "UP":
            final_support = float(c["p_up"].iloc[-1])
            mean_support = float(c["p_up"].mean())
            improvement = float(
                second_half["p_up"].mean() - first_half["p_up"].mean()
            )
            dist_support_mean = float((c["distance_target"] > 0).mean())
            final_distance = float(c["distance_target"].iloc[-1])
            distance_trend = float(d_slope)
        else:
            final_support = float(1.0 - c["p_up"].iloc[-1])
            mean_support = float(1.0 - c["p_up"].mean())
            improvement = float(
                (1.0 - second_half["p_up"]).mean()
                - (1.0 - first_half["p_up"]).mean()
            )
            dist_support_mean = float((c["distance_target"] < 0).mean())
            final_distance = float(-c["distance_target"].iloc[-1])
            distance_trend = float(-d_slope)

        # Number of sign flips around 50%.
        signs = np.where(c["p_up"] >= 0.5, 1, -1)
        flips = int(np.sum(signs[1:] != signs[:-1]))

        feats.append({
            "ticker": ticker,
            "official_side": winner,
            "traj_side": traj_side,
            "correct": traj_side == winner,
            "n_rows": len(c),
            "dominant_share": dominant_share,
            "final_support": final_support,
            "mean_support": mean_support,
            "improvement": improvement,
            "dist_support_mean": dist_support_mean,
            "final_distance": final_distance,
            "distance_trend": distance_trend,
            "flips": flips,
            "p_slope_abs": abs(float(p_slope)),
        })

    return pd.DataFrame(feats)

train = early[early["ticker"].isin(train_ticks)].copy()
hold = early[early["ticker"].isin(hold_ticks)].copy()

train_base = baseline_first(train)
hold_base = baseline_first(hold)

train_base_ticks = set(train_base["ticker"])
hold_base_ticks = set(hold_base["ticker"])

train_noq = train[~train["ticker"].isin(train_base_ticks)].copy()
hold_noq = hold[~hold["ticker"].isin(hold_base_ticks)].copy()

train_feat = trajectory_features(train_noq)
hold_feat = trajectory_features(hold_noq)

print("=== EXISTING BASELINE ===")
print(
    "TRAIN:",
    f"calls={len(train_base)}/{len(train_ticks)}",
    f"coverage={len(train_base)/len(train_ticks):.1%}",
    f"accuracy={train_base['correct'].mean():.1%}" if len(train_base) else "accuracy=N/A",
)
print(
    "HOLDOUT:",
    f"calls={len(hold_base)}/{len(hold_ticks)}",
    f"coverage={len(hold_base)/len(hold_ticks):.1%}",
    f"accuracy={hold_base['correct'].mean():.1%}" if len(hold_base) else "accuracy=N/A",
)
print()

print("No-baseline-call contracts:")
print("TRAIN:", train_feat["ticker"].nunique())
print("HOLDOUT:", hold_feat["ticker"].nunique())
print()

# Small, explicit rescue-rule family.
# Selection uses TRAIN no-call contracts only.
rules = []

for dominant_share in [0.60, 0.70, 0.80]:
    for final_support in [0.60, 0.65, 0.70]:
        for dist_support in [0.60, 0.70, 0.80]:
            for max_flips in [0, 1, 2]:
                mask = (
                    (train_feat["dominant_share"] >= dominant_share)
                    & (train_feat["final_support"] >= final_support)
                    & (train_feat["dist_support_mean"] >= dist_support)
                    & (train_feat["flips"] <= max_flips)
                )

                q = train_feat[mask].copy()
                n = len(q)

                if n < 5:
                    continue

                rules.append({
                    "dominant_share": dominant_share,
                    "final_support": final_support,
                    "dist_support": dist_support,
                    "max_flips": max_flips,
                    "train_n": n,
                    "train_accuracy": float(q["correct"].mean()),
                })

rules = pd.DataFrame(rules)

if rules.empty:
    raise SystemExit("No rescue rule had enough training contracts.")

# Prefer >=80% training rescue accuracy, then maximize rescued contracts.
eligible = rules[rules["train_accuracy"] >= 0.80].copy()

if eligible.empty:
    eligible = rules.copy()

eligible = eligible.sort_values(
    ["train_n","train_accuracy"],
    ascending=[False,False],
)

best = eligible.iloc[0].to_dict()

print("=== TRAINING-SELECTED TRAJECTORY RESCUE RULE ===")
print(
    f"dominant_share >= {best['dominant_share']:.0%}, "
    f"final_support >= {best['final_support']:.0%}, "
    f"distance_support >= {best['dist_support']:.0%}, "
    f"max_flips <= {int(best['max_flips'])}"
)
print(
    "TRAIN rescue:",
    f"accuracy={best['train_accuracy']:.1%}",
    f"contracts={int(best['train_n'])}/{len(train_feat)}",
)
print()

def apply_rule(feat, r):
    return feat[
        (feat["dominant_share"] >= r["dominant_share"])
        & (feat["final_support"] >= r["final_support"])
        & (feat["dist_support_mean"] >= r["dist_support"])
        & (feat["flips"] <= int(r["max_flips"]))
    ].copy()

train_rescue = apply_rule(train_feat, best)
hold_rescue = apply_rule(hold_feat, best)

print("=== UNTOUCHED HOLDOUT RESCUE ===")
if len(hold_rescue):
    print(
        "Rescue-only accuracy:",
        f"{hold_rescue['correct'].mean():.1%}",
        f"| rescued={len(hold_rescue)}/{len(hold_feat)} no-call contracts"
    )
else:
    print("No holdout contracts qualified for rescue.")
print()

# Combined baseline + rescue.
def combined_stats(base, rescue, total_contracts):
    base_correct = int(base["correct"].sum()) if len(base) else 0
    rescue_correct = int(rescue["correct"].sum()) if len(rescue) else 0
    total_calls = len(base) + len(rescue)
    total_correct = base_correct + rescue_correct

    accuracy = total_correct / total_calls if total_calls else np.nan
    coverage = total_calls / total_contracts if total_contracts else np.nan
    return total_calls, total_correct, accuracy, coverage

tr_calls, tr_correct, tr_acc, tr_cov = combined_stats(
    train_base, train_rescue, len(train_ticks)
)
ho_calls, ho_correct, ho_acc, ho_cov = combined_stats(
    hold_base, hold_rescue, len(hold_ticks)
)

print("=== COMBINED FINAL-OUTCOME COVERAGE ===")
print(
    "TRAIN combined:",
    f"accuracy={tr_acc:.1%}",
    f"coverage={tr_cov:.1%}",
    f"calls={tr_calls}/{len(train_ticks)}",
)
print(
    "HOLDOUT combined:",
    f"accuracy={ho_acc:.1%}",
    f"coverage={ho_cov:.1%}",
    f"calls={ho_calls}/{len(hold_ticks)}",
)
print()

print("=== HOLDOUT RESCUED CONTRACT DETAILS ===")
if hold_rescue.empty:
    print("None")
else:
    for _, r in hold_rescue.sort_values("ticker").iterrows():
        print(
            r["ticker"],
            "| call=", r["traj_side"],
            "| winner=", r["official_side"],
            "| correct=", bool(r["correct"]),
            "| dominant=", f"{r['dominant_share']:.1%}",
            "| final_support=", f"{r['final_support']:.1%}",
            "| dist_support=", f"{r['dist_support_mean']:.1%}",
            "| flips=", int(r["flips"]),
        )

# Save diagnostics.
train_feat.to_csv(
    "kalshi_probability_trajectory_train_no_call_contracts.csv",
    index=False,
)
hold_feat.to_csv(
    "kalshi_probability_trajectory_holdout_no_call_contracts.csv",
    index=False,
)

pd.DataFrame([best]).to_csv(
    "kalshi_probability_trajectory_selected_rescue_rule.csv",
    index=False,
)

print()
print("=== FILES CREATED ===")
print("kalshi_probability_trajectory_train_no_call_contracts.csv")
print("kalshi_probability_trajectory_holdout_no_call_contracts.csv")
print("kalshi_probability_trajectory_selected_rescue_rule.csv")
print()
print("=== IMPORTANT ===")
print("The baseline >=80% supported rule was NOT changed.")
print("The rescue rule was selected only on training no-call contracts.")
print("The final 40% holdout was untouched until evaluation.")
print("No rule has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== TRAJECTORY RESCUE VALIDATION COMPLETE ===")
