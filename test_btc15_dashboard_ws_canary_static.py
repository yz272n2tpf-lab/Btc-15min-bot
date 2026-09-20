#!/usr/bin/env python3
"""Static gate for isolated dashboard + qualified WebSocket BRTI canary. NO ORDERS."""
import ast,pathlib
root=pathlib.Path(__file__).parent
checks={
 "BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py":[
  "BTC15_INSTALL_LIVE_DASHBOARD_V13","BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
 ],
 "btc15_brti_shared_consumer_v1.py":[
  "BTC15_BRTI_TRANSPORT","websocket_gateway","PRIMARY_OK","source_ts_ms","signal_only"
 ],
 "btc15_brti_ws_gateway_client_v1.py":[
  'x.get("orders") is not False','x.get("signal_only") is not True',
  'x.get("reason")!="PRIMARY_OK"','age<0 or age>5000'
 ],
}
for name,markers in checks.items():
 p=root/name
 if not p.exists(): raise SystemExit("STOP missing dashboard-canary dependency: "+name)
 s=p.read_text();ast.parse(s)
 for marker in markers:
  if marker not in s: raise SystemExit("STOP missing protected marker in "+name+": "+marker)
for name in checks:
 s=(root/name).read_text()
 for write in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
  if write in s: raise SystemExit("STOP write-capable HTTP in "+name+": "+write)
print("BTC15_DASHBOARD_WS_CANARY_STATIC_GATE_PASS | V13 WRAPPER | PRIMARY_OK | <=5S | SIGNAL ONLY | NO ORDERS")
