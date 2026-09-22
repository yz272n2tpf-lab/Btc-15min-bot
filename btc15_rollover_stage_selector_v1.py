#!/usr/bin/env python3
"""Pure next-contract staging selector. Offline regression artifact only."""
from datetime import datetime
def choose(rows, now, prefix="KXBTC15M"):
 out=[]
 for m in rows:
  try:
   o=datetime.fromisoformat(str(m["open_time"]).replace("Z","+00:00"))
   c=datetime.fromisoformat(str(m["close_time"]).replace("Z","+00:00"))
   t=str(m["ticker"])
  except Exception: continue
  if t.startswith(prefix) and o>now and c>o: out.append((o,c,t,m))
 return min(out,key=lambda x:x[0]) if out else None
