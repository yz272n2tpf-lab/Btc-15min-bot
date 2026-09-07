from pathlib import Path
import pandas as pd
import numpy as np

MATCHED = Path("kalshi_flow_matched_snapshots.csv")
FIRST = Path("kalshi_flow_first_baseline_calls_with_warnings.csv")

print("=== KALSHI POST-CALL TRAJECTORY DANGER VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

for p in [MATCHED, FIRST]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p}")

snap = pd.read_csv(MATCHED)
first = pd.read_csv(FIRST)

snap["timestamp_utc"] = pd.to_datetime(snap["timestamp_utc"], utc=True, errors="coerce")
first["timestamp_utc"] = pd.to_datetime(first["timestamp_utc"], utc=True, errors="coerce")

for df in [snap, first]:
    for c in [
        "remaining_min","fair_preferred","distance_target","price_change_30s",
        "flow_imbalance","notional_zscore","largest_trade_notional"
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "correct" in df.columns and df["correct"].dtype != bool:
        df["correct"] = df["correct"].astype(str).str.lower().map(
            {"true": True, "false": False}
        )

snap = snap.dropna(subset=[
    "ticker","timestamp_utc","remaining_min","preferred_side",
    "fair_preferred","distance_target","official_side","correct"
]).copy()

first = first.dropna(subset=[
    "ticker","timestamp_utc","remaining_min","preferred_side",
    "fair_preferred","distance_target","official_side","correct"
]).copy()

rows = []

print("Baseline calls:", len(first))
print("Correct:", int(first["correct"].sum()))
print("Wrong:", int((~first["correct"]).sum()))
print()

for _, call in first.iterrows():
    ticker = call["ticker"]
    t0 = call["timestamp_utc"]
    call_side = call["preferred_side"]
    initial_fair = float(call["fair_preferred"])
    initial_dist = float(call["distance_target"])
    initial_abs_dist = abs(initial_dist)

    c = snap[
        (snap["ticker"] == ticker)
        & (snap["timestamp_utc"] >= t0)
    ].sort_values("timestamp_utc").copy()

    if c.empty:
        continue

    # Convert distance into "support for original call side".
    c["signed_dist_for_call"] = np.where(
        call_side == "UP",
        c["distance_target"],
        -c["distance_target"]
    )
    init_signed = initial_dist if call_side == "UP" else -initial_dist

    # Probability of the ORIGINAL call side, even if preferred side later flips.
    if call_side == "UP" and "fair_up" in c.columns:
        c["fair_original_side"] = pd.to_numeric(c["fair_up"], errors="coerce")
    elif call_side == "DOWN" and "fair_down" in c.columns:
        c["fair_original_side"] = pd.to_numeric(c["fair_down"], errors="coerce")
    else:
        c["fair_original_side"] = np.where(
            c["preferred_side"] == call_side,
            c["fair_preferred"],
            1.0 - c["fair_preferred"]
        )

    c["fair_drop"] = initial_fair - c["fair_original_side"]
    c["distance_drop"] = init_signed - c["signed_dist_for_call"]
    c["distance_ratio"] = np.where(
        abs(init_signed) > 1e-9,
        c["signed_dist_for_call"] / abs(init_signed),
        np.nan
    )
    c["side_flipped"] = c["preferred_side"] != call_side

    # Check within 30s, 60s, 90s, 2m, 3m, and rest of contract.
    windows = {
        "30s": 30,
        "60s": 60,
        "90s": 90,
        "2m": 120,
        "3m": 180,
        "rest": None,
    }

    out = {
        "ticker": ticker,
        "call_side": call_side,
        "official_side": call["official_side"],
        "correct": bool(call["correct"]),
        "call_time": t0,
        "initial_remaining_min": call["remaining_min"],
        "initial_fair": initial_fair,
        "initial_distance": initial_dist,
        "initial_abs_distance": initial_abs_dist,
    }

    for label, secs in windows.items():
        if secs is None:
            w = c.copy()
        else:
            w = c[c["timestamp_utc"] <= t0 + pd.Timedelta(seconds=secs)].copy()

        if w.empty:
            out[f"{label}_n"] = 0
            continue

        out[f"{label}_n"] = len(w)
        out[f"{label}_min_fair_original"] = w["fair_original_side"].min()
        out[f"{label}_max_fair_drop"] = w["fair_drop"].max()
        out[f"{label}_min_signed_distance"] = w["signed_dist_for_call"].min()
        out[f"{label}_max_distance_drop"] = w["distance_drop"].max()
        out[f"{label}_min_distance_ratio"] = w["distance_ratio"].min()
        out[f"{label}_any_flip"] = bool(w["side_flipped"].any())

    rows.append(out)

traj = pd.DataFrame(rows)

if traj.empty:
    raise SystemExit("ERROR: no post-call trajectories built")

print("Trajectories built:", len(traj))
print()

# Diagnostic comparison correct vs wrong
metrics = [
    "30s_max_fair_drop","60s_max_fair_drop","90s_max_fair_drop",
    "2m_max_fair_drop","3m_max_fair_drop",
    "30s_max_distance_drop","60s_max_distance_drop","90s_max_distance_drop",
    "2m_max_distance_drop","3m_max_distance_drop",
    "30s_min_distance_ratio","60s_min_distance_ratio","90s_min_distance_ratio",
    "2m_min_distance_ratio","3m_min_distance_ratio",
]

print("=== CORRECT VS WRONG TRAJECTORY SUMMARY ===")
for metric in metrics:
    if metric not in traj.columns:
        continue
    good = traj.loc[traj["correct"] == True, metric].dropna()
    bad = traj.loc[traj["correct"] == False, metric].dropna()

    if len(good) == 0 or len(bad) == 0:
        continue

    print(
        metric,
        "| good median=", f"{good.median():.4f}",
        "| bad median=", f"{bad.median():.4f}",
        "| good max=", f"{good.max():.4f}",
        "| bad max=", f"{bad.max():.4f}",
    )

print()
print("=== SIMPLE DANGER RULE SEARCH ===")

candidates = []

def eval_rule(name, mask):
    mask = mask.fillna(False)
    flagged = traj[mask]
    clean = traj[~mask]

    if len(flagged) == 0:
        return

    mistakes = traj[traj["correct"] == False]
    winners = traj[traj["correct"] == True]

    caught = int((flagged["correct"] == False).sum())
    good_flagged = int((flagged["correct"] == True).sum())

    candidates.append({
        "rule": name,
        "flagged": len(flagged),
        "mistakes_caught": caught,
        "mistake_capture": caught / len(mistakes) if len(mistakes) else np.nan,
        "good_flagged": good_flagged,
        "false_warning_rate": good_flagged / len(winners) if len(winners) else np.nan,
        "clean_calls": len(clean),
        "clean_accuracy": clean["correct"].mean() if len(clean) else np.nan,
    })

# Fair-drop rules
for window in ["30s","60s","90s","2m","3m"]:
    col = f"{window}_max_fair_drop"
    if col in traj.columns:
        for threshold in [0.03,0.05,0.07,0.10,0.12,0.15,0.20]:
            eval_rule(
                f"{window} fair_drop>={threshold:.0%}",
                traj[col] >= threshold
            )

# Distance collapse in absolute dollars
for window in ["30s","60s","90s","2m","3m"]:
    col = f"{window}_max_distance_drop"
    if col in traj.columns:
        for threshold in [25,50,75,100,150,200]:
            eval_rule(
                f"{window} distance_drop>={threshold}",
                traj[col] >= threshold
            )

# Distance retained ratio
for window in ["30s","60s","90s","2m","3m"]:
    col = f"{window}_min_distance_ratio"
    if col in traj.columns:
        for threshold in [0.75,0.50,0.25,0.0,-0.25]:
            eval_rule(
                f"{window} distance_ratio<={threshold}",
                traj[col] <= threshold
            )

# Side flip rules
for window in ["30s","60s","90s","2m","3m"]:
    col = f"{window}_any_flip"
    if col in traj.columns:
        eval_rule(
            f"{window} side_flip",
            traj[col] == True
        )

res = pd.DataFrame(candidates)

if not res.empty:
    res["score"] = (
        res["mistake_capture"].fillna(0) * 100
        - res["false_warning_rate"].fillna(1) * 60
        + res["clean_accuracy"].fillna(0) * 10
    )

    res = res.sort_values(
        ["score","mistake_capture","false_warning_rate","clean_accuracy"],
        ascending=[False, False, True, False]
    ).reset_index(drop=True)

    print("Top candidate danger rules:")
    for _, r in res.head(15).iterrows():
        print(
            r["rule"],
            "| flagged=", int(r["flagged"]),
            "| mistakes=", int(r["mistakes_caught"]),
            "| capture=", f"{r['mistake_capture']:.1%}",
            "| good_flagged=", int(r["good_flagged"]),
            "| false_warn=", f"{r['false_warning_rate']:.1%}",
            "| clean=", int(r["clean_calls"]),
            "| clean_acc=", f"{r['clean_accuracy']:.1%}",
        )

print()
print("=== MISS DETAILS ===")
misses = traj[traj["correct"] == False].copy()
for _, r in misses.iterrows():
    print(
        r["ticker"],
        "| call=", r["call_side"],
        "| winner=", r["official_side"],
        "| initial fair=", f"{r['initial_fair']:.1%}",
        "| initial dist=", f"${r['initial_distance']:+.2f}",
        "| 60s fair drop=", f"{r.get('60s_max_fair_drop', np.nan):.1%}",
        "| 90s fair drop=", f"{r.get('90s_max_fair_drop', np.nan):.1%}",
        "| 2m fair drop=", f"{r.get('2m_max_fair_drop', np.nan):.1%}",
        "| 60s dist drop=", f"${r.get('60s_max_distance_drop', np.nan):.2f}",
        "| 90s dist drop=", f"${r.get('90s_max_distance_drop', np.nan):.2f}",
        "| 2m dist drop=", f"${r.get('2m_max_distance_drop', np.nan):.2f}",
        "| 2m flip=", bool(r.get("2m_any_flip", False)),
    )

traj.to_csv("kalshi_postcall_trajectory_details.csv", index=False)
if not res.empty:
    res.to_csv("kalshi_postcall_danger_candidate_rules.csv", index=False)

print()
print("=== FILES CREATED ===")
print("kalshi_postcall_trajectory_details.csv")
if not res.empty:
    print("kalshi_postcall_danger_candidate_rules.csv")

print()
print("=== IMPORTANT ===")
print("This is a post-call research validator only.")
print("No danger rule has been installed into bot.py.")
print("No scalp logic has been changed.")
print("Signal-only remains intact.")
print()
print("=== TRAJECTORY VALIDATION COMPLETE ===")
