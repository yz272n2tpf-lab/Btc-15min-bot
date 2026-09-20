#!/usr/bin/env python3
"""Gated launcher for isolated V13 dashboard + qualified WebSocket BRTI. NO ORDERS."""
import os,subprocess,sys
rc=subprocess.run([sys.executable,"btc15_dashboard_ws_canary_preflight_v1.py"]).returncode
if rc: raise SystemExit("STOP dashboard WS preflight failed")
# Preserve frozen V13/V8.1 presentation chain; transport is selected by env.
print("BTC15_DASHBOARD_WS_CANARY_LAUNCH | V13 UI unchanged | isolated data | NO ORDERS",flush=True)
os.execv(sys.executable,[sys.executable,"-u","BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py"])
