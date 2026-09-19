#!/usr/bin/env python3
"""Read-only consumer for the authoritative shared BRTI feed. NO ORDERS."""
from __future__ import annotations
from datetime import datetime,timezone
import os,time,requests

def _ts(s):
    if not s:return None
    return datetime.fromisoformat(str(s).replace("Z","+00:00")).timestamp()

def read_shared_brti(base_url=None,timeout_s=0.8):
    base=(base_url or os.getenv("BTC15_BRTI_SHARED_URL","")).rstrip("/")
    if not base:raise RuntimeError("shared BRTI URL not configured")
    r=requests.get(base+"/state",timeout=timeout_s);r.raise_for_status();x=r.json()
    if x.get("orders") is not False:raise RuntimeError("shared BRTI safety metadata mismatch")
    value=x.get("value");success_ts=_ts(x.get("success_timestamp_utc"))
    if value is None or success_ts is None:raise RuntimeError("shared BRTI has no successful primary sample")
    # Recompute age locally from the upstream-success wall timestamp. Never trust a
    # consumer-read timestamp as freshness and never refresh age merely by reading.
    age=max(0.0,time.time()-success_ts)
    return {"value":float(value),"age_seconds":age,"sequence":int(x.get("sequence",0)),
            "status":x.get("status"),"clean_for_qualification":bool(x.get("clean_for_qualification")),
            "success_timestamp_utc":x.get("success_timestamp_utc"),
            "upstream_attempts":int(x.get("upstream_attempts",0)),"upstream_ok":int(x.get("upstream_ok",0)),
            "http_429":int(x.get("http_429",0)),"orders":False}
