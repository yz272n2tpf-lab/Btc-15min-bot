#!/usr/bin/env python3
"""Read-only consumer adapter for authoritative BRTI transport. NO ORDERS."""
from __future__ import annotations
import os
from datetime import datetime,timezone

def read_shared_brti(base_url=None,timeout_s=0.8):
    mode=os.getenv("BTC15_BRTI_TRANSPORT","legacy_shared_http").strip().lower()
    if mode=="websocket_gateway":
        from btc15_brti_ws_gateway_client_v1 import state
        s=state(base=base_url or os.getenv("BTC15_BRTI_GATEWAY_URL",""),timeout=timeout_s)
        return {"value":s["value"],"age_seconds":s["source_age_ms"]/1000.0,
                "sequence":s["sequence"],"status":"PRIMARY_OK","clean_for_qualification":True,
                "success_timestamp_utc":datetime.fromtimestamp(s["source_ts_ms"]/1000.0,tz=timezone.utc).isoformat().replace("+00:00","Z"),"upstream_attempts":0,"upstream_ok":0,
                "http_429":0,"orders":False,"signal_only":True,
                "owner_epoch":s["owner_epoch"],"source_ts_ms":s["source_ts_ms"]}
    import time,requests
    base=(base_url or os.getenv("BTC15_BRTI_SHARED_URL","")).rstrip("/")
    if not base:raise RuntimeError("shared BRTI URL not configured")
    r=requests.get(base+"/state",timeout=timeout_s);r.raise_for_status();x=r.json()
    if x.get("orders") is not False:raise RuntimeError("shared BRTI safety metadata mismatch")
    value=x.get("value");raw=x.get("success_timestamp_utc")
    success_ts=None if not raw else datetime.fromisoformat(str(raw).replace("Z","+00:00")).timestamp()
    if value is None or success_ts is None:raise RuntimeError("shared BRTI has no successful primary sample")
    age=max(0.0,time.time()-success_ts)
    return {"value":float(value),"age_seconds":age,"sequence":int(x.get("sequence",0)),
            "status":x.get("status"),"clean_for_qualification":bool(x.get("clean_for_qualification")),
            "success_timestamp_utc":x.get("success_timestamp_utc"),
            "upstream_attempts":int(x.get("upstream_attempts",0)),"upstream_ok":int(x.get("upstream_ok",0)),
            "http_429":int(x.get("http_429",0)),"orders":False}
