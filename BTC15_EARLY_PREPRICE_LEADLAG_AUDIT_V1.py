#!/usr/bin/env python3
import csv, json, time, urllib.request
from collections import defaultdict
from statistics import mean, median

CSV_PATH = "kalshi_early_conf_shadow_v1_2.csv"
OUT_PATH = "early_preprice_leadlag_v1_report.json"
BASES = [
    "https://api.elections.kalshi.com/trade-api/v2",
    "https://external-api.kalshi.com/trade-api/v2",
]

def f(x):
    try: return float(x)
    except: return None

def get_result(ticker):
    for base in BASES:
        try:
            req=urllib.request.Request(f"{base}/markets/{ticker}", headers={"User-Agent":"btc15-research/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                m=json.load(r).get("market",{})
            status=str(m.get("status","")).lower().strip()
            result=str(m.get("result","")).lower().strip()
            if status=="finalized" and result in ("yes","no"):
                return "UP" if result=="yes" else "DOWN"
        except Exception:
            pass
    return None

def baseline(r):
    return (
        r["ask"] <= .45 and r["fair"] >= .75 and r["edge"] >= .08
        and 120 <= r["sec"] <= 600 and abs(r["gap"]) >= 25
    )

def candidate(r):
    vals=[r["fm15"],r["fm30"],r["am15"],r["am30"]]
    return (
        all(v is not None for v in vals)
        and r["ask"] <= .45 and r["fair"] >= .75 and r["edge"] >= .08
        and 360 <= r["sec"] <= 660 and abs(r["gap"]) >= 25
        and r["fm15"] >= .02 and r["fm30"] >= .02
        and r["am15"] <= .01 and r["am30"] <= .02
    )

def first(g,p):
    for r in g:
        if p(r): return r
    return None

def stats(calls, denom):
    if not calls:
        return {"n":0,"coverage":0}
    return {
        "n":len(calls),
        "coverage":len(calls)/denom if denom else None,
        "accuracy":mean(x["correct"] for x in calls),
        "avg_ask":mean(x["ask"] for x in calls),
        "median_ask":median(x["ask"] for x in calls),
        "share_25_35":mean(.25 <= x["ask"] <= .35 for x in calls),
        "share_le50":mean(x["ask"] <= .50 for x in calls),
        "avg_minutes_left":mean(x["sec"]/60 for x in calls),
        "median_minutes_left":median(x["sec"]/60 for x in calls),
        "up_calls":sum(x["side"]=="UP" for x in calls),
        "down_calls":sum(x["side"]=="DOWN" for x in calls),
    }

raw=defaultdict(list)
with open(CSV_PATH,newline="") as fh:
    for z in csv.DictReader(fh):
        r={
            "ts":z["timestamp_utc"], "contract":z["contract"], "side":z["preferred_side"].upper(),
            "ask":f(z["preferred_ask"]), "fair":f(z["preferred_fair"]), "edge":f(z["edge"]),
            "sec":f(z["seconds_left"]), "gap":f(z["btc_gap"]),
            "fm15":f(z["fair_move_15s"]), "fm30":f(z["fair_move_30s"]),
            "am15":f(z["ask_move_15s"]), "am30":f(z["ask_move_30s"]),
        }
        if all(r[k] is not None for k in ["ask","fair","edge","sec","gap"]):
            raw[r["contract"]].append(r)
for g in raw.values():
    g.sort(key=lambda x:x["ts"])

truth={}
unresolved=[]
for i,ticker in enumerate(sorted(raw)):
    side=get_result(ticker)
    if side: truth[ticker]=side
    else: unresolved.append(ticker)
    if i < len(raw)-1: time.sleep(.08)

base_calls=[]; cand_calls=[]
base_by={}; cand_by={}
for ticker,g in raw.items():
    if ticker not in truth: continue
    b=first(g,baseline); c=first(g,candidate)
    if b:
        b=dict(b); b["correct"]=int(b["side"]==truth[ticker]); base_calls.append(b); base_by[ticker]=b
    if c:
        c=dict(c); c["correct"]=int(c["side"]==truth[ticker]); cand_calls.append(c); cand_by[ticker]=c

earlier=[]; incremental=[]
for ticker,c in cand_by.items():
    b=base_by.get(ticker)
    if b is None:
        incremental.append(c)
    elif c["ts"] < b["ts"]:
        # ISO timestamps are lexicographically sortable here.
        from datetime import datetime
        ct=datetime.fromisoformat(c["ts"].replace("Z","+00:00"))
        bt=datetime.fromisoformat(b["ts"].replace("Z","+00:00"))
        earlier.append((ticker,(bt-ct).total_seconds()))

cs=stats(cand_calls,len(truth))
gate={
    "calls_ge_12": cs.get("n",0) >= 12,
    "accuracy_ge_93": cs.get("accuracy",0) >= .93,
    "avg_ask_le_40c": cs.get("avg_ask",9) <= .40,
    "median_ask_le_40c": cs.get("median_ask",9) <= .40,
    "avg_time_ge_7m": cs.get("avg_minutes_left",0) >= 7,
    "all_entries_le_45c": all(x["ask"] <= .45 for x in cand_calls),
    "earlier_or_incremental_ge_3": len(earlier) >= 3 or len(incremental) >= 3,
}
report={
    "source":CSV_PATH,
    "source_contracts":len(raw),
    "officially_resolved_contracts":len(truth),
    "unresolved_contracts":len(unresolved),
    "protected_tier1_reference":stats(base_calls,len(truth)),
    "preprice_leadlag_v1":cs,
    "candidate_overlap_with_tier1":sum(t in base_by for t in cand_by),
    "candidate_incremental_contracts":len(incremental),
    "candidate_incremental_accuracy":mean(x["correct"] for x in incremental) if incremental else None,
    "candidate_earlier_than_tier1":len(earlier),
    "candidate_median_lead_seconds":median(x[1] for x in earlier) if earlier else None,
    "historical_screen_gate":gate,
    "historical_screen_pass":all(gate.values()),
    "orders":False,
    "production_changed":False,
}
with open(OUT_PATH,"w") as fh: json.dump(report,fh,indent=2,sort_keys=True)
print(json.dumps(report,indent=2,sort_keys=True))
