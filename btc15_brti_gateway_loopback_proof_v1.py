#!/usr/bin/env python3
"""In-process loopback proof of gateway consumer contract. NO ORDERS."""
import json,time,urllib.request
BASE="http://127.0.0.1:8080"
def get(p):
 with urllib.request.urlopen(BASE+p,timeout=1) as r:return json.load(r)
def main():
 s=get("/state");t=get("/ticks");now=int(time.time()*1000);o=s.get("latest") or {}
 age=now-int(o.get("source_ts_ms",0));ticks=t.get("ticks") or []
 secs=sorted({int(x["source_ts_ms"])//1000 for x in ticks if now-60000<=int(x["source_ts_ms"])<now})
 contiguous=len(secs)>=59 and all(b-a==1 for a,b in zip(secs,secs[1:]))
 ok=s.get("ready") is True and s.get("reason")=="PRIMARY_OK" and o.get("index_id")=="BRTI" and 0<=age<=5000 and contiguous and s.get("orders") is False and s.get("signal_only") is True
 print("BRTI_CONSUMER_LOOPBACK | pass=%s | value=%s | source_ts_ms=%s | local_age_ms=%s | seq=%s | epoch=%s | recent_seconds=%s | contiguous=%s | NO ORDERS"%(ok,o.get("value"),o.get("source_ts_ms"),age,o.get("sequence"),o.get("owner_epoch"),len(secs),contiguous),flush=True)
 raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
