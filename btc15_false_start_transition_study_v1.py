#!/usr/bin/env python3
"""BTC15 micro-confirmation transition study V1.

READ ONLY | RESEARCH ONLY | SIGNAL ONLY | NO ORDERS.

Tests whether the already-qualified move remains aligned for only a few seconds.
No entry-price gate, no seconds-left gate, no btc30 retune, and no strict
BRTI/BTC ratio. Entry economics use the actual ASK at confirmation and all
outcomes use subsequent executable BID.
"""
from __future__ import annotations
import json,math,statistics
from collections import defaultdict,deque
from typing import Any,Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION="BTC15_FALSE_START_MICRO_CONFIRM_V1"
DEV_SHARE=.60
MIN_DEV_N=50
MIN_HOLD_N=30

def f(v): return research.f(v)
def mean(xs):
    a=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(a) if a else None

def split_map(records):
    first={}
    for r in records:
        c=r["contract"];t=research.dt(r["timestamp_utc"])
        if c not in first or t<first[c]:first[c]=t
    ordered=sorted(first,key=lambda c:first[c])
    cut=max(1,min(len(ordered),int(round(len(ordered)*DEV_SHARE)))) if ordered else 0
    return {c:("DEVELOPMENT" if i<cut else "HOLDOUT") for i,c in enumerate(ordered)}

def source_objects(rows):
    cands={research.cid(c):dict(c) for c in forward.forward_candidates(rows) if research.cid(c)}
    paths=defaultdict(list)
    for r in rows:
        if research.typ(r)=="PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))
    for cid in paths:
        c=cands.get(cid)
        if c:
            paths[cid].sort(key=lambda x:(research.elapsed(x,research.dt(c.get("timestamp_utc"))) or 0.0,research.dt(x.get("timestamp_utc"))))
    projected=lifecycle.audit(rows).get("projected_ladder") or []
    out=[]
    for p in projected:
        cid=str(p.get("candidate_id") or "");c=cands.get(cid)
        if not c:continue
        out.append({
            "contract":str(p.get("contract") or research.contract(c)),
            "candidate_id":cid,
            "timestamp_utc":str(c.get("timestamp_utc") or ""),
            "side":str(p.get("side") or c.get("side") or "").upper(),
            "entry_ask":f(c.get("entry_ask")),
            "btc":f(c.get("btc")),
            "brti":f(c.get("brti")),
            "plus10":bool(p.get("plus10")),
            "plus20":bool(p.get("plus20")),
            "path":paths.get(cid,[]),
        })
    out.sort(key=lambda r:research.dt(r["timestamp_utc"]))
    return out

RULES={
 "DUAL_1OBS_4S":dict(need=1,btc_tol=0.0,brti_tol=0.0),
 "DUAL_2OBS_4S":dict(need=2,btc_tol=0.0,brti_tol=0.0),
 "BRTI_2OBS_BTC_TOL2_4S":dict(need=2,btc_tol=-2.0,brti_tol=0.0),
}

def verified(rec,rule):
    cb,cr=rec.get("btc"),rec.get("brti")
    if cb is None or cr is None:return None
    s=1 if rec["side"]=="UP" else -1
    q=deque(maxlen=rule["need"])
    ct=research.dt(rec["timestamp_utc"])
    for row in rec["path"]:
        e=research.elapsed(row,ct)
        if e is None or e<.75:continue
        if e>4.0:break
        b=f(row.get("btc"));r=f(row.get("brti"));ask=f(row.get("current_ask"))
        if b is None or r is None or ask is None: q.clear();continue
        db=(b-cb)*s;dr=(r-cr)*s
        ok=db>=rule["btc_tol"] and dr>=rule["brti_tol"]
        if not ok:q.clear();continue
        q.append((e,row,ask,db,dr))
        if len(q)>=rule["need"]:
            return q[-1]
    return None

def rescore(rec,verification):
    e0,row0,entry,db,dr=verification
    ct=research.dt(rec["timestamp_utc"])
    peak=None;adverse=None;armed=False;exit_gain=None
    hit5=hit10=hit20=False
    for row in rec["path"]:
        e=research.elapsed(row,ct)
        if e is None or e<e0:continue
        bid=f(row.get("current_bid"))
        if bid is None:continue
        g=bid-entry
        peak=g if peak is None else max(peak,g)
        adverse=g if adverse is None else min(adverse,g)
        hit5=hit5 or g>=.05-1e-12
        hit10=hit10 or g>=.10-1e-12
        hit20=hit20 or g>=.20-1e-12
        if peak>=.05-1e-12:armed=True
        if armed and peak-g>=.04-1e-12:
            exit_gain=g;break
    return {
      "entry":entry,"delay":e0,"btc_continue":db,"brti_continue":dr,
      "peak":peak,"adverse":adverse,"plus5":hit5,"plus10":hit10,"plus20":hit20,
      "exit_gain":exit_gain,
    }

def baseline_metrics(rows):
    n=len(rows);w=sum(r["plus10"] for r in rows)
    return {
      "n":n,"plus10_n":w,"plus10_rate":None if not n else w/n,
      "plus20_rate":None if not n else sum(r["plus20"] for r in rows)/n,
      "avg_entry_ask":mean(r.get("entry_ask") for r in rows),
    }

def score(rows,name,rule):
    base=baseline_metrics(rows)
    scored=[]
    passed_ids=set()
    original_winners={r["candidate_id"] for r in rows if r["plus10"]}
    original_losers={r["candidate_id"] for r in rows if not r["plus10"]}
    for rec in rows:
        v=verified(rec,rule)
        if v is None:continue
        z=rescore(rec,v)
        z["candidate_id"]=rec["candidate_id"]
        z["candidate_entry"]=rec["entry_ask"]
        scored.append(z);passed_ids.add(rec["candidate_id"])
    n=len(scored)
    w=sum(z["plus10"] for z in scored)
    removed_losers=len(original_losers-passed_ids)
    retained_winners=len(original_winners & passed_ids)
    avg_entry=mean(z["entry"] for z in scored)
    avg_candidate=mean(z["candidate_entry"] for z in scored)
    return {
      "rule":name,"n":n,
      "selected_share_retained":None if not rows else n/len(rows),
      "original_winner_retention":None if not original_winners else retained_winners/len(original_winners),
      "false_start_rejection_rate":None if not original_losers else removed_losers/len(original_losers),
      "delayed_plus10_rate":None if not n else w/n,
      "delayed_plus20_rate":None if not n else sum(z["plus20"] for z in scored)/n,
      "plus10_lift_vs_original_baseline":None if not n or base["plus10_rate"] is None else w/n-base["plus10_rate"],
      "avg_delay_sec":mean(z["delay"] for z in scored),
      "avg_entry_ask":avg_entry,
      "avg_entry_change_vs_candidate":None if avg_entry is None or avg_candidate is None else avg_entry-avg_candidate,
      "avg_peak_gain":mean(z["peak"] for z in scored),
      "avg_adverse_gain":mean(z["adverse"] for z in scored),
      "protected_exit_observed_rate":None if not n else sum(z["exit_gain"] is not None for z in scored)/n,
    }

def dev_ok(m):
    return bool(
      m["n"]>=MIN_DEV_N
      and (m.get("original_winner_retention") or 0)>=.90
      and (m.get("selected_share_retained") or 0)>=.75
      and (m.get("plus10_lift_vs_original_baseline") or -9)>=.03
      and (m.get("avg_delay_sec") or 99)<=3.0
      and (m.get("avg_entry_change_vs_candidate") or 99)<=.03
    )

def hold_ok(m):
    return bool(
      m["n"]>=MIN_HOLD_N
      and (m.get("original_winner_retention") or 0)>=.88
      and (m.get("selected_share_retained") or 0)>=.70
      and (m.get("plus10_lift_vs_original_baseline") or -9)>=.02
      and (m.get("avg_delay_sec") or 99)<=3.0
      and (m.get("avg_entry_change_vs_candidate") or 99)<=.03
    )

def main():
    rows,sha=forward.fetch_csv_rows()
    recs=source_objects(rows)
    sm=split_map(recs)
    dev=[r for r in recs if sm.get(r["contract"])=="DEVELOPMENT"]
    hold=[r for r in recs if sm.get(r["contract"])=="HOLDOUT"]
    dev_base=baseline_metrics(dev);hold_base=baseline_metrics(hold)
    frontier=[]
    for name,rule in RULES.items():
        m=score(dev,name,rule);m["development_eligible"]=dev_ok(m);frontier.append(m)
    elig=[m for m in frontier if m["development_eligible"]]
    elig.sort(key=lambda m:(
      float(m.get("plus10_lift_vs_original_baseline") or -9),
      float(m.get("original_winner_retention") or 0),
      -float(m.get("avg_delay_sec") or 99),
      -float(m.get("avg_entry_change_vs_candidate") or 99),
    ),reverse=True)
    nominee=elig[0] if elig else None
    hold_nom=None;supported=False
    if nominee:
        hold_nom=score(hold,nominee["rule"],RULES[nominee["rule"]])
        supported=hold_ok(hold_nom)
    print("MICRO_CONFIRM_RESULT "+json.dumps({
      "version":VERSION,"source_sha256":sha,"source_rows":len(rows),"records":len(recs),
      "development_n":len(dev),"holdout_n":len(hold),
      "development_baseline":dev_base,"development_frontier":frontier,
      "development_nominee":nominee,"holdout_baseline":hold_base,
      "holdout_nominee":hold_nom,"holdout_support":supported,
      "freeze_for_clean_forward_validation":bool(supported),
      "no_price_gate":True,"no_time_gate":True,"orders":False,"auto_promote":False,
    },sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
