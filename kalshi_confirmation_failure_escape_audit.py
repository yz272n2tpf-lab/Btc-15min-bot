from pathlib import Path
import pandas as pd
import numpy as np
import csv

RESULTS = Path("kalshi_confirmation_failure_forward_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== CONFIRMATION-FAILURE ESCAPE AUDIT ===")
print("Research only. No thresholds, bot.py, scalp, or order changes.")

if not RESULTS.exists():
    raise SystemExit("Missing kalshi_confirmation_failure_forward_results.csv")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

r = pd.read_csv(RESULTS)
r["call_time"] = pd.to_datetime(r["call_time"], utc=True, errors="coerce")
for c in ["correct","confirmation_failure_warning"]:
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
    keys=["ticker","timestamp","distance","fair","ask"]
    return sum(any(k in x for k in keys) for x in low) >= 2

rows=[]; header=None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
    for row in csv.reader(f):
        if not row: continue
        if headerish(row):
            header=[str(x).strip() for x in row]; continue
        if header is None: continue
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

for c in [dc,fu,fd,ua,da]:
    if c: live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

def nearest(df,t):
    if df.empty: return None
    d=(df[ts]-t).abs().dt.total_seconds()
    i=d.idxmin()
    return None if float(d.loc[i])>45 else df.loc[i]

out=[]
for _,call in r.iterrows():
    ticker=str(call["ticker"]); side=str(call["call_side"]).upper(); t0=call["call_time"]
    init_dist=float(call["initial_distance"])
    init_signed=init_dist if side=="UP" else -init_dist
    init_fair=float(call["initial_fair"])
    q=live[(live[tc]==ticker)&(live[ts]>=t0)].sort_values(ts)
    rec={"ticker":ticker,"correct":bool(call["correct"]),"warning":bool(call["confirmation_failure_warning"]),
         "call_side":side,"initial_fair":init_fair,"initial_signed_distance":init_signed}
    for m in range(1,7):
        nr=nearest(q,t0+pd.Timedelta(minutes=m))
        if nr is None:
            rec[f"{m}m_distance_gain"]=np.nan; rec[f"{m}m_fair_gain"]=np.nan; rec[f"{m}m_ask_change"]=np.nan
            continue
        signed=float(nr[dc]) if side=="UP" else -float(nr[dc])
        rec[f"{m}m_distance_gain"]=signed-init_signed
        fair=(float(nr[fu]) if side=="UP" and fu and pd.notna(nr[fu]) else
              float(nr[fd]) if side=="DOWN" and fd and pd.notna(nr[fd]) else np.nan)
        ask=(float(nr[ua]) if side=="UP" and ua and pd.notna(nr[ua]) else
             float(nr[da]) if side=="DOWN" and da and pd.notna(nr[da]) else np.nan)
        rec[f"{m}m_fair_gain"]=fair-init_fair if pd.notna(fair) else np.nan
        rec[f"{m}m_ask_change"]=ask-init_fair if pd.notna(ask) else np.nan
    out.append(rec)

d=pd.DataFrame(out)
print(f"Fresh CLEAN calls: {len(d)}")
print(f"Winners: {int(d.correct.sum())} | Misses: {int((~d.correct).sum())}")

print("\n=== FRESH CLEAN MISSES ===")
print(d[~d.correct].to_string(index=False))

print("\n=== WINNER VS MISS SUMMARY ===")
w=d[d.correct]; m=d[~d.correct]
for minute in range(1,7):
    for suffix in ["distance_gain","fair_gain","ask_change"]:
        col=f"{minute}m_{suffix}"
        ws=pd.to_numeric(w[col],errors="coerce").dropna()
        ms=pd.to_numeric(m[col],errors="coerce").dropna()
        print(f"{col:18s} | winners med={ws.median():8.4f} min={ws.min():8.4f} max={ws.max():8.4f} | misses={list(ms.round(6))}")

print("\n=== CAUGHT VS ESCAPED MISS ===")
print("CAUGHT:")
print(m[m.warning].to_string(index=False))
print("\nESCAPED:")
print(m[~m.warning].to_string(index=False))

d.to_csv("kalshi_confirmation_failure_escape_audit_details.csv",index=False)
print("\nSaved: kalshi_confirmation_failure_escape_audit_details.csv")
print("=== AUDIT COMPLETE ===")
