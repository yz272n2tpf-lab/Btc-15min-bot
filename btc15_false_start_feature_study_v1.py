#!/usr/bin/env python3
"""BTC15 false-start entry-quality study V1.

READ ONLY | RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Uses the current generalized scalp event tape through the existing authorized
read-only export. It does not change entry rules, protection, EARLY, FINAL,
price handling, or production.

Already-rejected paths are explicitly excluded from selection:
- btc30 tightening
- normalized momentum floors
- strict 15-second BRTI/BTC parity
- entry-price or fixed-time gates

The study asks whether stronger *existing candidate-time* BRTI support and/or
acceleration can reject false starts while retaining >=90% of +10c winners.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_FALSE_START_ENTRY_QUALITY_V1"
DEV_SHARE = 0.60
MIN_DEV_N = 50
MIN_HOLD_N = 30
DEV_WINNER_RETENTION = 0.90
DEV_SELECTED_RETENTION = 0.70
DEV_MIN_LIFT = 0.03
HOLD_WINNER_RETENTION = 0.88
HOLD_SELECTED_RETENTION = 0.65
HOLD_MIN_LIFT = 0.02
MAX_AVG_ASK_WORSEN = 0.02
MAX_AVG_TIME_LOSS_SEC = 30.0

REPORT_ONLY_FIELDS = (
    "btc5", "btc15", "btc30", "brti5", "brti15", "accel",
    "confirm_count", "recent_btc_range60", "btc5_norm", "btc15_norm",
    "ask5", "ask15",
)

def f(v: Any) -> float | None:
    return research.f(v)

def _median(xs):
    vals=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(vals) if vals else None

def _mean(xs):
    vals=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(vals) if vals else None

def build_records(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cands={
        research.cid(c):dict(c)
        for c in forward.forward_candidates([dict(r) for r in rows])
        if research.cid(c)
    }
    projected=lifecycle.audit([dict(r) for r in rows]).get("projected_ladder") or []
    out=[]
    for p in projected:
        cid=str(p.get("candidate_id") or "")
        c=cands.get(cid)
        if not c:
            continue
        peak=f(p.get("peak_gain"))
        rec={
            "contract":str(p.get("contract") or research.contract(c)),
            "candidate_id":cid,
            "timestamp_utc":str(c.get("timestamp_utc") or ""),
            "opportunity_index":int(p.get("opportunity_index") or 0),
            "side":str(p.get("side") or c.get("side") or "").upper(),
            "plus5":bool(peak is not None and peak >= 0.05-1e-12),
            "plus10":bool(p.get("plus10")),
            "plus20":bool(p.get("plus20")),
            "peak_gain":peak,
            "adverse_gain":f(p.get("adverse_gain")),
            "entry_ask":f(c.get("entry_ask")),
            "seconds_left":f(c.get("seconds_left")),
        }
        for k in REPORT_ONLY_FIELDS:
            rec[k]=f(c.get(k))
        raw=str(c.get("structure_ok") or "").strip().lower()
        rec["structure_ok"]=raw in {"1","true","yes","y"}
        out.append(rec)
    out.sort(key=lambda r: research.dt(r.get("timestamp_utc")))
    return out

def split_map(records):
    first={}
    for r in records:
        c=r["contract"]; t=research.dt(r["timestamp_utc"])
        if c not in first or t<first[c]: first[c]=t
    ordered=sorted(first,key=lambda c:first[c])
    cut=max(1,min(len(ordered),int(round(len(ordered)*DEV_SHARE)))) if ordered else 0
    return {c:("DEVELOPMENT" if i<cut else "HOLDOUT") for i,c in enumerate(ordered)}

def metrics(rows, base=None):
    n=len(rows)
    w=sum(bool(r["plus10"]) for r in rows)
    p20=sum(bool(r["plus20"]) for r in rows)
    out={
        "n":n,
        "plus10_n":w,
        "plus10_rate":None if not n else w/n,
        "plus20_rate":None if not n else p20/n,
        "avg_entry_ask":_mean(r.get("entry_ask") for r in rows),
        "median_entry_ask":_median(r.get("entry_ask") for r in rows),
        "avg_seconds_left":_mean(r.get("seconds_left") for r in rows),
        "median_seconds_left":_median(r.get("seconds_left") for r in rows),
    }
    if base is not None:
        bw=[r for r in base if r["plus10"]]
        ids={r["candidate_id"] for r in rows}
        keptw=sum(r["candidate_id"] in ids for r in bw)
        out["winner_retention"]=None if not bw else keptw/len(bw)
        out["selected_share_retained"]=None if not base else len(rows)/len(base)
        losers=[r for r in base if not r["plus10"]]
        removed_losers=sum(r["candidate_id"] not in ids for r in losers)
        removed_winners=sum(r["candidate_id"] not in ids for r in bw)
        out["false_start_rejection_rate"]=None if not losers else removed_losers/len(losers)
        out["winner_loss_rate"]=None if not bw else removed_winners/len(bw)
    return out

def describe(records):
    winners=[r for r in records if r["plus10"]]
    losers=[r for r in records if not r["plus10"]]
    d={}
    for k in REPORT_ONLY_FIELDS:
        d[k]={
            "winner_n":sum(r.get(k) is not None for r in winners),
            "false_start_n":sum(r.get(k) is not None for r in losers),
            "winner_median":_median(r.get(k) for r in winners),
            "false_start_median":_median(r.get(k) for r in losers),
        }
    d["structure_ok"]={
        "winner_rate":None if not winners else sum(bool(r.get("structure_ok")) for r in winners)/len(winners),
        "false_start_rate":None if not losers else sum(bool(r.get("structure_ok")) for r in losers)/len(losers),
    }
    return d

RULES=[]
for x in (10,12,15,18,20,25,30):
    RULES.append(("BRTI5_MIN_"+str(x),lambda r,x=x:(r.get("brti5") is not None and r["brti5"]>=x)))
for x in (2,4,6,8,10,12,15,20,25):
    RULES.append(("BRTI15_MIN_"+str(x),lambda r,x=x:(r.get("brti15") is not None and r["brti15"]>=x)))
for x in (5,6,8,10,12,15,20):
    RULES.append(("ACCEL_MIN_"+str(x),lambda r,x=x:(r.get("accel") is not None and r["accel"]>=x)))
for b,a in ((4,6),(4,8),(6,6),(6,8),(8,6),(8,8),(10,8),(10,10),(12,8),(12,10),(15,10)):
    RULES.append((
        f"BRTI15_{b}_ACCEL_{a}",
        lambda r,b=b,a=a:(
            r.get("brti15") is not None and r["brti15"]>=b
            and r.get("accel") is not None and r["accel"]>=a
        )
    ))

def eligible_dev(m, baseline):
    if m["n"]<MIN_DEV_N: return False
    if m.get("winner_retention") is None or m["winner_retention"]<DEV_WINNER_RETENTION: return False
    if m.get("selected_share_retained") is None or m["selected_share_retained"]<DEV_SELECTED_RETENTION: return False
    if m.get("plus10_rate") is None or baseline.get("plus10_rate") is None: return False
    if m["plus10_rate"]-baseline["plus10_rate"]<DEV_MIN_LIFT: return False
    return True

def holdout_support(m, baseline):
    if m["n"]<MIN_HOLD_N: return False
    if m.get("winner_retention") is None or m["winner_retention"]<HOLD_WINNER_RETENTION: return False
    if m.get("selected_share_retained") is None or m["selected_share_retained"]<HOLD_SELECTED_RETENTION: return False
    if m.get("plus10_rate") is None or baseline.get("plus10_rate") is None: return False
    if m["plus10_rate"]-baseline["plus10_rate"]<HOLD_MIN_LIFT: return False
    if m.get("avg_entry_ask") is not None and baseline.get("avg_entry_ask") is not None:
        if m["avg_entry_ask"] > baseline["avg_entry_ask"] + MAX_AVG_ASK_WORSEN: return False
    if m.get("avg_seconds_left") is not None and baseline.get("avg_seconds_left") is not None:
        if m["avg_seconds_left"] < baseline["avg_seconds_left"] - MAX_AVG_TIME_LOSS_SEC: return False
    return True

def main():
    rows,sha=forward.fetch_csv_rows()
    records=build_records(rows)
    sm=split_map(records)
    dev=[r for r in records if sm.get(r["contract"])=="DEVELOPMENT"]
    hold=[r for r in records if sm.get(r["contract"])=="HOLDOUT"]
    dev_base=metrics(dev)
    hold_base=metrics(hold)

    desc=describe(dev)
    print("FALSE_START_FEATURE_PROFILE "+json.dumps({
        "version":VERSION,
        "source_sha256":sha,
        "source_rows":len(rows),
        "records":len(records),
        "development_n":len(dev),
        "holdout_n":len(hold),
        "development_baseline":dev_base,
        "holdout_baseline":hold_base,
        "feature_profile":desc,
        "excluded_from_selection":["btc30","btc5_norm","btc15_norm","strict_brti_btc_parity","entry_price","seconds_left","ask5","ask15","confirm_count","structure_ok"],
        "orders":False,
    },sort_keys=True),flush=True)

    dev_rows=[]
    for name,fn in RULES:
        kept=[r for r in dev if fn(r)]
        m=metrics(kept,dev)
        m["rule"]=name
        m["plus10_lift"]=None if m["plus10_rate"] is None or dev_base["plus10_rate"] is None else m["plus10_rate"]-dev_base["plus10_rate"]
        m["eligible_dev"]=eligible_dev(m,dev_base)
        dev_rows.append(m)

    eligible=[x for x in dev_rows if x["eligible_dev"]]
    eligible.sort(key=lambda x:(
        float(x.get("plus10_lift") or -9),
        float(x.get("winner_retention") or 0),
        float(x.get("selected_share_retained") or 0),
        float(x.get("plus20_rate") or 0),
    ),reverse=True)
    nominee=eligible[0] if eligible else None

    hold_nom=None
    supported=False
    if nominee:
        fn=dict(RULES)[nominee["rule"]]
        kept=[r for r in hold if fn(r)]
        hold_nom=metrics(kept,hold)
        hold_nom["rule"]=nominee["rule"]
        hold_nom["plus10_lift"]=None if hold_nom["plus10_rate"] is None or hold_base["plus10_rate"] is None else hold_nom["plus10_rate"]-hold_base["plus10_rate"]
        supported=holdout_support(hold_nom,hold_base)

    print("FALSE_START_RULE_FRONTIER "+json.dumps({
        "development_baseline":dev_base,
        "eligible_development_rules":eligible[:10],
        "development_nominee":nominee,
        "holdout_baseline":hold_base,
        "holdout_nominee":hold_nom,
        "holdout_support":supported,
        "freeze_for_clean_forward_validation":bool(supported),
        "price_gate":False,
        "time_gate":False,
        "protected_thresholds_changed":False,
        "auto_promote":False,
        "orders":False,
    },sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
