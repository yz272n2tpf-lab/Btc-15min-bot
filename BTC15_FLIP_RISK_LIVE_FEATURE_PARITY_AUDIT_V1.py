#!/usr/bin/env python3
"""
BTC15 numeric Flip Risk live feature-parity audit V1.

READ ONLY | NO SIGNAL CHANGES | NO ORDERS

Compares the actual production dashboard state ingredients with the frozen
historical calibration feature definitions. This script intentionally does NOT
produce a live Flip Risk number. A calibrated model may not be projected live
until its feature source/semantics match training.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

VERSION = "BTC15_FLIP_RISK_LIVE_FEATURE_PARITY_AUDIT_V1"
URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"

HISTORICAL_SOURCE = "btc_35d_live_cache.csv / Coinbase 1m OHLCV"
HISTORICAL_FEATURES = [
    "elapsed", "remaining", "current_side",
    "dist_target", "abs_dist_target", "dist_target_pct",
    "move_from_start", "move_from_start_pct",
    "move1", "move2", "move3", "move5",
    "support1", "support2", "support3", "support5",
    "range5", "vol5", "dist_per_min_remaining", "dist_over_range5",
]
MONTHS={m:i+1 for i,m in enumerate(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"])}


def f(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def parse_contract(ticker):
    m=re.search(r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",str(ticker).upper())
    if not m: return None,None
    yy,mon,dd,hh,mm=m.groups()
    wall=datetime(2000+int(yy),MONTHS[mon],int(dd),int(hh),int(mm),tzinfo=ZoneInfo("America/New_York"))
    close=wall.astimezone(timezone.utc)
    return close-timedelta(minutes=15),close


def parse_ts(v):
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


print(f"=== {VERSION} ===",flush=True)
print("Historical gate already passed for SHADOW VALIDATION ONLY; checking exact live feature semantics now.",flush=True)
r=requests.get(URL,timeout=15,headers={"Cache-Control":"no-cache"})
print("Production state HTTP:",r.status_code,flush=True)
r.raise_for_status()
d=r.json()

contract=str(d.get("contract") or "")
market=d.get("market") if isinstance(d.get("market"),dict) else {}
timer=d.get("timer") if isinstance(d.get("timer"),dict) else {}
chart=d.get("chart") if isinstance(d.get("chart"),dict) else {}
points=chart.get("points") if isinstance(chart.get("points"),list) else []

seconds=f(timer.get("seconds_left")); target=f(market.get("target")); brti=f(market.get("brti_value"))
if seconds is None: seconds=f(d.get("seconds_left"))
start,close=parse_contract(contract)

print("Contract:",contract)
print("Historical calibrated feature source:",HISTORICAL_SOURCE)
print("Live authoritative price field: market.brti_value (direct BRTI dashboard state)")
print("seconds_left:",seconds,"target:",target,"brti_value:",brti)
print("chart point count:",len(points))
print("chart point keys:",sorted(set().union(*(p.keys() for p in points if isinstance(p,dict)))) if points else [])

parsed=[]
for p in points:
    if not isinstance(p,dict): continue
    t=parse_ts(p.get("t")); v=f(p.get("brti"))
    if t is not None and v is not None: parsed.append((t,v,p))
parsed.sort(key=lambda x:x[0])
if parsed:
    span=(parsed[-1][0]-parsed[0][0]).total_seconds()
    spacings=[(parsed[i][0]-parsed[i-1][0]).total_seconds() for i in range(1,len(parsed)) if parsed[i][0]>parsed[i-1][0]]
    med_spacing=statistics.median(spacings) if spacings else None
    first_lag=(parsed[0][0]-start).total_seconds() if start else None
    print("chart span sec:",round(span,3),"median spacing sec:",None if med_spacing is None else round(med_spacing,3))
    print("earliest chart point vs canonical start sec:",None if first_lag is None else round(first_lag,3))
else:
    span=0; med_spacing=None; first_lag=None

# Historical model source semantics from the frozen validator:
# px() uses Coinbase Close; range5 uses 5-minute High max - Low min;
# vol5 uses std of Coinbase Close pct_change. The live dashboard chart exposes
# sampled BRTI points, not the same Coinbase OHLCV observations.
point_keys=set().union(*(p.keys() for p in points if isinstance(p,dict))) if points else set()
live_has_ohlc=all(k in point_keys for k in ("open","high","low","close"))
live_has_volume="volume" in point_keys

availability={
    "elapsed_remaining": seconds is not None,
    "target_distance": target is not None and brti is not None,
    "sampled_price_history": bool(parsed and span>=300),
    "historical_equivalent_ohlc": live_has_ohlc,
    "historical_equivalent_volume": live_has_volume,
}

feature_status={}
for name in HISTORICAL_FEATURES:
    if name in {"elapsed","remaining"}:
        feature_status[name]=(availability["elapsed_remaining"],"timer semantics available")
    elif name in {"current_side","dist_target","abs_dist_target","dist_target_pct","dist_per_min_remaining"}:
        feature_status[name]=(availability["target_distance"],"derivable from live direct BRTI + Kalshi target")
    elif name in {"move_from_start","move_from_start_pct","move1","move2","move3","move5","support1","support2","support3","support5"}:
        feature_status[name]=(False,"source mismatch: historical Coinbase Close vs live sampled direct BRTI")
    elif name=="range5":
        feature_status[name]=(False,"historical 1m OHLC High-Low window unavailable with equivalent semantics")
    elif name=="vol5":
        feature_status[name]=(False,"historical Coinbase 1m Close pct-change volatility != live sampled BRTI cadence")
    elif name=="dist_over_range5":
        feature_status[name]=(False,"depends on non-parity range5")
    else:
        feature_status[name]=(False,"not proven")

print("\n=== FEATURE PARITY MATRIX ===")
for name in HISTORICAL_FEATURES:
    ok,why=feature_status[name]
    print(f"{name}: {'EXACT' if ok else 'NOT_EXACT'} | {why}")

exact=sum(1 for ok,_ in feature_status.values() if ok)
not_exact=len(feature_status)-exact
exact_parity=not_exact==0
print("\n=== DECISION ===")
print(f"exact_features={exact}/{len(feature_status)} | not_exact={not_exact}")
print("LIVE_FEATURE_PARITY=" + ("PASS" if exact_parity else "FAIL"))
print("NUMERIC_FLIP_RISK_LIVE_ALLOWED=False")
if not exact_parity:
    print("NEXT_SAFE_STEP=RETRAIN_AND_CALIBRATE_ON_DIRECT_BRTI_ALIGNED_FEATURES")
else:
    print("NEXT_SAFE_STEP=FREEZE_FRESH_FORWARD_SHADOW_SAMPLE")
print("PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False")
print("STATE_KEYS="+json.dumps(sorted(d.keys())))
