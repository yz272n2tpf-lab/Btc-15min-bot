#!/usr/bin/env python3
"""Read-only current production dashboard-state probe. NO ORDERS."""
import json,os,urllib.request
BASE=os.environ["BTC15_PRODUCTION_STATE_BASE"].rstrip("/")
with urllib.request.urlopen(BASE+"/dashboard_state.json",timeout=3) as r:d=json.load(r)
def pick(o,*ks):
 for k in ks:
  if isinstance(o,dict) and k in o:return o[k]
 return None
print("BTC15_PROD_STATE_PROBE | keys=%s | contract=%s | ts=%s | seconds_left=%s | NO ORDERS"%(",".join(sorted(d.keys())[:40]),pick(d,"contract","ticker"),pick(d,"timestamp_utc","timestamp","generated_at"),pick(d,"seconds_left","remaining_sec")),flush=True)
