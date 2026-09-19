#!/usr/bin/env python3
"""Read-only client for BRTI WebSocket gateway V1. NO ORDERS."""
import os,time,requests
BASE_DEFAULT=os.getenv("BTC15_BRTI_GATEWAY_URL","").rstrip("/")
def state(base=None,timeout=.5):
 b=(base or BASE_DEFAULT).rstrip("/")
 if not b:raise RuntimeError("BRTI gateway URL missing")
 x=requests.get(b+"/state",timeout=timeout).json()
 if x.get("orders") is not False or x.get("signal_only") is not True:raise RuntimeError("gateway safety metadata invalid")
 o=x.get("latest")
 if not x.get("ready") or x.get("reason")!="PRIMARY_OK" or not x.get("connected") or not o:raise RuntimeError("BRTI gateway not qualified")
 if o.get("index_id")!="BRTI":raise RuntimeError("wrong index")
 source=int(o["source_ts_ms"]);age=int(time.time()*1000)-source
 if age<0 or age>5000:raise RuntimeError("BRTI source stale")
 return {"value":float(o["value"]),"source_ts_ms":source,"source_age_ms":age,"sequence":int(o["sequence"]),"owner_epoch":o["owner_epoch"],"orders":False,"signal_only":True}
def ticks(base=None,timeout=.8):
 b=(base or BASE_DEFAULT).rstrip("/")
 if not b:raise RuntimeError("BRTI gateway URL missing")
 x=requests.get(b+"/ticks",timeout=timeout).json()
 if x.get("orders") is not False or x.get("signal_only") is not True:raise RuntimeError("gateway safety metadata invalid")
 return x.get("ticks",[])
