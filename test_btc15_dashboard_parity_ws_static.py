#!/usr/bin/env python3
"""Static gate: dashboard parity BRTI must use qualified adapter in shared mode. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_kalshi_parity_shadow_v1.py")
s=p.read_text();ast.parse(s)
i=s.index("def direct_brti_payload():");j=s.find("\ndef ",i+5);b=s[i:j if j>0 else len(s)]
for x in ["BTC15_USE_SHARED_BRTI","btc15_brti_shared_consumer_v1","BTC15_BRTI_TRANSPORT","websocket_gateway","btc15_brti_ws_gateway_client_v1","source_ts_ms","PRIMARY_OK","5.0"]:
 if x not in b: raise SystemExit("STOP parity WS invariant missing: "+x)
if b.index("BTC15_USE_SHARED_BRTI") > b.index("kalshi_get(BRTI_PATH"):
 raise SystemExit("STOP direct BRTI HTTP precedes shared-mode branch")
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
 if x in s: raise SystemExit("STOP write-capable HTTP in parity")
print("BTC15_DASHBOARD_PARITY_WS_GATE_PASS | TICKS | PRIMARY_OK | <=5S | HTTP ROLLBACK OFF-MODE ONLY | NO ORDERS")
