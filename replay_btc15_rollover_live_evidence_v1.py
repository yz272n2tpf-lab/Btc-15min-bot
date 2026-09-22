#!/usr/bin/env python3
"""Replay proven live rollover delays through the pure handoff model."""
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged,transition
CASES=[("14:00",26.048),("14:15",26.814),("14:30",41.582),("14:45",26.209)]
def replay():
 out=[]
 base=datetime(2026,9,22,14,0,tzinfo=timezone.utc)
 for i,(label,delay) in enumerate(CASES):
  o=base+timedelta(minutes=15*i);s=Staged(f"KXBTC15M-CASE{i}",o,o+timedelta(minutes=15))
  a,held,act=transition("CURRENT",s,o+timedelta(seconds=max(0,delay-.001)),[])
  if a!="CURRENT" or held is None or act!="HOLD_UNVERIFIED":raise AssertionError(label+" failed hold")
  a,held,act=transition("CURRENT",s,o+timedelta(seconds=delay),[s.ticker])
  if a!=s.ticker or held is not None or act!="VERIFIED_HANDOFF":raise AssertionError(label+" failed handoff")
  out.append((label,delay,"PASS"))
 return out
if __name__=="__main__":
 for x in replay():print(*x)
 print("LIVE-EVIDENCE REPLAY PASS | 4/4 | NO EARLY HANDOFF")
