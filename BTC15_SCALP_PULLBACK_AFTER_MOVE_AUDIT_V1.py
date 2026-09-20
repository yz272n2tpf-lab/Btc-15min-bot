#!/usr/bin/env python3
import csv, json
from collections import defaultdict
from statistics import mean, median
from datetime import datetime

SRC="kalshi_scalp_shadow_events_v1.csv"
OUT="scalp_pullback_after_move_v1_report.json"

def f(x):
    try: return float(x)
    except: return None

def b(x):
    return str(x).strip().lower()=="true"

def ts(x):
    return datetime.fromisoformat(str(x).replace("Z","+00:00"))

def aligned_btc30(r):
    if r["btc30"] is None: return None
    s=1 if r["side"]=="UP" else -1
    return r["btc30"]*s

def base_ok(r):
    a=aligned_btc30(r)
    return r["sec"] is not None and r["sec"]>=120 and a is not None and a>=15

def cand_ok(r):
    return base_ok(r) and r["drawdown"] is not None and r["drawdown"]>=.04

def summarize(rows):
    if not rows: return {"n":0}
    return {
        "n":len(rows),
        "arm5_rate":mean(r["maxgain"] is not None and r["maxgain"]>=.05 for r in rows),
        "hit10_rate":mean(r["hit10"] for r in rows),
        "hit15_rate":mean(r["hit15"] for r in rows),
        "hit20_rate":mean(r["hit20"] for r in rows),
        "avg_ask":mean(r["ask"] for r in rows if r["ask"] is not None),
        "median_ask":median(r["ask"] for r in rows if r["ask"] is not None),
        "avg_seconds_left":mean(r["sec"] for r in rows if r["sec"] is not None),
        "avg_adverse":mean(r["adverse"] for r in rows if r["adverse"] is not None),
        "bands":{
            "le20c":sum((r["ask"] or 99)<=.20 for r in rows),
            "21_35c":sum(r["ask"] is not None and .20<r["ask"]<=.35 for r in rows),
            "36_50c":sum(r["ask"] is not None and .35<r["ask"]<=.50 for r in rows),
            "gt50c":sum(r["ask"] is not None and r["ask"]>.50 for r in rows),
        }
    }

by=defaultdict(list)
with open(SRC,newline="") as fh:
    for z in csv.DictReader(fh):
        r={
            "event_id":z["event_id"],
            "contract":z["contract"],
            "side":z["side"].upper(),
            "time":ts(z["entry_timestamp_utc"]),
            "ask":f(z["entry_ask"]),
            "sec":f(z["seconds_left"]),
            "btc30":f(z["btc_move_30s"]),
            "drawdown":f(z["drawdown_from_high"]),
            "maxgain":f(z["max_gain_vs_entry_ask"]),
            "adverse":f(z["max_adverse_vs_entry_ask"]),
            "hit10":b(z["hit_10c"]),
            "hit15":b(z["hit_15c"]),
            "hit20":b(z["hit_20c"]),
        }
        by[r["contract"]].append(r)
for g in by.values():
    g.sort(key=lambda x:x["time"])

base=[]
cand=[]
delays=[]
baseline_winners=0
baseline_winners_retained=0
for contract,g in by.items():
    q=next((r for r in g if base_ok(r)),None)
    if q is None: continue
    base.append(q)
    if q["hit10"]: baseline_winners+=1

    deadline=(q["time"].timestamp()+30)
    c=None
    for r in g:
        if r["time"] < q["time"]: continue
        if r["time"].timestamp() > deadline: break
        if r["side"]!=q["side"]: continue
        if cand_ok(r):
            c=r; break
    if c is not None:
        cand.append(c)
        delays.append((c["time"]-q["time"]).total_seconds())
        if q["hit10"]: baseline_winners_retained+=1

bs=summarize(base)
cs=summarize(cand)
ret=len(cand)/len(base) if base else 0
winner_ret=baseline_winners_retained/baseline_winners if baseline_winners else 0
lift=cs.get("hit10_rate",0)-bs.get("hit10_rate",0)
avg_delay=mean(delays) if delays else None
gate={
    "opportunity_retention_ge_70":ret>=.70,
    "winner_retention_ge_80":winner_ret>=.80,
    "hit10_precision_lift_ge_5pp":lift>=.05,
    "avg_ask_not_worse":cs.get("avg_ask",99)<=bs.get("avg_ask",99),
    "avg_delay_le_30s":avg_delay is not None and avg_delay<=30,
    "no_absolute_price_gate":True,
}
report={
    "source":SRC,
    "contracts_in_source":len(by),
    "baseline":bs,
    "candidate":cs,
    "candidate_avg_delay_seconds":avg_delay,
    "opportunity_retention":ret,
    "baseline_hit10_winners":baseline_winners,
    "baseline_hit10_winners_retained":baseline_winners_retained,
    "winner_id_retention":winner_ret,
    "hit10_precision_lift_pp":lift*100,
    "historical_screen_gate":gate,
    "historical_screen_pass":all(gate.values()),
    "production_changed":False,
    "orders":False,
}
with open(OUT,"w") as fh: json.dump(report,fh,indent=2,sort_keys=True)
print(json.dumps(report,indent=2,sort_keys=True))
