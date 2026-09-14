#!/usr/bin/env python3
"""
BTC15 frozen generalized-scalp forward stability audit V1.
READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Purpose
-------
Audit the already-frozen untouched-forward challenger across broad descriptive
slices WITHOUT changing eligibility, management, or thresholds.

Frozen challenger (unchanged):
- post-freeze rows only
- first candidate per contract with seconds_left >= 120 and btc30 >= 15
- no entry-price filter
- management arms at +5c and protects after 4c giveback from executable peak

This audit is descriptive only. It does not choose thresholds or promote rules.
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

DEFAULT_CSV = "/data/scalp_move_shadow_v1_events.csv"
FREEZE = pd.Timestamp("2026-09-14T02:24:03.366238Z")


def pct(v):
    return "—" if pd.isna(v) else f"{100.0*float(v):.1f}%"


def cents(v):
    return "—" if pd.isna(v) else f"{100.0*float(v):+.2f}c"


def managed_exit(candidate_ids, paths, results, arm=.05, giveback=.04):
    pmap = {k:g.sort_values("elapsed_sec") for k,g in paths.groupby("candidate_id")}
    rmap = results.set_index("candidate_id")
    out=[]
    for cid in candidate_ids:
        peak=-1e9; armed=False; exit_gain=np.nan
        for _, z in pmap.get(cid, paths.iloc[0:0]).iterrows():
            g=z.get("exec_gain")
            if pd.isna(g):
                continue
            g=float(g); peak=max(peak,g); armed=armed or peak>=arm
            if armed and peak-g>=giveback:
                exit_gain=g
                break
        if pd.isna(exit_gain):
            if cid in rmap.index:
                v=rmap.loc[cid].get("horizon_exec_gain")
                exit_gain=0.0 if pd.isna(v) else float(v)
        out.append((cid,exit_gain))
    return pd.DataFrame(out,columns=["candidate_id","managed_gain"])


def stats(g):
    if g.empty:
        return {"n":0,"h5":np.nan,"h10":np.nan,"h20":np.nan,"managed_avg":np.nan,
                "managed_med":np.nan,"positive":np.nan,"med_adv":np.nan}
    return {
        "n":len(g),
        "h5":g.hit5_sec.notna().mean(),
        "h10":g.hit10_sec.notna().mean(),
        "h20":g.hit20_sec.notna().mean(),
        "managed_avg":g.managed_gain.mean(),
        "managed_med":g.managed_gain.median(),
        "positive":(g.managed_gain>0).mean(),
        "med_adv":g.max_adverse.median(),
    }


def emit(label,g):
    s=stats(g)
    print(f"{label}: n={s['n']} +5={pct(s['h5'])} +10={pct(s['h10'])} +20={pct(s['h20'])} "
          f"managed_avg={cents(s['managed_avg'])} managed_med={cents(s['managed_med'])} "
          f"positive={pct(s['positive'])} med_adverse={cents(s['med_adv'])}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",default=DEFAULT_CSV)
    ap.add_argument("--freeze",default=str(FREEZE))
    a=ap.parse_args()

    d=pd.read_csv(a.csv,low_memory=False)
    d["timestamp_utc"]=pd.to_datetime(d["timestamp_utc"],utc=True,errors="coerce")
    d=d[d.timestamp_utc>pd.Timestamp(a.freeze)].copy()
    nums=["seconds_left","entry_ask","btc30","elapsed_sec","exec_gain","peak_exec_gain",
          "max_adverse","horizon_exec_gain","hit5_sec","hit10_sec","hit20_sec"]
    for f in nums:
        if f in d.columns:
            d[f]=pd.to_numeric(d[f],errors="coerce")

    cand=d[d.record_type.eq("CANDIDATE")].copy()
    res=d[d.record_type.eq("RESULT")].copy()
    path=d[d.record_type.eq("PATH")].copy()

    qual=cand[(cand.seconds_left>=120)&(cand.btc30>=15)].copy()
    qual=qual.sort_values(["contract","timestamp_utc"]).drop_duplicates("contract",keep="first")
    keep=["candidate_id","timestamp_utc","contract","side","seconds_left","entry_ask","btc30"]
    outcomes=["candidate_id","peak_exec_gain","max_adverse","horizon_exec_gain",
              "hit5_sec","hit10_sec","hit20_sec"]
    done=qual[keep].merge(res[outcomes],on="candidate_id",how="inner")
    done=done.merge(managed_exit(done.candidate_id.tolist(),path,res),on="candidate_id",how="left")

    print("="*96)
    print("BTC15 FROZEN SCALP FORWARD STABILITY AUDIT V1 | READ ONLY | SIGNAL ONLY | NO ORDERS")
    print("="*96)
    emit("ALL",done)

    print("\nSIDE")
    for side in ["UP","DOWN"]:
        emit(side,done[done.side.astype(str).str.upper().eq(side)])

    print("\nENTRY TIMING")
    emit("2-5m",done[done.seconds_left.between(120,300,inclusive="left")])
    emit("5-10m",done[done.seconds_left.between(300,600,inclusive="left")])
    emit("10-15m",done[done.seconds_left.between(600,900,inclusive="both")])

    print("\nBTC30 MOMENTUM INTENSITY — DESCRIPTIVE ONLY")
    emit("15-25",done[done.btc30.between(15,25,inclusive="left")])
    emit("25-40",done[done.btc30.between(25,40,inclusive="left")])
    emit("40+",done[done.btc30>=40])

    print("\nENTRY PRICE TELEMETRY — NEVER ELIGIBILITY")
    bands=[("<20c",done.entry_ask<.20),
           ("20-35c",done.entry_ask.between(.20,.35,inclusive="left")),
           ("35-50c",done.entry_ask.between(.35,.50,inclusive="left")),
           ("50-70c",done.entry_ask.between(.50,.70,inclusive="left")),
           ("70c+",done.entry_ask>=.70)]
    for name,mask in bands:
        emit(name,done[mask])

    print("\nTIME-OF-DAY UTC — BROAD STABILITY CHECK")
    h=done.timestamp_utc.dt.hour
    emit("00-08Z",done[h.between(0,7)])
    emit("08-16Z",done[h.between(8,15)])
    emit("16-24Z",done[h.between(16,23)])

    print("\nGUARDRAILS")
    print("- No eligibility or management threshold changed.")
    print("- Price and slice labels are telemetry only, not new filters.")
    print("- Do not tune the challenger from this forward sample.")
    print("- This audit is descriptive support for KEEP/SCRATCH stability review only.")
    print("- No order-placement code exists.")


if __name__=="__main__":
    main()
