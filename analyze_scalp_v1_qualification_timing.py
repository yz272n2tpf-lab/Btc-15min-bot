#!/usr/bin/env python3
"""Offline diagnostic: compare V1 qualification to candidate path. READ ONLY."""
import csv,sys,json
from collections import defaultdict
from score_scalp_developing_move_filter_v1 import qualifies
def f(x):
 try:return float(x)
 except:return None
def analyze(path):
 rows=list(csv.DictReader(open(path,newline="",encoding="utf-8")))
 by=defaultdict(list); cand={}
 for r in rows:
  cid=str(r.get("candidate_id") or "")
  if not cid:continue
  by[cid].append(r)
  if str(r.get("record_type","")).upper()=="CANDIDATE":cand[cid]=r
 out=[]
 for cid,c in cand.items():
  if not qualifies(c):continue
  side=str(c.get("side") or c.get("direction") or "").upper()
  entry=f(c.get("entry_ask") or c.get("ask"))
  seq=by[cid]
  vals=[]
  for r in seq:
   if str(r.get("record_type","")).upper() not in ("PATH","RESULT"):continue
   # Prefer executable exit bid for the selected side, then generic price fields.
   keys=("up_bid","exit_bid","bid","price") if side=="UP" else ("down_bid","exit_bid","bid","price")
   v=next((f(r.get(k)) for k in keys if f(r.get(k)) is not None),None)
   if v is not None:vals.append(v)
  peak=max(vals) if vals else None
  out.append({"candidate_id":cid,"contract":c.get("contract"),"side":side,"entry":entry,
   "seconds_left":f(c.get("seconds_left") or c.get("left")),"btc15":f(c.get("btc_move_15s") or c.get("btc15")),
   "postqual_peak_bid":peak,"postqual_gain":None if peak is None or entry is None else peak-entry})
 return out
if __name__=="__main__":
 if len(sys.argv)!=2:raise SystemExit("usage: ... EVENTS.csv")
 print(json.dumps(analyze(sys.argv[1]),indent=2,sort_keys=True))
