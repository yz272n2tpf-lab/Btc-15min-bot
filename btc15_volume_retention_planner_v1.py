#!/usr/bin/env python3
"""BTC15 volume retention planner V1. READ ONLY by default. NO ORDERS."""
import os,csv,json,time
from pathlib import Path
FILES={"subminute":"kalshi_subminute_unified_v1_1.csv","scalp_snapshots":"kalshi_scalp_shadow_snapshots_v1.csv","scalp_events":"kalshi_scalp_shadow_events_v1.csv"}
def inspect(root="/data"):
 out=[]
 for role,name in FILES.items():
  p=Path(root)/name
  if not p.exists(): out.append({"role":role,"path":str(p),"exists":False});continue
  s=p.stat();out.append({"role":role,"path":str(p),"exists":True,"bytes":s.st_size,"mtime":s.st_mtime,"age_seconds":max(0,time.time()-s.st_mtime)})
 return out
def plan(root="/data"):
 rows=inspect(root); total=sum(x.get("bytes",0) for x in rows)
 return {"version":"BTC15_VOLUME_RETENTION_PLANNER_V1","mode":"READ_ONLY","files":rows,"tracked_bytes":total,
 "recommendation":"ROTATION_REQUIRED" if total>=400_000_000 else "MONITOR","orders":False,"mutations":False}
if __name__=="__main__": print(json.dumps(plan(),sort_keys=True))
