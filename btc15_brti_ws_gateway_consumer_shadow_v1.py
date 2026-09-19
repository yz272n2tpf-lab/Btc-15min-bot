#!/usr/bin/env python3
"""Gateway shadow consumer proof. Read-only, NO ORDERS."""
import os,time
from btc15_brti_ws_gateway_client_v1 import state,ticks
def main():
 last=None
 while True:
  try:
   s=state();a=ticks();now=int(time.time()*1000)
   recent=[x for x in a if now-60000 <= int(x["source_ts_ms"]) < now]
   uniq={int(x["source_ts_ms"])//1000:x for x in recent}
   continuity=all((b-a)==1 for a,b in zip(sorted(uniq),sorted(uniq)[1:])) if len(uniq)>1 else False
   seq=s["sequence"];advanced=last is None or seq>last
   if last is not None and not advanced: raise RuntimeError("BRTI sequence not advancing")
   last=seq
   print("BRTI_CONSUMER_SHADOW | ready=True | value=%.2f | age_ms=%s | seq=%s | advanced=%s | epoch=%s | recent60=%s | contiguous=%s | NO ORDERS"%(s["value"],s["source_age_ms"],seq,advanced,s["owner_epoch"],len(uniq),continuity),flush=True)
  except Exception as e:
   print("BRTI_CONSUMER_SHADOW | ready=False | WAIT | %s | NO ORDERS"%type(e).__name__,flush=True)
  time.sleep(10)
if __name__=="__main__":main()
