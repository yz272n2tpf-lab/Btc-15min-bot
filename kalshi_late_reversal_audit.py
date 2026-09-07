from pathlib import Path
import pandas as pd
import numpy as np
import csv

RESULTS = Path("kalshi_confirmation_failure_forward_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

TARGET = "KXBTC15M-26AUG270615-15"

print("=== KALSHI LATE-REVERSAL AUDIT ===")
print("Purpose: study a CLEAN call that genuinely confirmed, then later lost.")
print("Target:", TARGET)
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not RESULTS.exists():
    raise SystemExit("Missing kalshi_confirmation_failure_forward_results.csv")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

r = pd.read_csv(RESULTS)
r["call_time"] = pd.to_datetime(r["call_time"], utc=True, errors="coerce")
for c in ["correct","confirmation_failure_warning"]:
    if c in r.columns:
        r[c] = r[c].astype(str).str.lower().map({"true":True,"false":False})

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
    for line_no,row in enumerate(csv.reader(f),1):
        if not row: continue
        if headerish(row):
            header=[str(x).strip() for x in row]; continue
        if header is None: continue
        row=row+[""]*max(0,len(header)-len(row))
        rec=dict(zip(header,row[:len(header)]))
        rec["_source_line"]=line_no
        rows.append(rec)

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
status=pick(live.columns,["signal_status","status"])

for c in [dc,fu,fd,ua,da,rm]:
    if c:
        live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

def nearest(df,t,tolerance=45):
    if df.empty: return None
    d=(df[ts]-t).abs().dt.total_seconds()
    i=d.idxmin()
    return None if float(d.loc[i])>tolerance else df.loc[i]

def path_for(call):
    ticker=str(call["ticker"])
    side=str(call["call_side"]).upper()
    t0=call["call_time"]
    init_dist=float(call["initial_distance"])
    init_signed=init_dist if side=="UP" else -init_dist
    init_fair=float(call["initial_fair"])
    q=live[(live[tc]==ticker)&(live[ts]>=t0)].sort_values(ts).copy()

    path=[]
    for _,nr in q.iterrows():
        sec=(nr[ts]-t0).total_seconds()
        if sec < 0: 
            continue
        signed=float(nr[dc]) if side=="UP" else -float(nr[dc])
        fair=(float(nr[fu]) if side=="UP" and fu and pd.notna(nr[fu]) else
              float(nr[fd]) if side=="DOWN" and fd and pd.notna(nr[fd]) else np.nan)
        ask=(float(nr[ua]) if side=="UP" and ua and pd.notna(nr[ua]) else
             float(nr[da]) if side=="DOWN" and da and pd.notna(nr[da]) else np.nan)
        path.append({
            "ticker":ticker,
            "correct":bool(call["correct"]),
            "call_side":side,
            "sec_from_call":sec,
            "min_from_call":sec/60.0,
            "timestamp":nr[ts],
            "remaining_min": float(nr[rm]) if rm and pd.notna(nr[rm]) else np.nan,
            "signed_distance":signed,
            "distance_gain":signed-init_signed,
            "fair":fair,
            "fair_gain":fair-init_fair if pd.notna(fair) else np.nan,
            "ask":ask,
            "ask_change":ask-init_fair if pd.notna(ask) else np.nan,
            "preferred_side": nr[ps] if ps else "",
            "signal_status": nr[status] if status else "",
        })
    return pd.DataFrame(path)

target_row = r[r["ticker"].astype(str)==TARGET]
if target_row.empty:
    raise SystemExit("Target not found in confirmation forward results.")
target_row = target_row.iloc[0]

tp = path_for(target_row)

print("=== TARGET FULL POST-CALL PATH ===")
if tp.empty:
    print("No live rows found.")
else:
    show_cols=["timestamp","sec_from_call","remaining_min","signed_distance","distance_gain","fair","fair_gain","ask","ask_change","preferred_side","signal_status"]
    print(tp[show_cols].to_string(index=False))

# Identify strongly-confirmed CLEAN winners:
# By 6m, distance gain >= +40 and fair gain >= +0.10, and correct=True.
comparison=[]
for _,call in r.iterrows():
    if not bool(call["correct"]):
        continue
    p=path_for(call)
    if p.empty:
        continue
    nr=nearest(p.rename(columns={"timestamp":ts}), call["call_time"]+pd.Timedelta(minutes=6), 45) if False else None
    # use direct nearest on original path based on min_from_call
    d=(p["min_from_call"]-6).abs()
    if len(d)==0:
        continue
    i=d.idxmin()
    if abs(float(p.loc[i,"min_from_call"])-6)>0.75:
        continue
    dg=float(p.loc[i,"distance_gain"])
    fg=float(p.loc[i,"fair_gain"]) if pd.notna(p.loc[i,"fair_gain"]) else np.nan
    if dg>=40 and pd.notna(fg) and fg>=0.10:
        comparison.append((call,p))

print()
print("Strongly-confirmed winner comparison set:", len(comparison))

def checkpoint(p, minute):
    d=(p["min_from_call"]-minute).abs()
    if len(d)==0: return None
    i=d.idxmin()
    if abs(float(p.loc[i,"min_from_call"])-minute)>0.75: return None
    return p.loc[i]

rows_out=[]

# target + winners
all_cases=[(target_row,tp,False)] + [(c,p,True) for c,p in comparison]

for call,p,is_winner in all_cases:
    if p.empty: 
        continue
    rec={
        "ticker":str(call["ticker"]),
        "correct":bool(call["correct"]),
        "call_side":str(call["call_side"]).upper(),
        "initial_fair":float(call["initial_fair"]),
        "initial_distance":float(call["initial_distance"]),
    }
    for minute in [4,5,6,7,8,9,10]:
        cp=checkpoint(p,minute)
        if cp is None:
            rec[f"{minute}m_distance_gain"]=np.nan
            rec[f"{minute}m_fair_gain"]=np.nan
            continue
        rec[f"{minute}m_distance_gain"]=cp["distance_gain"]
        rec[f"{minute}m_fair_gain"]=cp["fair_gain"]

    # Reversal metrics after the 6m checkpoint:
    c6=checkpoint(p,6)
    if c6 is not None:
        after6=p[p["min_from_call"]>=float(c6["min_from_call"])].copy()
        rec["gain6"]=float(c6["distance_gain"])
        rec["fair6"]=float(c6["fair_gain"]) if pd.notna(c6["fair_gain"]) else np.nan
        rec["worst_distance_gain_after6"]=float(after6["distance_gain"].min()) if len(after6) else np.nan
        rec["worst_fair_gain_after6"]=float(after6["fair_gain"].min()) if len(after6) else np.nan
        rec["distance_reversal_from_6m_peak"]=rec["gain6"]-rec["worst_distance_gain_after6"]
        rec["fair_reversal_from_6m"]=rec["fair6"]-rec["worst_fair_gain_after6"] if pd.notna(rec["fair6"]) else np.nan

        # first time it gave back 50% of 6m distance gain
        threshold=rec["gain6"]*0.5
        hit=after6[after6["distance_gain"]<=threshold]
        rec["first_50pct_giveback_min"]=float(hit.iloc[0]["min_from_call"]) if len(hit) else np.nan

        # first time fair gain dropped below +5pt
        hit2=after6[after6["fair_gain"]<0.05]
        rec["first_fair_below_5pt_min"]=float(hit2.iloc[0]["min_from_call"]) if len(hit2) else np.nan
    rows_out.append(rec)

summary=pd.DataFrame(rows_out)

print()
print("=== TARGET VS STRONGLY-CONFIRMED WINNERS ===")
if not summary.empty:
    print(summary.to_string(index=False))

print()
print("=== GIVEBACK SUMMARY ===")
if len(summary):
    winners=summary[summary["correct"]==True]
    miss=summary[summary["correct"]==False]
    for col in ["distance_reversal_from_6m_peak","fair_reversal_from_6m","first_50pct_giveback_min","first_fair_below_5pt_min"]:
        ws=pd.to_numeric(winners[col],errors="coerce").dropna()
        ms=pd.to_numeric(miss[col],errors="coerce").dropna()
        print(f"{col:30s} | winners n={len(ws):2d} med={ws.median() if len(ws) else np.nan:8.3f} "
              f"min={ws.min() if len(ws) else np.nan:8.3f} max={ws.max() if len(ws) else np.nan:8.3f} "
              f"| target={list(ms.round(6))}")

tp.to_csv("kalshi_late_reversal_target_path.csv",index=False)
summary.to_csv("kalshi_late_reversal_audit_details.csv",index=False)

print()
print("Saved: kalshi_late_reversal_target_path.csv")
print("Saved: kalshi_late_reversal_audit_details.csv")
print("=== LATE-REVERSAL AUDIT COMPLETE ===")
print("Research only. No rule installed.")
