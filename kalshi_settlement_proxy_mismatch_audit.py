from pathlib import Path
import pandas as pd, numpy as np, csv

LIVE=Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL=Path("kalshi_official_settlement_check.csv")

print("=== KALSHI SETTLEMENT-PROXY MISMATCH AUDIT ===")
print("Measures Coinbase late-window proxies vs official Kalshi outcome.")
print("Does NOT recreate true BRTI.")
print("No bot.py/scalp/order changes.\n")

def pick(cols,names):
    for n in names:
        for c in cols:
            if str(c).lower()==n.lower(): return c
    for n in names:
        for c in cols:
            if n.lower() in str(c).lower(): return c
    return None

def headerish(row):
    low=[str(x).lower() for x in row]
    keys=["ticker","timestamp","distance","remaining","coinbase","target"]
    return sum(any(k in x for k in keys) for x in low)>=2

rows=[]; header=None
with LIVE.open("r",newline="",encoding="utf-8-sig",errors="replace") as f:
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
rm=pick(live.columns,["remaining_min","time_left","minutes_left"])
dist=pick(live.columns,["distance_target","distance_from_target","distance"])
coin=pick(live.columns,["coinbase_close","coinbase_price","btc_price"])
target=pick(live.columns,["target","target_price","strike","start_price"])

for c in [rm,dist,coin,target]:
    if c: live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

official=pd.read_csv(OFFICIAL)
ot=pick(official.columns,["ticker","contract_ticker","market_ticker"])
ores=pick(official.columns,["result","official_result","winner","settlement_result"])

def norm(x):
    s=str(x).upper().strip()
    if s in ["UP","YES","Y","TRUE","1"]: return "UP"
    if s in ["DOWN","NO","N","FALSE","0"]: return "DOWN"
    return ""
official["_official_side"]=official[ores].apply(norm)
official[ot]=official[ot].astype(str)
official=official[official["_official_side"].isin(["UP","DOWN"])].drop_duplicates(ot,keep="last")

def side(x):
    if pd.isna(x): return ""
    return "UP" if x>0 else "DOWN" if x<0 else "TIE"

recs=[]
for ticker,q in live.groupby(tc):
    oq=official[official[ot]==ticker]
    if oq.empty: continue
    official_side=oq.iloc[-1]["_official_side"]
    q=q.sort_values(ts)
    q=q[q[rm].notna() & q[dist].notna()]
    if q.empty: continue
    last=q.iloc[-1]
    f60=q[(q[rm]>=0)&(q[rm]<=1.0)]
    f90=q[(q[rm]>=0)&(q[rm]<=1.5)]
    f120=q[(q[rm]>=0)&(q[rm]<=2.0)]
    q1=q.assign(_err=(q[rm]-1.0).abs())
    one=q1.loc[q1["_err"].idxmin()]
    m60=float(f60[dist].mean()) if len(f60) else np.nan
    m90=float(f90[dist].mean()) if len(f90) else np.nan
    m120=float(f120[dist].mean()) if len(f120) else np.nan
    recs.append({
        "ticker":ticker,"official_side":official_side,
        "last_remaining_min":float(last[rm]),"last_distance":float(last[dist]),
        "last_side":side(float(last[dist])),"last_matches_official":side(float(last[dist]))==official_side,
        "one_min_remaining":float(one[rm]),"one_min_distance":float(one[dist]),
        "one_min_side":side(float(one[dist])),"one_min_matches_official":side(float(one[dist]))==official_side,
        "final60_n":len(f60),"final60_mean_distance":m60,"final60_side":side(m60),
        "final60_matches_official":(side(m60)==official_side) if side(m60) else np.nan,
        "final90_n":len(f90),"final90_mean_distance":m90,"final90_side":side(m90),
        "final90_matches_official":(side(m90)==official_side) if side(m90) else np.nan,
        "final120_n":len(f120),"final120_mean_distance":m120,"final120_side":side(m120),
        "final120_matches_official":(side(m120)==official_side) if side(m120) else np.nan,
    })

d=pd.DataFrame(recs)
print("Usable settled contracts:",len(d))

def report(label,col):
    v=d[col].dropna()
    if len(v):
        print(f"{label:28s} n={len(v):4d} agreement={v.mean():.1%} disagreement={(1-v.mean()):.1%}")

print("\n=== AGREEMENT WITH OFFICIAL KALSHI OUTCOME ===")
report("Last Coinbase-distance side","last_matches_official")
report("~1 min snapshot side","one_min_matches_official")
report("Mean final <=60 sec","final60_matches_official")
report("Mean final <=90 sec","final90_matches_official")
report("Mean final <=120 sec","final120_matches_official")

print("\n=== SAMPLE COVERAGE ===")
for label,col in [("Final <=60 sec","final60_n"),("Final <=90 sec","final90_n"),("Final <=120 sec","final120_n")]:
    n=pd.to_numeric(d[col],errors="coerce")
    print(f"{label:18s} contracts={(n>0).sum():4d} median_snapshots={n[n>0].median() if (n>0).any() else np.nan:.1f} max={n.max():.0f}")

print("\n=== LAST-SNAPSHOT DISAGREEMENT BY ABS DISTANCE ===")
absd=d["last_distance"].abs()
for lo,hi in [(0,25),(25,50),(50,100),(100,200),(200,500),(500,np.inf)]:
    x=d[(absd>=lo)&(absd<hi)]
    if len(x):
        bad=(~x["last_matches_official"]).sum()
        lab=f"${lo:g}-${hi:g}" if np.isfinite(hi) else f"${lo:g}+"
        print(f"{lab:12s} n={len(x):4d} disagreements={bad:3d} rate={bad/len(x):.1%}")

print("\n=== FINAL-60S PROXY DISAGREEMENTS ===")
bad=d[d["final60_matches_official"]==False]
cols=["ticker","official_side","last_remaining_min","last_distance","last_side",
      "final60_n","final60_mean_distance","final60_side","final90_n","final90_mean_distance","final90_side"]
print(bad[cols].to_string(index=False) if len(bad) else "None")

d.to_csv("kalshi_settlement_proxy_mismatch_details.csv",index=False)
print("\nSaved: kalshi_settlement_proxy_mismatch_details.csv")
print("=== AUDIT COMPLETE ===")
