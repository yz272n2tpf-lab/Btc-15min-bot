#!/usr/bin/env python3
"""Static gate for dashboard WS gated launcher. NO ORDERS."""
import ast,pathlib
s=pathlib.Path(__file__).with_name("btc15_dashboard_ws_canary_runner_v1.py").read_text();ast.parse(s)
for x in ["btc15_dashboard_ws_canary_preflight_v1.py","BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py","os.execv","NO ORDERS"]:
 if x not in s: raise SystemExit("STOP runner invariant missing: "+x)
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
 if x in s: raise SystemExit("STOP write-capable HTTP in runner")
print("BTC15_DASHBOARD_WS_RUNNER_STATIC_PASS | PREFLIGHT FIRST | V13 CHAIN | NO ORDERS")
