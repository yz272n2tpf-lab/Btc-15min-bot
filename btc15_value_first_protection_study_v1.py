#!/usr/bin/env python3
"""BTC15 value-first protection study V1.

READ ONLY | RESEARCH ONLY | SIGNAL ONLY | NO ORDERS.

Detector is unchanged. Entry is the frozen development candidate:
- movement candidate first;
- immediate actual ASK if <=50c;
- otherwise first actual ASK <=50c within 30 seconds;
- no price bucket changes detector qualification.

Protection arm remains fixed at +5c. Only trailing giveback behavior is compared.
"""
from __future__ import annotations
import json,math,statistics
from collections import defaultdict
from typing import Any

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION="BTC15_VALUE_FIRST_PROTECTION_STUDY_V1"
ARM=.05
DEV_SHARE=.60

VARIANTS={
  "GB2": lambda peak:.02,
  "GB3": lambda peak:.03,
  "CONTROL_GB4": lambda peak:.04,
  "GB5": lambda peak:.05,
  "GB6": lambda peak:.06,
  "STEP_4_3_2": lambda peak:(.02 if peak>=.20-1e-12 else (.03 if peak>=.10-1e-12 else .04)),
}

def f(v): return research.f(v)
def mean(xs):
    a=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(a) if a else None
def median(xs):
    a=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(a) if a else None
def rate(xs):
    a=list(xs); return None if not a else sum(bool(x) for x in a)/len(a)

def raw_objects(rows):
    cands={research.cid(c):dict(c) for c in forward.forward_candidates(rows) if research.cid(c)}
    paths=defaultdict(list)
    for r in rows:
        if research.typ(r)=="PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))
    for cid,p in paths.items():
        c=cands.get(cid)
        if c:
            t0=research.dt(c.get("timestamp_utc"))
            p.sort(key=lambda r:(research.elapsed(r,t0) if research.elapsed(r,t0) is not None else 1e99,research.dt(r.get("timestamp_utc"))))
    projected=lifecycle.audit(rows).get("projected_ladder") or []
    return cands,paths,projected

def value_entry(c,path):
    ask0=f(c.get("entry_ask"))
    if ask0 is None or not 0<ask0<1:return None
    if ask0<=.50+1e-12:return (0.0,ask0)
    t0=research.dt(c.get("timestamp_utc"))
    for r in path:
        e=research.elapsed(r,t0)
        if e is None or e<=0:continue
        if e>30.0:break
        ask=f(r.get("current_ask"));bid=f(r.get("current_bid"))
        if ask is None or bid is None or not 0<=bid<=ask<=1:continue
        if ask<=.50+1e-12:return (e,ask)
    return None

def build_entries(rows):
    cands,paths,projected=raw_objects(rows)
    out=[]
    for p in projected:
        cid=str(p.get("candidate_id") or "")
        c=cands.get(cid)
        if not c:continue
        path=paths.get(cid,[])
        ent=value_entry(c,path)
        if ent is None:continue
        ee,ask=ent;t0=research.dt(c.get("timestamp_utc"))
        future=[]
        for r in path:
            e=research.elapsed(r,t0)
            if e is None or e<ee:continue
            bid=f(r.get("current_bid"))
            if bid is None:continue
            future.append((e-ee,bid-ask))
        if not future:continue
        out.append({
          "contract":research.contract(c),"candidate_id":cid,
          "timestamp_utc":str(c.get("timestamp_utc") or ""),
          "entry_ask":ask,"entry_delay":ee,
          "future":future,
        })
    out.sort(key=lambda x:research.dt(x["timestamp_utc"]))
    return out

def split_map(entries):
    first={}
    for r in entries:
        c=r["contract"];t=research.dt(r["timestamp_utc"])
        if c not in first or t<first[c]:first[c]=t
    ordered=sorted(first,key=lambda c:first[c])
    cut=max(1,min(len(ordered),int(round(len(ordered)*DEV_SHARE)))) if ordered else 0
    return {c:("DEVELOPMENT" if i<cut else "HOLDOUT") for i,c in enumerate(ordered)}

def manage(r,giveback_fn):
    fut=r["future"]
    full_peak=max(g for _,g in fut)
    full_adverse=min(g for _,g in fut)
    plus10=full_peak>=.10-1e-12
    plus20=full_peak>=.20-1e-12
    peak=-1e99;armed=False;exit_idx=None;exit_gain=None;peak_at_exit=None;gb_at_exit=None
    for i,(e,g) in enumerate(fut):
        peak=max(peak,g)
        armed=armed or peak>=ARM-1e-12
        gb=giveback_fn(peak)
        if armed and peak-g>=gb-1e-12:
            exit_idx=i;exit_gain=g;peak_at_exit=peak;gb_at_exit=peak-g;break
    if exit_idx is None:
        realized=fut[-1][1]
        later_new_high=False
    else:
        realized=exit_gain
        later=[g for _,g in fut[exit_idx+1:]]
        later_new_high=bool(later and max(later)>peak_at_exit+1e-12)
    return {
      "full_peak":full_peak,"full_adverse":full_adverse,"plus10":plus10,"plus20":plus20,
      "armed":armed,"exit":exit_idx is not None,"realized":realized,
      "exit_gain":exit_gain,"peak_at_exit":peak_at_exit,"giveback_at_exit":gb_at_exit,
      "later_new_high":later_new_high,
      "left_on_table":full_peak-realized,
      "capture_ratio":None if full_peak<=0 else realized/full_peak,
    }

def score(entries,name,fn):
    z=[manage(r,fn) for r in entries]
    return {
      "variant":name,"n":len(z),
      "avg_entry_ask_c":None if not entries else 100*mean(r["entry_ask"] for r in entries),
      "avg_entry_delay_sec":mean(r["entry_delay"] for r in entries),
      "plus10_rate":rate(x["plus10"] for x in z),
      "plus20_rate":rate(x["plus20"] for x in z),
      "armed_rate":rate(x["armed"] for x in z),
      "exit_rate":rate(x["exit"] for x in z),
      "avg_realized_c":None if not z else 100*mean(x["realized"] for x in z),
      "median_realized_c":None if not z else 100*median(x["realized"] for x in z),
      "positive_realized_rate":rate(x["realized"]>0 for x in z),
      "realized_ge5_rate":rate(x["realized"]>=.05-1e-12 for x in z),
      "realized_ge10_rate":rate(x["realized"]>=.10-1e-12 for x in z),
      "avg_left_on_table_c":None if not z else 100*mean(x["left_on_table"] for x in z),
      "median_capture_ratio":median(x["capture_ratio"] for x in z),
      "later_new_high_after_exit_rate":rate(x["later_new_high"] for x in z if x["exit"]),
      "negative_exit_rate":rate(x["exit_gain"] is not None and x["exit_gain"]<0 for x in z if x["exit"]),
      "avg_exit_gain_c":100*mean(x["exit_gain"] for x in z if x["exit"]) if any(x["exit"] for x in z) else None,
    }

def main():
    rows,sha=forward.fetch_csv_rows()
    entries=build_entries(rows)
    sm=split_map(entries)
    dev=[r for r in entries if sm.get(r["contract"])=="DEVELOPMENT"]
    hold=[r for r in entries if sm.get(r["contract"])=="HOLDOUT"]
    print(f"PROTECT_BASE | source_rows={len(rows)} | entries={len(entries)} | dev={len(dev)} | hold={len(hold)} | source_sha={sha} | NO ORDERS",flush=True)
    dev_scores={}
    hold_scores={}
    for name,fn in VARIANTS.items():
        d=score(dev,name,fn);h=score(hold,name,fn)
        dev_scores[name]=d;hold_scores[name]=h
        print("PROTECT_DEV "+json.dumps(d,sort_keys=True),flush=True)
        print("PROTECT_HOLD "+json.dumps(h,sort_keys=True),flush=True)
    control=dev_scores["CONTROL_GB4"]
    # Mechanical shortlist only: no worse positive rate by >2pp; improve avg realized
    # by >=0.25c; no more than +5pp later-new-high regret vs control.
    shortlist=[]
    for name,d in dev_scores.items():
        if name=="CONTROL_GB4":continue
        if (d["positive_realized_rate"] or 0)<(control["positive_realized_rate"] or 0)-.02:continue
        if (d["avg_realized_c"] or -999)<(control["avg_realized_c"] or -999)+.25:continue
        if (d["later_new_high_after_exit_rate"] or 0)>(control["later_new_high_after_exit_rate"] or 0)+.05:continue
        shortlist.append(name)
    print("PROTECT_SHORTLIST | "+",".join(shortlist)+" | CONTROL=CONTROL_GB4 | NO AUTO PROMOTE | NO ORDERS",flush=True)
    for name in shortlist:
        h=hold_scores[name];hc=hold_scores["CONTROL_GB4"]
        support=bool(
          (h["positive_realized_rate"] or 0)>=(hc["positive_realized_rate"] or 0)-.02
          and (h["avg_realized_c"] or -999)>=(hc["avg_realized_c"] or -999)+.10
          and (h["later_new_high_after_exit_rate"] or 0)<=(hc["later_new_high_after_exit_rate"] or 0)+.05
        )
        print(f"PROTECT_HOLD_SUPPORT | variant={name} | support={support} | NO ORDERS",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
