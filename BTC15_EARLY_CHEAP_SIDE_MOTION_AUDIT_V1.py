#!/usr/bin/env python3
import csv, json, time, urllib.request
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

SRC="kalshi_scalp_shadow_snapshots_v1.csv"
OUT="early_cheap_side_motion_v1_report.json"
BASES=[
    "https://api.elections.kalshi.com/trade-api/v2",
    "https://external-api.kalshi.com/trade-api/v2",
]

def f(x):
    try: return float(x)
    except: return None

def dt(x):
    return datetime.fromisoformat(str(x).replace("Z","+00:00"))

def result_for(ticker):
    for base in BASES:
        try:
            req=urllib.request.Request(f"{base}/markets/{ticker}",headers={"User-Agent":"btc15-research/1.0"})
            with urllib.request.urlopen(req,timeout=15) as r:
                m=json.load(r).get("market",{})
            if str(m.get("status","")).lower()=="finalized":
                z=str(m.get("result","")).lower()
                if z=="yes": return "UP"
                if z=="no": return "DOWN"
        except Exception:
            pass
    return None

def qualify(row,side):
    sign=1 if side=="UP" else -1
    ask=row["up_ask"] if side=="UP" else row["down_ask"]
    ask15=row["up_ask_move_15s"] if side=="UP" else row["down_ask_move_15s"]
    vals=[ask,ask15,row["btc_move_5s"],row["btc_move_15s"],row["btc_move_30s"],row["btc_gap"],row["seconds_left"]]
    if any(v is None for v in vals): return None
    a5=sign*row["btc_move_5s"]
    a15=sign*row["btc_move_15s"]
    a30=sign*row["btc_move_30s"]
    wrong=max(0.0,-sign*row["btc_gap"])
    projected=max(0.0,a30)*4.0
    ok=(
        360<=row["seconds_left"]<=780
        and ask<=.50
        and a5>=4.0 and a15>=8.0 and a30>=15.0
        and projected>=wrong
        and ask15<=.02
    )
    if not ok: return None
    return {
        "contract":row["contract"],"timestamp":row["timestamp"],"side":side,
        "ask":ask,"seconds_left":row["seconds_left"],"a5":a5,"a15":a15,"a30":a30,
        "wrong_distance":wrong,"projected_2m":projected,"ask_move_15s":ask15,
    }

def summary(calls,denom):
    if not calls:
        return {"n":0,"coverage":0}
    return {
        "n":len(calls),
        "coverage":len(calls)/denom if denom else None,
        "accuracy":mean(x["correct"] for x in calls),
        "avg_ask":mean(x["ask"] for x in calls),
        "median_ask":median(x["ask"] for x in calls),
        "ideal_25_35_share":mean(.25<=x["ask"]<=.35 for x in calls),
        "le50_share":mean(x["ask"]<=.50 for x in calls),
        "avg_minutes_left":mean(x["seconds_left"]/60 for x in calls),
        "median_minutes_left":median(x["seconds_left"]/60 for x in calls),
        "up_calls":sum(x["side"]=="UP" for x in calls),
        "down_calls":sum(x["side"]=="DOWN" for x in calls),
    }

by=defaultdict(list)
with open(SRC,newline="") as fh:
    for z in csv.DictReader(fh):
        row={"timestamp":z["timestamp_utc"],"contract":z["contract"]}
        for k in ["seconds_left","btc_gap","btc_move_5s","btc_move_15s","btc_move_30s",
                  "up_ask","down_ask","up_ask_move_15s","down_ask_move_15s"]:
            row[k]=f(z.get(k))
        by[row["contract"]].append(row)
for g in by.values():
    g.sort(key=lambda x:x["timestamp"])

contracts=sorted(by,key=lambda t: by[t][0]["timestamp"])
truth={}; unresolved=[]
for i,t in enumerate(contracts):
    z=result_for(t)
    if z: truth[t]=z
    else: unresolved.append(t)
    if i<len(contracts)-1: time.sleep(.06)

calls=[]
for t in contracts:
    if t not in truth: continue
    chosen=None
    for row in by[t]:
        q=[x for x in (qualify(row,"UP"),qualify(row,"DOWN")) if x is not None]
        if q:
            q.sort(key=lambda x:x["a30"],reverse=True)
            chosen=q[0]; break
    if chosen:
        chosen["correct"]=int(chosen["side"]==truth[t])
        calls.append(chosen)

resolved_contracts=[t for t in contracts if t in truth]
mid=len(resolved_contracts)//2
first=set(resolved_contracts[:mid]); second=set(resolved_contracts[mid:])
first_calls=[x for x in calls if x["contract"] in first]
second_calls=[x for x in calls if x["contract"] in second]
all_s=summary(calls,len(resolved_contracts)); s1=summary(first_calls,len(first)); s2=summary(second_calls,len(second))

gate={
    "calls_ge_15":all_s.get("n",0)>=15,
    "accuracy_ge_93":all_s.get("accuracy",0)>=.93,
    "avg_ask_le_40c":all_s.get("avg_ask",99)<=.40,
    "median_ask_le_40c":all_s.get("median_ask",99)<=.40,
    "avg_time_ge_7m":all_s.get("avg_minutes_left",0)>=7,
    "all_entries_le_50c":all(x["ask"]<=.50 for x in calls),
    "up_down_balance_ge_3_each":all_s.get("up_calls",0)>=3 and all_s.get("down_calls",0)>=3,
    "second_half_n_ge_6":s2.get("n",0)>=6,
    "second_half_accuracy_ge_90":s2.get("accuracy",0)>=.90,
}
report={
    "source":SRC,
    "source_contracts":len(contracts),
    "resolved_contracts":len(resolved_contracts),
    "unresolved_contracts":len(unresolved),
    "combined":all_s,
    "chronological_first_half":s1,
    "chronological_second_half":s2,
    "historical_screen_gate":gate,
    "historical_screen_pass":all(gate.values()),
    "production_changed":False,
    "orders":False,
}
with open(OUT,"w") as fh: json.dump(report,fh,indent=2,sort_keys=True)
print(json.dumps(report,indent=2,sort_keys=True))
