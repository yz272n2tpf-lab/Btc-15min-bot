#!/usr/bin/env python3
"""Read-only V1 developing-move forward observer.
Consumes the clean SCALP path-export CSV and writes ONLY its own research state.
SIGNAL ONLY | NO ORDERS.
"""
import csv, io, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from score_scalp_developing_move_filter_v1 import qualifies

SOURCE=os.getenv("SCALP_CLEAN_EXPORT_URL","https://scalp-finalprod-clean-v1-production.up.railway.app/research/path-export")
STATE=Path(os.getenv("SCALP_V1_FORWARD_STATE","scalp_developing_move_v1_forward_state.json"))
FREEZE_UTC=datetime.fromisoformat("2026-09-21T18:19:00+00:00")
seen=set(); qualified={}; results={}

def parse_ts(r):
    for k in ("timestamp_utc","candidate_timestamp_utc","signal_timestamp_utc"):
        v=r.get(k)
        if v:
            try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
            except Exception:pass
    return None

def poll():
    r=requests.get(SOURCE,timeout=10,headers={"Cache-Control":"no-cache","User-Agent":"btc15-scalp-v1-forward"})
    r.raise_for_status()
    rows=list(csv.DictReader(io.StringIO(r.text)))
    for row in rows:
        cid=str(row.get("candidate_id") or "").strip()
        typ=str(row.get("record_type") or "").upper()
        if not cid: continue
        ts=parse_ts(row)
        if typ=="CANDIDATE" and ts is not None and ts>FREEZE_UTC and qualifies(row):
            qualified.setdefault(cid,row)
        elif typ=="RESULT" and cid in qualified:
            results[cid]=row
    save()

def hit(r,key):
    v=str(r.get(key,"")).strip().lower()
    return v not in {"","none","nan","false","0","0.0"}

def save():
    settled=[results[c] for c in qualified if c in results]
    out={"version":"BTC15_SCALP_DEVELOPING_MOVE_FILTER_V1_FORWARD","freeze_utc":FREEZE_UTC.isoformat(),
         "updated_utc":datetime.now(timezone.utc).isoformat(),"orders":False,"signal_only":True,
         "qualified_candidates":len(qualified),
         "unique_contracts":len({r.get("contract") for r in qualified.values()}),
         "settled_results":len(settled),"hit_10c":sum(hit(r,"seconds_to_10c") for r in settled),
         "hit_20c":sum(hit(r,"seconds_to_20c") for r in settled),
         "checkpoints":{"20":len(settled)>=20,"40":len(settled)>=40,"60":len(settled)>=60}}
    tmp=STATE.with_suffix(".tmp");tmp.write_text(json.dumps(out,sort_keys=True));tmp.replace(STATE)
    print(json.dumps(out,sort_keys=True),flush=True)

if __name__=="__main__":
    while True:
        try: poll()
        except Exception as e: print("SCALP_V1_FORWARD_WAIT | "+type(e).__name__+" | NO ORDERS",flush=True)
        time.sleep(30)

# RAILWAY_BRANCH_BOUND_DEPLOY_TRIGGER_20260921
