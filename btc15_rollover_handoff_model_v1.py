#!/usr/bin/env python3
"""Pure state-machine model for production rollover pre-discovery.
Regression artifact only: no network, no websocket, no publication, no orders.
"""
from dataclasses import dataclass
from datetime import datetime
@dataclass
class Staged:
 ticker:str; open_time:datetime; close_time:datetime
def transition(active, staged, now, open_tickers):
 """Return (active, staged, action). Never activates before staged.open_time."""
 if staged is None:return active,None,"NO_STAGED"
 if now < staged.open_time:return active,staged,"HOLD_PREOPEN"
 if staged.ticker not in set(open_tickers):return active,staged,"HOLD_UNVERIFIED"
 return staged.ticker,None,"VERIFIED_HANDOFF"
