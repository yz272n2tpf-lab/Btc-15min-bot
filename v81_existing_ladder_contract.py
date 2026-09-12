#!/usr/bin/env python3
"""Pure mapping/guard contract for wiring V8.1 into the EXISTING scalp ladder.

This file does not edit HTML, place orders, or own Final Outcome/Early Opportunity.
It exists so the later UI splice has one fail-closed contract and no new visual card.
"""

ALLOWED_STATUS={"WAIT","WATCH","ACTIONABLE","ACTIONABLE_EXPANSION","PROTECT"}
ALLOWED_ROUTE={"CORE","SURGE"}


def map_v81_to_existing_ladder(d):
    """Return a safe presentation payload for the already-approved scalp ladder."""
    required=(
        d.get("version")=="V8.1_GRADUATED_30_45",
        d.get("entry_band")=="30-45c",
        d.get("graduated") is True,
        d.get("manual_execution_only") is True,
        d.get("order_action") is None,
        d.get("owns_final_outcome") is False,
        d.get("owns_early_opportunity") is False,
    )
    if not all(required):
        return {"ready":False,"status":"WAIT","reason":"V81_BOUNDARY_BLOCK"}

    if not d.get("active"):
        return {"ready":False,"status":"WAIT","reason":"NO_GRADUATED_SETUP"}

    side=str(d.get("side") or "").upper()
    route=str(d.get("route") or "").upper()
    status=str(d.get("status") or "WATCH").upper()
    entry=d.get("entry_price")
    bid=d.get("current_bid")
    left=d.get("seconds_left")

    if side not in {"UP","DOWN"}: return {"ready":False,"status":"WAIT","reason":"BAD_SIDE"}
    if route not in ALLOWED_ROUTE: return {"ready":False,"status":"WAIT","reason":"BAD_ROUTE"}
    if status not in ALLOWED_STATUS: return {"ready":False,"status":"WAIT","reason":"BAD_STATUS"}
    try:
        entry=float(entry); left=float(left)
        bid=None if bid is None else float(bid)
    except (TypeError,ValueError):
        return {"ready":False,"status":"WAIT","reason":"BAD_NUMERIC"}
    if not (0.30 <= entry <= 0.45): return {"ready":False,"status":"WAIT","reason":"OUTSIDE_30_45"}
    if left <= 0: return {"ready":False,"status":"WAIT","reason":"EXPIRED"}

    targets=d.get("targets") or {}
    return {
        "ready":True,
        "source":"V8.1_GRADUATED_30_45",
        "side":side,
        "status":status,
        "route":route,
        "entry_price":entry,
        "current_bid":bid,
        "seconds_left":left,
        "targets":{
            "plus_5c":targets.get("plus_5c"),
            "plus_10c":targets.get("plus_10c"),
            "plus_20c":targets.get("plus_20c"),
        },
        "ui_destination":"EXISTING_SCALP_LADDER_ONLY",
        "new_card_allowed":False,
        "owns_final_outcome":False,
        "owns_early_opportunity":False,
        "manual_execution_only":True,
        "order_action":None,
    }


def self_test():
    base={
        "version":"V8.1_GRADUATED_30_45","entry_band":"30-45c","graduated":True,
        "manual_execution_only":True,"order_action":None,
        "owns_final_outcome":False,"owns_early_opportunity":False,
        "active":True,"side":"UP","route":"CORE","status":"ACTIONABLE",
        "entry_price":.34,"current_bid":.41,"seconds_left":420,
        "targets":{"plus_5c":.39,"plus_10c":.44,"plus_20c":.54},
    }
    r=map_v81_to_existing_ladder(base)
    assert r["ready"] and r["ui_destination"]=="EXISTING_SCALP_LADDER_ONLY" and r["new_card_allowed"] is False
    for bad in (.29,.451):
        x=dict(base);x["entry_price"]=bad;assert not map_v81_to_existing_ladder(x)["ready"]
    x=dict(base);x["route"]="SUB30_STRONG";assert not map_v81_to_existing_ladder(x)["ready"]
    x=dict(base);x["seconds_left"]=0;assert not map_v81_to_existing_ladder(x)["ready"]
    x=dict(base);x["order_action"]="BUY";assert not map_v81_to_existing_ladder(x)["ready"]
    print("V81 EXISTING-LADDER CONTRACT PASS | NO NEW CARD | 30-45 ONLY | SIGNAL ONLY | NO ORDERS")

if __name__=="__main__": self_test()
