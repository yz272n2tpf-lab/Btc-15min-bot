#!/usr/bin/env python3
"""
BTC15 generalized scalp management scorer V3.
READ-ONLY OFFLINE RESEARCH. NO ORDERS.

Price bands are telemetry only. A challenger discovered on this tape is not
promoted until a genuinely untouched forward sample confirms it.
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

DEFAULT_CSV="/data/scalp_move_shadow_v1_events.csv"
V2_CUTOFF="2026-09-13T13:09:01Z"
TARGETS=(5,10,15,20,30)

def pct(x): return "—" if pd.isna(x) else f"{100*x:.1f}%"
def cents(x): return "—" if pd.isna(x) else f"{100*x:+.2f}c"

def load(path, cutoff=None):
    d=pd.read_csv(path,low_memory=False)
    d["timestamp_utc"]=pd.to_datetime(d["timestamp_utc"],utc=True,errors="coerce")
    if cutoff is not None:
        d=d[d["timestamp_utc"]>=cutoff].copy()
    c=d[d.record_type.eq("CANDIDATE")].copy()
    r=d[d.record_type.eq("RESULT")].copy()
    p=d[d.record_type.eq("PATH")].copy()
    s=d[d.record_type.eq("SNAPSHOT")].copy()
    nums=["seconds_left","entry_ask","btc30","brti15","elapsed_sec","exec_gain",
          "peak_exec_gain","max_adverse","max_giveback","horizon_exec_gain",
          "hit5_sec","hit10_sec","hit15_sec","hit20_sec","hit30_sec"]
    for f in nums:
        for x in (c,r,p):
            if f in x: x[f]=pd.to_numeric(x[f],errors="coerce")
    keep=["candidate_id","timestamp_utc","contract","side","seconds_left","entry_ask",
          "entry_price_telemetry","btc30","brti15"]
    outcomes=["candidate_id","peak_exec_gain","max_adverse","max_giveback",
              "horizon_exec_gain","hit5_sec","hit10_sec","hit15_sec","hit20_sec","hit30_sec"]
    x=c[keep].merge(r[outcomes],on="candidate_id",how="inner")
    return d,x,p,s

def stats(x):
    z={"n":len(x),"contracts":x.contract.nunique()}
    for t in TARGETS: z[f"h{t}"]=x[f"hit{t}_sec"].notna().mean() if len(x) else np.nan
    z["med_peak"]=x.peak_exec_gain.median() if len(x) else np.nan
    z["med_adv"]=x.max_adverse.median() if len(x) else np.nan
    return z

def first_qualified(x, mask=None):
    q=x.copy()
    if mask is not None: q=q[mask(q)]
    return q.sort_values(["contract","timestamp_utc"]).drop_duplicates("contract",keep="first").sort_values("timestamp_utc")

def trailing(x,p,arm=.05,giveback=.04):
    by={k:g.sort_values("elapsed_sec") for k,g in p.groupby("candidate_id")}
    vals=[]; trail=0
    for _,r in x.iterrows():
        peak=-1e9; armed=False; exited=False
        for _,z in by.get(r.candidate_id,p.iloc[0:0]).iterrows():
            g=z.exec_gain
            if pd.isna(g): continue
            peak=max(peak,g)
            armed=armed or peak>=arm
            if armed and peak-g>=giveback:
                vals.append(g); trail+=1; exited=True; break
        if not exited:
            vals.append(0.0 if pd.isna(r.horizon_exec_gain) else r.horizon_exec_gain)
    a=np.asarray(vals,float)
    return {"avg":a.mean() if len(a) else np.nan,
            "med":np.median(a) if len(a) else np.nan,
            "win":(a>0).mean() if len(a) else np.nan,
            "trail":trail/len(a) if len(a) else np.nan}

def chrono(x):
    q=x.sort_values("timestamp_utc")
    cs=q[["contract","timestamp_utc"]].drop_duplicates("contract").sort_values("timestamp_utc")
    n=len(cs); a=int(n*.60); b=int(n*.80)
    sets={"DEV":set(cs.iloc[:a].contract),"VAL":set(cs.iloc[a:b].contract),"HOLD":set(cs.iloc[b:].contract)}
    return {k:q[q.contract.isin(v)] for k,v in sets.items()}

def table(headers,rows):
    w=[len(str(x)) for x in headers]
    for r in rows:
        for i,v in enumerate(r): w[i]=max(w[i],len(str(v)))
    print(" | ".join(str(v).ljust(w[i]) for i,v in enumerate(headers)))
    print("-+-".join("-"*x for x in w))
    for r in rows: print(" | ".join(str(v).ljust(w[i]) for i,v in enumerate(r)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",default=DEFAULT_CSV)
    ap.add_argument("--cutoff")
    ap.add_argument("--v2-only",action="store_true")
    a=ap.parse_args()
    cutoff=pd.Timestamp(V2_CUTOFF) if a.v2_only else (pd.Timestamp(a.cutoff) if a.cutoff else None)
    d,x,p,s=load(a.csv,cutoff)
    latest=d.timestamp_utc.max()
    s["contract_close_utc"]=pd.to_datetime(s.contract_close_utc,utc=True,errors="coerce")
    settled=set(s[s.contract_close_utc<=latest].contract.dropna())
    sig=set(x.contract)
    coverage=len(settled&sig)/len(settled) if settled else np.nan

    print("="*88)
    print("BTC15 GENERALIZED SCALP MANAGEMENT V3 | READ ONLY | SIGNAL ONLY | NO ORDERS")
    print("="*88)
    print(f"CSV {a.csv}")
    print(f"Cutoff {cutoff if cutoff is not None else 'NONE'}")
    print(f"rows={len(d):,} complete={len(x)} PATH={len(p):,} settled_contracts={len(settled)} candidate_contracts={len(settled&sig)} coverage={pct(coverage)}")
    z=stats(x)
    print(f"ALL: +5 {pct(z['h5'])} +10 {pct(z['h10'])} +20 {pct(z['h20'])} median_peak {cents(z['med_peak'])}")

    bands=[("<10",x.entry_ask<.10),("10-20",x.entry_ask.between(.10,.20,inclusive="left")),
           ("20-30",x.entry_ask.between(.20,.30,inclusive="left")),
           ("30-45",x.entry_ask.between(.30,.45,inclusive="left")),
           ("45-60",x.entry_ask.between(.45,.60,inclusive="left")),
           ("60-80",x.entry_ask.between(.60,.80,inclusive="left")),("80+",x.entry_ask>=.80)]
    print("\nPRICE TELEMETRY ONLY — NEVER ELIGIBILITY")
    table(["band","n","+10","+20","med peak"],
          [[n,stats(x[m])["n"],pct(stats(x[m])["h10"]),pct(stats(x[m])["h20"]),cents(stats(x[m])["med_peak"])] for n,m in bands])

    times=[("<2m",x.seconds_left<120),("2-5m",x.seconds_left.between(120,300,inclusive="left")),
           ("5-10m",x.seconds_left.between(300,600,inclusive="left")),
           ("10-15m",x.seconds_left.between(600,900,inclusive="both"))]
    print("\nENTRY TIME")
    table(["time","n","+5","+10","+20","med peak"],
          [[n,stats(x[m])["n"],pct(stats(x[m])["h5"]),pct(stats(x[m])["h10"]),pct(stats(x[m])["h20"]),cents(stats(x[m])["med_peak"])] for n,m in times])

    q=x.sort_values(["contract","timestamp_utc"]).copy()
    q["rank"]=q.groupby("contract").cumcount()+1
    print("\nCANDIDATE ORDER")
    table(["rank","n","+5","+10","+20","med peak"],
          [[r,stats(g)["n"],pct(stats(g)["h5"]),pct(stats(g)["h10"]),pct(stats(g)["h20"]),cents(stats(g)["med_peak"])]
           for r,g in q[q["rank"]<=6].groupby("rank")])

    print("\nTRAILING MANAGEMENT — ALL CANDIDATES")
    rows=[]
    for arm in (.05,.08):
        for gb in (.03,.04,.05):
            m=trailing(x,p,arm,gb)
            rows.append([f"+{arm*100:.0f}c",f"{gb*100:.0f}c",cents(m["avg"]),cents(m["med"]),pct(m["win"]),pct(m["trail"])])
    table(["arm","giveback","avg","median","win","trail exit"],rows)

    base=first_qualified(x)
    challenger=first_qualified(x,lambda d:(d.seconds_left>=120)&(d.btc30>=15))
    print("\nFIRST SIGNAL vs PRICE-AGNOSTIC RESEARCH CHALLENGER")
    rows=[]
    for name,g in (("baseline first",base),(">=120s + btc30>=15",challenger)):
        z=stats(g); m=trailing(g,p,.05,.04)
        rows.append([name,len(g),pct(z["h10"]),pct(z["h20"]),cents(m["avg"]),cents(m["med"]),pct(m["win"])])
    table(["policy","n","+10","+20","trail avg","trail med","trail win"],rows)

    print("\nCHRONOLOGICAL DESCRIPTIVE SLICES — NOT A TRUE UNTOUCHED TEST AFTER RULE DISCOVERY")
    rows=[]
    for name,g in (("baseline",base),("challenger",challenger)):
        for split,h in chrono(g).items():
            z=stats(h); m=trailing(h,p,.05,.04)
            rows.append([f"{name} {split}",len(h),pct(z["h10"]),pct(z["h20"]),cents(m["avg"]),pct(m["win"])])
    table(["slice","n","+10","+20","trail avg","trail win"],rows)

    print("\nGUARDRAILS")
    print("- Price is telemetry, not eligibility.")
    print("- Under-2-minute candidates are a separate late regime; do not promote them from this tape.")
    print("- Raw reversal telemetry is not a calibrated reversal-risk percentage.")
    print("- Challenger is RESEARCH ONLY until new forward data confirms it.")
    print("- This script reads the CSV only and contains no order-placement code.")

if __name__=="__main__":
    main()
