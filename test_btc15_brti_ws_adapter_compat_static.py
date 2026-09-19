#!/usr/bin/env python3
"""Static compatibility gate for WebSocket BRTI adapter. NO NETWORK. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_brti_shared_consumer_v1.py")
s=p.read_text()
ast.parse(s)
required=["source_ts_ms","success_timestamp_utc","datetime.fromtimestamp","timezone.utc","PRIMARY_OK",'"orders":False','"signal_only":True']
for x in required:
    if x not in s:
        raise SystemExit("STOP missing WS adapter compatibility invariant: "+x)
if "    from datetime import datetime" in s:
    raise SystemExit("STOP function-local datetime shadows module import")
if '"success_timestamp_utc":None' in s:
    raise SystemExit("STOP websocket adapter exposes null legacy timestamp")
print("BRTI_WS_ADAPTER_COMPAT_PASS | SOURCE_TS->ISO UTC | DATETIME SCOPE | PRIMARY_OK | NO ORDERS")
