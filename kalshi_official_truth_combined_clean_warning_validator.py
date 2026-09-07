from pathlib import Path
import csv
import math
import pandas as pd
import numpy as np

RESCORE = Path("kalshi_official_truth_layer_a_rescore_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OUT = Path("kalshi_official_truth_combined_clean_warning_results.csv")

print("=== KALSHI OFFICIAL-TRUTH COMBINED CLEAN-WARNING VALIDATOR ===")
print("Purpose: combine the earlier CLEAN-miss deterioration signal with the late-reversal signal.")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

EARLY_FAIR_DROP = 0.150
EARLY_HORIZON_SEC = 420.0
LATE_FLIP_REMAINING_MIN = 1.5
LATE_NEG25_REMAINING_MIN = 3.0
LATE_NEG25_DISTANCE = -25.0

def pick(cols, names):
    low = {str(c).lower(): c for c in cols}
    for n in names:
        if n in cols:
            return n
        if n.lower() in low:
            return low[n.lower()]
    return None

def as_bool(v):
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in ("true", "1", "yes", "y", "t")

def read_mixed_csv(path: Path) -> pd.DataFrame:
    # Mixed-schema-safe reader: use first row as canonical header, then pad/truncate later rows.
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return pd.DataFrame()
    header = rows[0]
    width = len(header)
    fixed = []
    for r in rows[1:]:
        if not r:
            continue
        if len(r) < width:
            r = r + [""] * (width - len(r))
        elif len(r) > width:
            r = r[:width]
        fixed.append(r)
    return pd.DataFrame(fixed, columns=header)

if not RESCORE.exists():
    raise SystemExit(f"Missing {RESCORE}")
if not LIVE.exists():
    raise SystemExit(f"Missing {LIVE}")

r = pd.read_csv(RESCORE, low_memory=False)
live = read_mixed_csv(LIVE)

# ---------- RESCORE COLUMN MAP ----------
rticker = pick(r.columns, ["ticker"])
rtime = pick(r.columns, ["ts", "call_time", "timestamp_utc", "timestamp"])
rside = pick(r.columns, ["call_side", "preferred_side"])
rcorrect = pick(r.columns, ["correct"])
rstate = pick(r.columns, ["state", "layer_a_state"])
rfair = pick(r.columns, ["fair_pref_num", "initial_fair", "fair_preferred"])
rremain = pick(r.columns, ["remaining_num", "initial_remaining_min", "remaining_min"])
rinitdist = pick(r.columns, ["initial_signed_distance", "rescore_initial_signed_distance", "initial_distance"])

need = {
    "ticker": rticker, "call_time": rtime, "call_side": rside,
    "correct": rcorrect, "state": rstate
}
missing = [k for k, v in need.items() if v is None]
if missing:
    print("Rescore columns:", list(r.columns))
    raise SystemExit("Missing required rescore fields: " + ", ".join(missing))

# ---------- LIVE COLUMN MAP ----------
lticker = pick(live.columns, ["ticker"])
ltime = pick(live.columns, ["timestamp_utc", "timestamp"])
lremain = pick(live.columns, ["remaining_min", "remaining"])
ldist = pick(live.columns, ["distance_target", "distance_from_target", "distance"])
lfup = pick(live.columns, ["fair_up"])
lfdown = pick(live.columns, ["fair_down"])
lstatus = pick(live.columns, ["signal_status"])

need_live = {
    "ticker": lticker, "timestamp": ltime, "remaining_min": lremain,
    "distance_target": ldist, "fair_up": lfup, "fair_down": lfdown
}
missing_live = [k for k, v in need_live.items() if v is None]
if missing_live:
    print("Live columns:", list(live.columns))
    raise SystemExit("Missing required live fields: " + ", ".join(missing_live))

# Parse live once.
live["_ts"] = pd.to_datetime(live[ltime], utc=True, errors="coerce")
live["_rem"] = pd.to_numeric(live[lremain], errors="coerce")
live["_dist"] = pd.to_numeric(live[ldist], errors="coerce")
live["_fair_up"] = pd.to_numeric(live[lfup], errors="coerce")
live["_fair_down"] = pd.to_numeric(live[lfdown], errors="coerce")
live["_ticker"] = live[lticker].astype(str)

# Clean-call population only, official truth already baked into rescore file.
rr = r.copy()
rr["_ticker"] = rr[rticker].astype(str)
rr["_call_time"] = pd.to_datetime(rr[rtime], utc=True, errors="coerce")
rr["_side"] = rr[rside].astype(str).str.upper().str.strip()
rr["_correct"] = rr[rcorrect].map(as_bool)
rr["_state"] = rr[rstate].astype(str).str.upper().str.strip()
rr = rr[(rr["_state"] == "CLEAN") & rr["_call_time"].notna() & rr["_side"].isin(["UP", "DOWN"])].copy()
rr = rr.sort_values("_call_time").reset_index(drop=True)

print(f"CLEAN calls loaded: {len(rr)}")
print(f"Winners: {int(rr['_correct'].sum())}")
print(f"Misses: {int((~rr['_correct']).sum())}")
print()

rows = []
for _, call in rr.iterrows():
    ticker = call["_ticker"]
    side = call["_side"]
    ct = call["_call_time"]

    q = live[(live["_ticker"] == ticker) & live["_ts"].notna()].copy()
    q = q[q["_ts"] >= ct].sort_values("_ts")

    if q.empty:
        rows.append({
            "ticker": ticker, "call_time": ct, "call_side": side,
            "correct": bool(call["_correct"]), "usable": False
        })
        continue

    q["sec_from_call"] = (q["_ts"] - ct).dt.total_seconds()
    q["signed_distance"] = np.where(side == "UP", q["_dist"], -q["_dist"])
    q["call_fair"] = np.where(side == "UP", q["_fair_up"], q["_fair_down"])

    # Initial fair: prefer rescore's exact stored call fair. If absent, first live row at/after call.
    init_fair = pd.to_numeric(pd.Series([call[rfair] if rfair else np.nan]), errors="coerce").iloc[0]
    if pd.isna(init_fair):
        init_fair = q["call_fair"].dropna().iloc[0] if q["call_fair"].notna().any() else np.nan

    init_dist = pd.to_numeric(pd.Series([call[rinitdist] if rinitdist else np.nan]), errors="coerce").iloc[0]
    if pd.isna(init_dist):
        init_dist = q["signed_distance"].dropna().iloc[0] if q["signed_distance"].notna().any() else np.nan

    # Earlier deterioration: maximum fair-value drop within first 420 seconds after call.
    early = q[(q["sec_from_call"] >= 0) & (q["sec_from_call"] <= EARLY_HORIZON_SEC)].copy()
    if pd.notna(init_fair) and early["call_fair"].notna().any():
        early_worst_fair_drop = float((init_fair - early["call_fair"]).max())
    else:
        early_worst_fair_drop = np.nan
    early_warning = bool(pd.notna(early_worst_fair_drop) and early_worst_fair_drop >= EARLY_FAIR_DROP)

    # Late reversal signature #1: original call side flips negative with <=1.5m remaining.
    late15 = q[(q["_rem"] >= 0) & (q["_rem"] <= LATE_FLIP_REMAINING_MIN)]
    late_flip = bool((late15["signed_distance"] < 0).any()) if len(late15) else False

    # Late reversal signature #2: reaches at least $25 onto the opposite side in final 3m.
    late3 = q[(q["_rem"] >= 0) & (q["_rem"] <= LATE_NEG25_REMAINING_MIN)]
    late_neg25 = bool((late3["signed_distance"] < LATE_NEG25_DISTANCE).any()) if len(late3) else False

    first_flip_remaining = np.nan
    flips = q[(q["_rem"] >= 0) & (q["signed_distance"] < 0)]
    if len(flips):
        first_flip_remaining = float(flips.iloc[0]["_rem"])

    min_late3_distance = float(late3["signed_distance"].min()) if len(late3) and late3["signed_distance"].notna().any() else np.nan
    min_late15_distance = float(late15["signed_distance"].min()) if len(late15) and late15["signed_distance"].notna().any() else np.nan

    rows.append({
        "ticker": ticker,
        "call_time": ct,
        "call_side": side,
        "correct": bool(call["_correct"]),
        "usable": True,
        "initial_fair": init_fair,
        "initial_signed_distance": init_dist,
        "early_420s_worst_fair_drop": early_worst_fair_drop,
        "early_warning": early_warning,
        "late_flip_le_1p5m": late_flip,
        "late_neg25_le_3m": late_neg25,
        "first_flip_remaining_min": first_flip_remaining,
        "min_signed_distance_final_1p5m": min_late15_distance,
        "min_signed_distance_final_3m": min_late3_distance,
        "combined_early_or_lateflip": early_warning or late_flip,
        "combined_early_or_neg25": early_warning or late_neg25,
    })

d = pd.DataFrame(rows)
d = d[d["usable"] == True].sort_values("call_time").reset_index(drop=True)

print(f"Usable CLEAN calls: {len(d)}")
print(f"Usable winners: {int(d['correct'].sum())}")
print(f"Usable misses: {int((~d['correct']).sum())}")
print()

def score(label, mask, frame):
    mask = mask.fillna(False).astype(bool)
    misses = ~frame["correct"].astype(bool)
    winners = frame["correct"].astype(bool)
    flagged = int(mask.sum())
    caught = int((mask & misses).sum())
    total_misses = int(misses.sum())
    good_flagged = int((mask & winners).sum())
    kept = frame[~mask]
    kept_correct = int(kept["correct"].sum()) if len(kept) else 0
    kept_acc = (100.0 * kept_correct / len(kept)) if len(kept) else float("nan")
    capture = (100.0 * caught / total_misses) if total_misses else float("nan")
    false_warn = (100.0 * good_flagged / int(winners.sum())) if int(winners.sum()) else float("nan")
    print(f"{label:<34} | flagged={flagged:3d} | misses_caught={caught}/{total_misses} | capture={capture:5.1f}% | good_flagged={good_flagged:3d} | false_warn={false_warn:5.1f}% | kept={len(kept):3d} | kept_acc={kept_acc:5.1f}%")

print("=== FULL CLEAN SAMPLE ===")
score("EARLY: 420s fair drop >= 15pt", d["early_warning"], d)
score("LATE: flip with <=1.5m left", d["late_flip_le_1p5m"], d)
score("LATE: distance < -$25 <=3m", d["late_neg25_le_3m"], d)
score("COMBINED: EARLY OR late flip", d["combined_early_or_lateflip"], d)
score("COMBINED: EARLY OR late -$25", d["combined_early_or_neg25"], d)
print()

# Chronological last 40% holdout.
cut = max(1, int(math.floor(len(d) * 0.60)))
hold = d.iloc[cut:].copy()
print("=== CHRONOLOGICAL HOLDOUT: LAST 40% OF CLEAN CALLS ===")
print(f"Holdout CLEAN calls: {len(hold)}")
print(f"Holdout winners: {int(hold['correct'].sum())}")
print(f"Holdout misses: {int((~hold['correct']).sum())}")
score("EARLY: 420s fair drop >= 15pt", hold["early_warning"], hold)
score("LATE: flip with <=1.5m left", hold["late_flip_le_1p5m"], hold)
score("LATE: distance < -$25 <=3m", hold["late_neg25_le_3m"], hold)
score("COMBINED: EARLY OR late flip", hold["combined_early_or_lateflip"], hold)
score("COMBINED: EARLY OR late -$25", hold["combined_early_or_neg25"], hold)
print()

print("=== CLEAN MISSES ===")
miss_cols = [
    "ticker", "call_time", "call_side", "initial_fair", "initial_signed_distance",
    "early_420s_worst_fair_drop", "early_warning",
    "late_flip_le_1p5m", "late_neg25_le_3m",
    "first_flip_remaining_min",
    "min_signed_distance_final_1p5m", "min_signed_distance_final_3m",
    "combined_early_or_lateflip", "combined_early_or_neg25"
]
print(d.loc[~d["correct"], miss_cols].to_string(index=False))
print()

d.to_csv(OUT, index=False)
print(f"Saved: {OUT}")
print("=== VALIDATION COMPLETE ===")
print("Research only. No rule installed.")
