#!/usr/bin/env python3
"""Compare protected vs fast runtime state snapshots.
Fails closed on semantic drift; reports latency/freshness deltas. NO ORDERS.
"""
import argparse,json,math
from pathlib import Path

EXACT=["contract","final_status","final_side","final_source","early_status","early_side","scalp_status","scalp_side"]
NUM=["final_confidence","early_fair","early_ask","early_edge","seconds_left","brti_age_sec","brti_gap"]
def get(d,k):
 for root in (d,d.get("state",{}),d.get("scoreboard",{})):
  if isinstance(root,dict) and k in root:return root[k]
 return None
def main():
 ap=argparse.ArgumentParser();ap.add_argument("protected");ap.add_argument("fast");a=ap.parse_args()
 p=json.loads(Path(a.protected).read_text());f=json.loads(Path(a.fast).read_text());bad=[]
 for k in EXACT:
  if get(p,k)!=get(f,k):bad.append({"field":k,"protected":get(p,k),"fast":get(f,k)})
 for k in NUM:
  x,y=get(p,k),get(f,k)
  if x is None and y is None:continue
  try:
   if abs(float(x)-float(y))>1e-12:bad.append({"field":k,"protected":x,"fast":y})
  except Exception:
   if x!=y:bad.append({"field":k,"protected":x,"fast":y})
 out={"status":"PASS" if not bad else "FAIL","semantic_mismatches":bad,"orders":False}
 print(json.dumps(out,sort_keys=True))
 if bad:raise SystemExit(2)
if __name__=="__main__":main()
