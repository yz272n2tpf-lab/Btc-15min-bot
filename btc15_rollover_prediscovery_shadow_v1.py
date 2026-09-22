#!/usr/bin/env python3
"""BTC15 rollover pre-discovery shadow V1.
Read-only proof: stage next unopened ticker before boundary; never activates early.
SIGNAL ONLY | NO ORDERS | NO PRODUCTION MUTATION.
"""
import os,time,json,requests
from datetime import datetime,timezone
BASE=os.getenv("KALSHI_BASE_URL","https://api.elections.kalshi.com")
POLL=float(os.getenv("PREDISCOVERY_POLL_SECONDS","2"))
s=requests.Session(); staged=None
def now(): return datetime.now(timezone.utc)
def get(status):
 r=s.get(BASE+"/trade-api/v2/markets",params={"status":status,"series_ticker":"KXBTC15M","limit":1000},timeout=5,headers={"Cache-Control":"no-cache","User-Agent":"btc15-prediscovery-shadow-v1"})
 r.raise_for_status();return r.json().get("markets",[])
def dt(v): return datetime.fromisoformat(str(v).replace("Z","+00:00"))
def choose_next(rows,t):
 x=[]
 for m in rows:
  try:o=dt(m["open_time"]);c=dt(m["close_time"])
  except:continue
  if str(m.get("ticker","")).startswith("KXBTC15M") and o>t:x.append((o,c,m))
 return min(x,key=lambda z:z[0]) if x else None
def main():
 global staged
 print("BTC15 PREDISCOVERY SHADOW V1 START | READ ONLY | SIGNAL ONLY | NO ORDERS",flush=True)
 while True:
  t=now()
  try:
   q=choose_next(get("unopened"),t)
   if q:
    o,c,m=q; ticker=m["ticker"]
    if staged is None or staged["ticker"]!=ticker:
     staged={"ticker":ticker,"open":o,"close":c,"staged_at":t}
     print(json.dumps({"event":"NEXT_TICKER_STAGED","ticker":ticker,"open_utc":o.isoformat(),"seconds_before_open":round((o-t).total_seconds(),3),"signal_only":True,"orders":False}),flush=True)
  except Exception as e: print(json.dumps({"event":"WAIT","error":type(e).__name__,"orders":False}),flush=True)
  time.sleep(POLL)
if __name__=="__main__":main()

# RAILWAY_SHADOW_DEPLOY_TRIGGER_20260922

# DEPLOY_CORRECTED_VERIFIER_20260922
