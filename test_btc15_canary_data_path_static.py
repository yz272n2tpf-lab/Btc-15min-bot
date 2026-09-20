#!/usr/bin/env python3
"""Static canary data-path gate. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
s=p.read_text();ast.parse(s)
for x in ['def _btc15_data_path(filename):','BTC15_ISOLATED_CANARY_LOCAL_DATA','/tmp/btc15-canary-data','base.mkdir(parents=True, exist_ok=True)']:
 if x not in s: raise SystemExit("STOP missing canary data-path invariant: "+x)
q=pathlib.Path(__file__).with_name("btc15_kalshi_parity_shadow_v1.py").read_text();ast.parse(q)
for x in ['BTC15_ISOLATED_CANARY_LOCAL_DATA','/tmp/btc15-canary-data','UNIFIED = DATA_ROOT / "kalshi_subminute_unified_v1_1.csv"']:
 if x not in q: raise SystemExit("STOP parity canary data-path invariant: "+x)
if 'UNIFIED_SUBMINUTE_LOG = _btc15_data_path("kalshi_subminute_unified_v1_1.csv")' not in s:
 raise SystemExit("STOP unified collector bypasses isolated data path")
if 'BRTI_PARITY_LOG = _btc15_data_path("kalshi_direct_brti_parity_v1.csv")' not in s:
 raise SystemExit("STOP BRTI parity log bypasses isolated data path")
print("BTC15_CANARY_DATA_PATH_GATE_PASS | BOT+PARITY SHARED ISOLATED /tmp | NO ORDERS")
