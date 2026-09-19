#!/usr/bin/env python3
"""Static canary data-path gate. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
s=p.read_text();ast.parse(s)
for x in ['def _btc15_data_path(filename):','BTC15_ISOLATED_CANARY_LOCAL_DATA','/tmp/btc15-canary-data','base.mkdir(parents=True, exist_ok=True)']:
 if x not in s: raise SystemExit("STOP missing canary data-path invariant: "+x)
print("BTC15_CANARY_DATA_PATH_GATE_PASS | ISOLATED /tmp | NO ORDERS")
