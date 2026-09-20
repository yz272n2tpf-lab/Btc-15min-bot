#!/usr/bin/env python3
"""Read-only preflight for V13 dashboard WebSocket-BRTI canary. NO ORDERS."""
import os,subprocess,sys
required={
 "BTC15_USE_SHARED_BRTI":"1",
 "BTC15_BRTI_TRANSPORT":"websocket_gateway",
 "BTC15_ISOLATED_CANARY_LOCAL_DATA":"1",
}
for k,v in required.items():
 if os.getenv(k,"").strip()!=v: raise SystemExit(f"STOP {k} must equal {v}")
if not os.getenv("BTC15_BRTI_GATEWAY_URL","").strip():
 raise SystemExit("STOP BTC15_BRTI_GATEWAY_URL missing")
gates=[
 "test_btc15_dashboard_ws_canary_static.py",
 "test_btc15_dashboard_ws_runner_static.py",
 "test_brti_main_cutover_static_gate_v1.py",
 "test_btc15_brti_ws_gateway_client_v1_static.py",
 "test_btc15_brti_ws_adapter_compat_static.py",
 "test_btc15_canary_data_path_static.py",
]
for g in gates:
 rc=subprocess.run([sys.executable,g]).returncode
 if rc: raise SystemExit("STOP gate failed: "+g)
from btc15_brti_shared_consumer_v1 import read_shared_brti
s=read_shared_brti()
if s.get("status")!="PRIMARY_OK" or float(s.get("age_seconds",99))>5:
 raise SystemExit("STOP gateway preflight not fresh PRIMARY_OK")
if s.get("orders") is not False or s.get("signal_only") is not True:
 raise SystemExit("STOP gateway preflight safety metadata")
print(f"BTC15_DASHBOARD_WS_PREFLIGHT_PASS | age={s['age_seconds']:.3f}s | seq={s['sequence']} | NO ORDERS")
