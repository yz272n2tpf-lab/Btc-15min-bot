#!/usr/bin/env python3
"""Frozen V1 developing-move qualifier for clean SCALP event tapes.
RESEARCH/SHADOW ONLY | SIGNAL ONLY | NO ORDERS.
"""
import csv, json, sys
from pathlib import Path

MIN_ENTRY=0.02
MAX_ENTRY=0.50
MIN_LEFT=180.0
MAX_ABS_BTC15=35.0

def f(v):
    try: return float(v)
    except Exception: return None

def qualifies(r):
    e=f(r.get("entry_ask") or r.get("ask"))
    left=f(r.get("seconds_left") or r.get("left"))
    b15=f(r.get("btc_move_15s") or r.get("btc15"))
    return (e is not None and MIN_ENTRY <= e <= MAX_ENTRY
            and left is not None and left >= MIN_LEFT
            and b15 is not None and abs(b15) <= MAX_ABS_BTC15)

def main(path):
    rows=list(csv.DictReader(Path(path).open(newline="",encoding="utf-8")))
    candidates=[r for r in rows if str(r.get("record_type","")).upper()=="CANDIDATE"]
    results={str(r.get("candidate_id","")):r for r in rows if str(r.get("record_type","")).upper()=="RESULT"}
    q=[r for r in candidates if qualifies(r)]
    settled=[(r,results.get(str(r.get("candidate_id","")))) for r in q if results.get(str(r.get("candidate_id","")))]
    def hit(res,key):
        v=str((res or {}).get(key,"")).strip().lower()
        return v not in {"","none","nan","false","0","0.0"}
    out={"version":"BTC15_SCALP_DEVELOPING_MOVE_FILTER_V1","orders":False,"signal_only":True,
         "thresholds":{"min_entry":MIN_ENTRY,"max_entry":MAX_ENTRY,"min_left":MIN_LEFT,"max_abs_btc15":MAX_ABS_BTC15},
         "qualified_candidates":len(q),"unique_contracts":len({r.get("contract") for r in q}),
         "settled_results":len(settled),
         "hit_10c":sum(hit(x,"seconds_to_10c") for _,x in settled),
         "hit_20c":sum(hit(x,"seconds_to_20c") for _,x in settled)}
    print(json.dumps(out,sort_keys=True))
if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: score_scalp_developing_move_filter_v1.py EVENTS.csv")
    main(sys.argv[1])
