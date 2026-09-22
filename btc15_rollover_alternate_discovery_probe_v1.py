#!/usr/bin/env python3
"""BTC15 alternate rollover discovery probe V1.
READ ONLY. Compares official REST discovery surfaces. NO ORDERS.
"""
import os,time,json,requests
from datetime import datetime,timezone
BASE=os.getenv("KALSHI_BASE_URL","https://api.elections.kalshi.com")
SERIES="KXBTC15M"; POLL=2.0
def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def get(path,params):
 r=requests.get(BASE+path,params=params,timeout=8,headers={"Cache-Control":"no-cache","Pragma":"no-cache","User-Agent":"btc15-rollover-probe-v1"})
 return r.status_code,r.headers,{ } if not r.content else r.json()
def tickers(obj):
 out=[]
 def walk(x):
  if isinstance(x,dict):
   t=x.get("ticker")
   if isinstance(t,str) and t.startswith(SERIES): out.append(t)
   for v in x.values(): walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(obj);return sorted(set(out))
def emit(path,status,headers,obj):
 print(json.dumps({"ts":now(),"probe":path,"http":status,"tickers":tickers(obj),
 "cache":{"age":headers.get("age"),"x-cache":headers.get("x-cache"),"cache-control":headers.get("cache-control")},
 "signal_only":True,"orders":False},sort_keys=True),flush=True)
def run_forever():
 while True:
  for name,path,params in [
  ("markets_open","/trade-api/v2/markets",{"series_ticker":SERIES,"status":"open","limit":1000}),
  ("markets_unopened","/trade-api/v2/markets",{"series_ticker":SERIES,"status":"unopened","limit":1000}),
  ("markets_all","/trade-api/v2/markets",{"series_ticker":SERIES,"limit":1000}),
  ("events_nested","/trade-api/v2/events",{"series_ticker":SERIES,"with_nested_markets":"true","limit":200})]:
   try:
    s,h,o=get(path,params);emit(name,s,h,o)
   except Exception as e:
    print(json.dumps({"ts":now(),"probe":name,"error":type(e).__name__,"signal_only":True,"orders":False}),flush=True)
  time.sleep(POLL)
if __name__=="__main__": run_forever()

# RAILWAY_BRANCH_BOUND_DEPLOY_TRIGGER_20260922
