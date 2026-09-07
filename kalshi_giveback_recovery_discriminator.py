from pathlib import Path
import pandas as pd
import numpy as np
import csv

DETAILS = Path("kalshi_strong_confirmation_giveback_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI GIVEBACK RECOVERY DISCRIMINATOR ===")
print("Purpose: compare false-warning winners vs true late-reversal losses.")
print("Focus: what recovery behavior separates a winner after a big giveback from a true failure?")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not DETAILS.exists():
    raise SystemExit("Missing kalshi_strong_confirmation_giveback_details.csv")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

d = pd.read_csv(DETAILS)
d["correct"] = d["correct"].astype(str).str.lower().map({"true":True,"false":False})

# Reproduce the clean candidate from the prior test:
# fair-value giveback >= 10 percentage points.
flagged = d[d["fair_giveback"] >= 0.10].copy()

print("Flagged by fair giveback >= 10pt:", len(flagged))
print("Flagged winners:", int(flagged["correct"].sum()))
print("Flagged losses:", int((~flagged["correct"]).sum()))
print()

def pick(cols, names):
    for n in names:
        for c in cols:
            if str(c).lower() == n.lower():
                return c
    for n in names:
        for c in cols:
            if n.lower() in str(c).lower():
                return c
    return None

def headerish(row):
    low=[str(x).lower() for x in row]
    keys=["ticker","timestamp","distance","fair","ask","remaining"]
    return sum(any(k in x for k in keys) for x in low) >= 2

rows=[]; header=None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
    for row in csv.reader(f):
        if not row:
            continue
        if headerish(row):
            header=[str(x).strip() for x in row]
            continue
        if header is None:
            continue
        row=row+[""]*max(0,len(header)-len(row))
        rows.append(dict(zip(header,row[:len(header)])))

live=pd.DataFrame(rows)

tc=pick(live.columns,["ticker","contract_ticker","market_ticker"])
ts=pick(live.columns,["timestamp_utc","timestamp","snapshot_time"])
dc=pick(live.columns,["distance_target","distance_from_target","distance"])
fu=pick(live.columns,["fair_up"])
fd=pick(live.columns,["fair_down"])
ua=pick(live.columns,["up_ask"])
da=pick(live.columns,["down_ask"])
rm=pick(live.columns,["remaining_min","time_left","minutes_left"])
ps=pick(live.columns,["preferred_side","current_target_side"])
st=pick(live.columns,["signal_status","status"])

for c in [dc,fu,fd,ua,da,rm]:
    if c:
        live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

# We need call time and initial state. Pull from Layer A forward results.
base_path = Path("kalshi_layer_a_forward_only_results.csv")
if not base_path.exists():
    raise SystemExit("Missing kalshi_layer_a_forward_only_results.csv")

base = pd.read_csv(base_path)
base["call_time"] = pd.to_datetime(base["call_time"], utc=True, errors="coerce")
base["correct"] = base["correct"].astype(str).str.lower().map({"true":True,"false":False})

def path_for(call):
    ticker=str(call["ticker"])
    side=str(call["call_side"]).upper()
    t0=call["call_time"]
    init_dist=float(call["initial_distance"])
    init_signed=init_dist if side=="UP" else -init_dist
    init_fair=float(call["initial_fair"])

    q=live[(live[tc]==ticker)&(live[ts]>=t0)].sort_values(ts).copy()
    out=[]
    for _,nr in q.iterrows():
        sec=(nr[ts]-t0).total_seconds()
        if sec<0:
            continue
        signed=float(nr[dc]) if side=="UP" else -float(nr[dc])
        fair=(float(nr[fu]) if side=="UP" and fu and pd.notna(nr[fu]) else
              float(nr[fd]) if side=="DOWN" and fd and pd.notna(nr[fd]) else np.nan)
        ask=(float(nr[ua]) if side=="UP" and ua and pd.notna(nr[ua]) else
             float(nr[da]) if side=="DOWN" and da and pd.notna(nr[da]) else np.nan)
        out.append({
            "ticker":ticker,
            "correct":bool(call["correct"]),
            "call_side":side,
            "timestamp":nr[ts],
            "min_from_call":sec/60.0,
            "remaining_min":float(nr[rm]) if rm and pd.notna(nr[rm]) else np.nan,
            "distance_gain":signed-init_signed,
            "fair_gain":fair-init_fair if pd.notna(fair) else np.nan,
            "ask_change":ask-init_fair if pd.notna(ask) else np.nan,
            "preferred_side":nr[ps] if ps else "",
            "signal_status":nr[st] if st else "",
        })
    return pd.DataFrame(out)

all_paths=[]
summary=[]

for ticker in flagged["ticker"].astype(str):
    br=base[base["ticker"].astype(str)==ticker]
    if br.empty:
        continue
    call=br.iloc[0]
    p=path_for(call)
    if p.empty:
        continue

    # Define the collapse point as the row with worst fair gain after 6m.
    p6=p[p["min_from_call"]>=6].copy()
    if p6.empty:
        continue

    collapse_idx=p6["fair_gain"].idxmin()
    collapse=p.loc[collapse_idx]
    collapse_min=float(collapse["min_from_call"])
    collapse_dist=float(collapse["distance_gain"])
    collapse_fair=float(collapse["fair_gain"])

    after=p[p["min_from_call"]>collapse_min].copy()

    best_dist_after=float(after["distance_gain"].max()) if len(after) else np.nan
    best_fair_after=float(after["fair_gain"].max()) if len(after) and after["fair_gain"].notna().any() else np.nan

    distance_recovery=(best_dist_after-collapse_dist) if pd.notna(best_dist_after) else np.nan
    fair_recovery=(best_fair_after-collapse_fair) if pd.notna(best_fair_after) else np.nan

    # Did it reclaim key levels after collapse?
    reclaimed_positive_distance=bool((after["distance_gain"]>0).any()) if len(after) else False
    reclaimed_positive_fair=bool((after["fair_gain"]>0).any()) if len(after) else False
    reclaimed_5pt_fair=bool((after["fair_gain"]>=0.05).any()) if len(after) else False
    reclaimed_10pt_fair=bool((after["fair_gain"]>=0.10).any()) if len(after) else False

    # First recovery timestamps after collapse
    def first_min(mask):
        h=after[mask]
        return float(h.iloc[0]["min_from_call"]) if len(h) else np.nan

    first_dist_pos=first_min(after["distance_gain"]>0) if len(after) else np.nan
    first_fair_pos=first_min(after["fair_gain"]>0) if len(after) else np.nan
    first_fair5=first_min(after["fair_gain"]>=0.05) if len(after) else np.nan
    first_fair10=first_min(after["fair_gain"]>=0.10) if len(after) else np.nan

    summary.append({
        "ticker":ticker,
        "correct":bool(call["correct"]),
        "call_side":str(call["call_side"]).upper(),
        "initial_fair":float(call["initial_fair"]),
        "collapse_min":collapse_min,
        "collapse_remaining_min":float(collapse["remaining_min"]) if pd.notna(collapse["remaining_min"]) else np.nan,
        "collapse_distance_gain":collapse_dist,
        "collapse_fair_gain":collapse_fair,
        "best_distance_after":best_dist_after,
        "best_fair_after":best_fair_after,
        "distance_recovery_after_collapse":distance_recovery,
        "fair_recovery_after_collapse":fair_recovery,
        "reclaimed_positive_distance":reclaimed_positive_distance,
        "reclaimed_positive_fair":reclaimed_positive_fair,
        "reclaimed_5pt_fair":reclaimed_5pt_fair,
        "reclaimed_10pt_fair":reclaimed_10pt_fair,
        "first_positive_distance_min":first_dist_pos,
        "first_positive_fair_min":first_fair_pos,
        "first_5pt_fair_min":first_fair5,
        "first_10pt_fair_min":first_fair10,
    })

    p["collapse_point"]=False
    p.loc[collapse_idx,"collapse_point"]=True
    all_paths.append(p)

s=pd.DataFrame(summary)

print("=== FLAGGED CASE SUMMARY ===")
if len(s):
    print(s.to_string(index=False))
else:
    print("No cases available.")

print()
print("=== WINNER VS LOSS RECOVERY COMPARISON ===")
if len(s):
    for col in [
        "collapse_min","collapse_remaining_min",
        "collapse_distance_gain","collapse_fair_gain",
        "distance_recovery_after_collapse","fair_recovery_after_collapse",
        "first_positive_distance_min","first_positive_fair_min",
        "first_5pt_fair_min","first_10pt_fair_min"
    ]:
        w=pd.to_numeric(s.loc[s.correct,col],errors="coerce").dropna()
        m=pd.to_numeric(s.loc[~s.correct,col],errors="coerce").dropna()
        print(
            f"{col:34s} | winners={list(w.round(6))} | losses={list(m.round(6))}"
        )

    for col in [
        "reclaimed_positive_distance",
        "reclaimed_positive_fair",
        "reclaimed_5pt_fair",
        "reclaimed_10pt_fair"
    ]:
        print(
            f"{col:34s} | winners={list(s.loc[s.correct,col])} | losses={list(s.loc[~s.correct,col])}"
        )

print()
print("=== FULL PATHS FOR FLAGGED CASES ===")
if all_paths:
    paths=pd.concat(all_paths,ignore_index=True)
    cols=["ticker","correct","timestamp","min_from_call","remaining_min","distance_gain","fair_gain","ask_change","preferred_side","signal_status","collapse_point"]
    print(paths[cols].to_string(index=False))
    paths.to_csv("kalshi_giveback_recovery_paths.csv",index=False)
else:
    paths=pd.DataFrame()

s.to_csv("kalshi_giveback_recovery_discriminator.csv",index=False)

print()
print("Saved: kalshi_giveback_recovery_discriminator.csv")
print("Saved: kalshi_giveback_recovery_paths.csv")
print("=== RECOVERY DISCRIMINATOR COMPLETE ===")
print("Research only. No rule installed.")
