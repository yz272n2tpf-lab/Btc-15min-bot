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
    import time, math
    x = _legacy_get("/state", base_url, timeout_s)
    _legacy_metadata(x)
    ts, value = x.get("source_ts_ms"), x.get("value")
    if type(ts) is not int or ts <= 0 or isinstance(value, bool):
        raise RuntimeError("shared BRTI has no source-timestamped sample")
    value = float(value)
    age = time.time() - ts / 1000.0
    if (not math.isfinite(value) or not 1000 < value < 1_000_000
            or not 0 <= age <= 5.0 or x.get("status") != "PRIMARY_OK"
            or x.get("clean_for_qualification") is not True):
        raise RuntimeError("shared BRTI source not qualified/fresh")
    return {"value":value,"age_seconds":age,"sequence":int(x.get("sequence",0)),
            "status":"PRIMARY_OK","clean_for_qualification":True,
            "success_timestamp_utc":datetime.fromtimestamp(ts/1000.0,tz=timezone.utc).isoformat(),
            "source_ts_ms":ts,"owner_epoch":x["owner_epoch"],
            "upstream_attempts":int(x.get("upstream_attempts",0)),"upstream_ok":int(x.get("upstream_ok",0)),
            "http_429":int(x.get("http_429",0)),"orders":False,"signal_only":True}


def _legacy_get(path, base_url, timeout_s):
    import requests
    base = (base_url or os.getenv("BTC15_BRTI_SHARED_URL", "")).rstrip("/")
    if not base:
        raise RuntimeError("shared BRTI URL not configured")
    response = requests.get(base + path, timeout=timeout_s)
    response.raise_for_status()
    return response.json()


def _legacy_metadata(x):
    if (not isinstance(x, dict) or x.get("schema_version") != 2
            or x.get("orders") is not False or x.get("signal_only") is not True
            or x.get("index_id") != "BRTI" or not isinstance(x.get("owner_epoch"), str)
            or not x["owner_epoch"]):
        raise RuntimeError("shared BRTI source/safety schema mismatch")


def read_shared_brti_ticks(base_url=None, timeout_s=0.8, owner_epoch=None):
    """Read retained publications only; no upstream calls or generated samples."""
    import time, math
    x = _legacy_get("/ticks", base_url, timeout_s)
    _legacy_metadata(x)
    if owner_epoch is not None and x["owner_epoch"] != owner_epoch:
        raise RuntimeError("shared BRTI owner restarted between reads")
    raw = x.get("ticks")
    if not isinstance(raw, list):
        raise RuntimeError("shared BRTI history missing")
    points = {}
    now_ms = time.time() * 1000
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("invalid shared BRTI history")
        ts, value = item.get("source_ts_ms"), item.get("value")
        if item.get("index_id") != "BRTI" or type(ts) is not int or ts <= 0 or ts > now_ms:
            raise RuntimeError("invalid shared BRTI history source")
        value = float(value)
        if not math.isfinite(value) or not 1000 < value < 1_000_000:
            raise RuntimeError("invalid shared BRTI history value")
        if ts in points and points[ts] != value:
            raise RuntimeError("conflicting shared BRTI history")
        points[ts] = value
    return [dict(index_id="BRTI", source_ts_ms=ts, value=v) for ts,v in sorted(points.items())]
