#!/usr/bin/env python3
"""Static gate for gateway-backed Kalshi/BRTI parity shadow. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_kalshi_parity_shadow_gateway_v1.py");s=p.read_text();ast.parse(s)
if "gateway_brti_state()" not in s:raise SystemExit("STOP gateway adapter missing")
# The market API may remain read-only; CF passthrough acquisition must be absent from executable code.
tree=ast.parse(s)
for n in ast.walk(tree):
 if isinstance(n,ast.Constant) and isinstance(n.value,str) and "cfbenchmarks/values" in n.value:
  raise SystemExit("STOP direct CF BRTI path remains")
for bad in ("requests.post(","requests.put(","requests.patch(","requests.delete(","create_order","place_order"):
 if bad in s:raise SystemExit("STOP write/order capability: "+bad)
print("BRTI_PARITY_GATEWAY_SHADOW_STATIC_PASS | zero direct CF values path | market reads allowed | NO ORDERS")
