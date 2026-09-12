#!/usr/bin/env python3
"""V8.1 graduated 30-45c scalp integration adapter.

Pure/read-only mapping layer. SIGNAL ONLY. NO ORDERS.
Does not fetch data, place orders, alter Final Outcome, Early Opportunity,
BRTI, Kalshi timing, or qualification thresholds.
"""
from dataclasses import dataclass, asdict
from typing import Optional

MIN_ENTRY=0.30
MAX_ENTRY=0.45
ALLOWED_ROUTES={"CORE","SURGE"}

@dataclass(frozen=True)
class ScalpSignal:
    engine: str
    side: str
    entry_ask: float
    current_bid: Optional[float]
    route: str
    seconds_left: float
    target_5c: float
    target_10c: float
    target_20c: float
    status: str
    signal_only: bool=True
    automatic_order: bool=False


def map_graduated_30_45(*, side:str, entry_ask:float, current_bid:Optional[float], route:str, seconds_left:float):
    side=side.upper(); route=route.upper()
    if side not in {"UP","DOWN"}: return None
    if not (MIN_ENTRY <= float(entry_ask) <= MAX_ENTRY): return None
    if route not in ALLOWED_ROUTES: return None
    if seconds_left <= 0: return None
    bid=None if current_bid is None else float(current_bid)
    gain=None if bid is None else bid-float(entry_ask)
    if gain is None: status="WATCH"
    elif gain >= .20: status="PROTECT"
    elif gain >= .10: status="ACTIONABLE_EXPANSION"
    elif gain >= .05: status="ACTIONABLE"
    else: status="WATCH"
    s=ScalpSignal(
        engine="V81_GRADUATED_30_45",
        side=side,
        entry_ask=float(entry_ask),
        current_bid=bid,
        route=route,
        seconds_left=float(seconds_left),
        target_5c=min(1.0,float(entry_ask)+.05),
        target_10c=min(1.0,float(entry_ask)+.10),
        target_20c=min(1.0,float(entry_ask)+.20),
        status=status,
    )
    return asdict(s)


def self_test():
    good=map_graduated_30_45(side="UP",entry_ask=.34,current_bid=.45,route="CORE",seconds_left=600)
    assert good and good["status"]=="ACTIONABLE_EXPANSION"
    assert good["signal_only"] is True and good["automatic_order"] is False
    assert map_graduated_30_45(side="DOWN",entry_ask=.29,current_bid=.40,route="CORE",seconds_left=600) is None
    assert map_graduated_30_45(side="DOWN",entry_ask=.36,current_bid=.40,route="SUB30_STRONG",seconds_left=600) is None
    print("V81_30_45_ADAPTER_SELFTEST_PASS | SIGNAL_ONLY | NO_ORDERS")

if __name__=="__main__": self_test()
