from pathlib import Path
import pandas as pd
import numpy as np

DETAILS = Path("kalshi_official_truth_layer_a_rescore_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OUT = Path("kalshi_official_truth_clean_miss_discriminator.csv")

print("=== OFFICIAL-TRUTH CLEAN-MISS DISCRIMINATOR ===")
print("Purpose: compare Layer A CLEAN winners vs CLEAN misses using only information available after the qualifying call.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

def read_mixed_csv(path):
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.read_csv(path, engine="python", on_bad_lines="skip")

def pick(cols, candidates):
    lower = {str(c).lower(): c for c in cols}
    for x in candidates:
        if x.lower() in lower:
            return lower[x.lower()]
    for c in cols:
        cl = str(c).lower()
        for x in candidates:
            if x.lower() in cl:
                return c
    return None

if not DETAILS.exists():
    raise SystemExit(f"Missing {DETAILS}")
if not LIVE.exists():
    raise SystemExit(f"Missing {LIVE}")

d = read_mixed_csv(DETAILS)
live = read_mixed_csv(LIVE)

ticker_col = pick(d.columns, ["ticker"])
state_col = pick(d.columns, ["state"])
correct_col = pick(d.columns, ["correct"])
call_side_col = pick(d.columns, ["call_side"])
call_time_col = pick(d.columns, ["ts","call_time","timestamp"])
fair_col = pick(d.columns, ["fair_pref_num","initial_fair","fair_preferred"])
rem_col = pick(d.columns, ["remaining_num","initial_remaining","remaining_min"])
init_dist_col = pick(d.columns, ["initial_signed_distance","initial_distance"])

need = {
    "ticker": ticker_col, "state": state_col, "correct": correct_col,
    "call_side": call_side_col, "call_time": call_time_col
}
missing = [k for k,v in need.items() if v is None]
if missing:
    raise SystemExit(f"Missing required detail columns: {missing}\nColumns: {list(d.columns)}")

# normalize correctness
def to_bool(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true","1","yes","y"):
        return True
    if s in ("false","0","no","n"):
        return False
    return np.nan

d["_correct"] = d[correct_col].map(to_bool)
d["_state"] = d[state_col].astype(str).str.upper()
clean = d[d["_state"].str.contains("CLEAN", na=False)].copy()
clean = clean[clean["_correct"].notna()].copy()

print(f"CLEAN sample: {len(clean)}")
print(f"Winners: {int(clean['_correct'].sum())}")
print(f"Misses: {int((~clean['_correct']).sum())}")
print()

lt = pick(live.columns, ["ticker"])
lts = pick(live.columns, ["timestamp_utc","timestamp"])
ldist = pick(live.columns, ["distance_target","distance_from_target","distance"])
lpref = pick(live.columns, ["preferred_side","current_target_side","current_side"])
lfup = pick(live.columns, ["fair_up"])
lfdn = pick(live.columns, ["fair_down"])
lfpref = pick(live.columns, ["fair_preferred"])
lask = pick(live.columns, ["preferred_ask"])
lupask = pick(live.columns, ["up_ask"])
ldnask = pick(live.columns, ["down_ask"])
lstatus = pick(live.columns, ["signal_status"])

if None in (lt,lts,ldist):
    raise SystemExit(f"Live log missing ticker/timestamp/distance columns.\nColumns: {list(live.columns)}")

live[lts] = pd.to_datetime(live[lts], utc=True, errors="coerce")
live[ldist] = pd.to_numeric(live[ldist], errors="coerce")

def side_fair(row, side):
    if lfpref and pd.notna(row.get(lfpref)):
        # fair_preferred is safe only if preferred side equals call side
        if lpref and str(row.get(lpref)).upper() == side:
            return pd.to_numeric(row.get(lfpref), errors="coerce")
    if side == "UP" and lfup:
        return pd.to_numeric(row.get(lfup), errors="coerce")
    if side == "DOWN" and lfdn:
        return pd.to_numeric(row.get(lfdn), errors="coerce")
    return np.nan

def side_ask(row, side):
    if lask and lpref and str(row.get(lpref)).upper() == side:
        return pd.to_numeric(row.get(lask), errors="coerce")
    if side == "UP" and lupask:
        return pd.to_numeric(row.get(lupask), errors="coerce")
    if side == "DOWN" and ldnask:
        return pd.to_numeric(row.get(ldnask), errors="coerce")
    return np.nan

checkpoints = [30,60,90,120,180,240,300,360,420,480]
rows = []

for _, r in clean.iterrows():
    ticker = str(r[ticker_col])
    side = str(r[call_side_col]).upper().strip()
    ct = pd.to_datetime(r[call_time_col], utc=True, errors="coerce")
    if pd.isna(ct):
        continue

    q = live[live[lt].astype(str) == ticker].copy().sort_values(lts)
    q = q[q[lts].notna() & q[ldist].notna()]
    if q.empty:
        continue

    q["_sec"] = (q[lts] - ct).dt.total_seconds()
    q = q[(q["_sec"] >= -5) & (q["_sec"] <= 540)]
    if q.empty:
        continue

    # signed distance in direction of original call
    q["_signed"] = q[ldist] if side == "UP" else -q[ldist]

    # anchor nearest to call
    aidx = q["_sec"].abs().idxmin()
    a = q.loc[aidx]
    init_signed = float(a["_signed"])
    init_fair = side_fair(a, side)
    init_ask = side_ask(a, side)

    out = {
        "ticker": ticker,
        "correct": bool(r["_correct"]),
        "call_side": side,
        "call_time": ct,
        "initial_signed_distance": init_signed,
        "initial_fair": init_fair,
        "initial_ask": init_ask,
    }

    if fair_col: out["rescore_initial_fair"] = pd.to_numeric(r[fair_col], errors="coerce")
    if rem_col: out["rescore_remaining_min"] = pd.to_numeric(r[rem_col], errors="coerce")
    if init_dist_col: out["rescore_initial_signed_distance"] = pd.to_numeric(r[init_dist_col], errors="coerce")

    for sec in checkpoints:
        w = q[(q["_sec"] >= 0) & (q["_sec"] <= sec)]
        if w.empty:
            out[f"{sec}s_worst_distance_drop"] = np.nan
            out[f"{sec}s_worst_fair_drop"] = np.nan
            out[f"{sec}s_worst_ask_change"] = np.nan
            continue

        # maximum deterioration from initial call-side signed distance
        worst_signed = float(w["_signed"].min())
        out[f"{sec}s_worst_distance_drop"] = max(0.0, init_signed - worst_signed)

        fairs = w.apply(lambda rr: side_fair(rr, side), axis=1)
        asks = w.apply(lambda rr: side_ask(rr, side), axis=1)

        if pd.notna(init_fair) and fairs.notna().any():
            out[f"{sec}s_worst_fair_drop"] = max(0.0, float(init_fair) - float(fairs.min()))
        else:
            out[f"{sec}s_worst_fair_drop"] = np.nan

        if pd.notna(init_ask) and asks.notna().any():
            out[f"{sec}s_worst_ask_change"] = float(asks.min()) - float(init_ask)
        else:
            out[f"{sec}s_worst_ask_change"] = np.nan

    rows.append(out)

x = pd.DataFrame(rows)
if x.empty:
    raise SystemExit("No CLEAN calls could be matched to live trajectories.")

print("=== CLEAN MISSES ===")
miss = x[~x["correct"]].copy()
show_cols = ["ticker","call_side","initial_fair","initial_signed_distance",
             "30s_worst_distance_drop","60s_worst_distance_drop","120s_worst_distance_drop",
             "180s_worst_distance_drop","240s_worst_distance_drop","300s_worst_distance_drop",
             "360s_worst_distance_drop","420s_worst_distance_drop",
             "120s_worst_fair_drop","240s_worst_fair_drop","360s_worst_fair_drop"]
show_cols = [c for c in show_cols if c in x.columns]
print(miss[show_cols].to_string(index=False))
print()

print("=== WINNER VS MISS SUMMARY ===")
for sec in checkpoints:
    for metric in ("worst_distance_drop","worst_fair_drop"):
        c = f"{sec}s_{metric}"
        if c not in x.columns: 
            continue
        wv = x.loc[x["correct"], c].dropna()
        mv = x.loc[~x["correct"], c].dropna()
        if len(wv) == 0 and len(mv) == 0:
            continue
        wtxt = f"winners n={len(wv)} med={wv.median():.3f} min={wv.min():.3f} max={wv.max():.3f}" if len(wv) else "winners n=0"
        mtxt = f"misses={list(np.round(mv.values,3))}" if len(mv) else "misses=[]"
        print(f"{c:28s} | {wtxt} | {mtxt}")
print()

# diagnostic-only scans, intentionally broad. These DO NOT install rules.
candidates = []
for sec in [30,60,90,120,180,240,300,360,420]:
    dc = f"{sec}s_worst_distance_drop"
    fc = f"{sec}s_worst_fair_drop"
    if dc in x:
        for th in [25,40,50,75,100,125,150]:
            candidates.append((f"{sec}s dist_drop >= ${th}", x[dc] >= th))
    if fc in x:
        for th in [0.05,0.075,0.10,0.15,0.20]:
            candidates.append((f"{sec}s fair_drop >= {th:.3f}", x[fc] >= th))

scans = []
total_misses = int((~x["correct"]).sum())
for name, flag in candidates:
    flag = flag.fillna(False)
    flagged = x[flag]
    caught = int((~flagged["correct"]).sum())
    good = int(flagged["correct"].sum())
    kept = x[~flag]
    kept_acc = float(kept["correct"].mean()) if len(kept) else np.nan
    scans.append({
        "rule": name,
        "flagged": int(flag.sum()),
        "misses_caught": caught,
        "total_misses": total_misses,
        "good_flagged": good,
        "kept": len(kept),
        "kept_accuracy": kept_acc
    })

s = pd.DataFrame(scans)
s["capture"] = np.where(s["total_misses"]>0, s["misses_caught"]/s["total_misses"], np.nan)
s = s.sort_values(["misses_caught","good_flagged","flagged"], ascending=[False,True,True])

print("=== TOP DIAGNOSTIC CANDIDATES ONLY ===")
print(s.head(25).to_string(index=False, formatters={
    "kept_accuracy": lambda v: f"{v*100:.1f}%" if pd.notna(v) else "nan",
    "capture": lambda v: f"{v*100:.1f}%" if pd.notna(v) else "nan",
}))
print()
print("IMPORTANT: diagnostic only. No rule installed.")
x.to_csv(OUT, index=False)
print(f"Saved: {OUT}")
print("=== DISCRIMINATOR COMPLETE ===")
