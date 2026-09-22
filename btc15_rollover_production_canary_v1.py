#!/usr/bin/env python3
"""BTC15 rollover pre-discovery production-environment CANARY.
Observe/compare only. Never selects active market, publishes signals, or places orders.
Uses existing authenticated kalshi_get/parse_dt when imported by production core.
"""
from datetime import datetime,timezone
_state={"staged":None,"last_report":None}
def observe(kalshi_get,parse_dt,now=None,emit=print):
 now=now or datetime.now(timezone.utc)
 try:
  data=kalshi_get("/trade-api/v2/markets",params={"status":"unopened","series_ticker":"KXBTC15M","limit":1000})
  raw=data.get("markets",[])
  emit(f"ROLLOVER CANARY UNOPENED RESPONSE | count={len(raw)} | OBSERVE ONLY | NO ORDERS")
  rows=[]
  for m in raw:
   t=str(m.get("ticker",""));op=parse_dt(m.get("open_time"));cl=parse_dt(m.get("close_time"))
   emit("ROLLOVER CANARY UNOPENED ITEM | ticker={} | open={} | close={} | status={} | OBSERVE ONLY | NO ORDERS".format(t,m.get("open_time"),m.get("close_time"),m.get("status")))
   if t.startswith("KXBTC15M") and op and cl and op>now and (cl-op).total_seconds()==900:
    rows.append((op,cl,t))
  if rows:
   op,cl,t=min(rows)
   st=_state["staged"]
   if st is None or st["ticker"]!=t:
    _state["staged"]={"ticker":t,"open":op,"close":cl}
    emit(f"ROLLOVER CANARY STAGED | {t} | open {op.isoformat()} | OBSERVE ONLY | NO ORDERS")
 except Exception as exc:
  emit(f"ROLLOVER CANARY WAIT | {type(exc).__name__} | OBSERVE ONLY | NO ORDERS")
def compare(actual_ticker,now=None,emit=print):
 now=now or datetime.now(timezone.utc);st=_state["staged"]
 if not st or now<st["open"]:return None
 ok=str(actual_ticker)==st["ticker"]
 key=(st["ticker"],str(actual_ticker),ok)
 if _state["last_report"]!=key:
  emit(f"ROLLOVER CANARY COMPARE | staged {st['ticker']} | actual {actual_ticker} | match {ok} | +{(now-st['open']).total_seconds():.3f}s | OBSERVE ONLY | NO ORDERS")
  _state["last_report"]=key
 return ok
