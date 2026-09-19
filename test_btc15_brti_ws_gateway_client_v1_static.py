#!/usr/bin/env python3
"""Deterministic fail-closed tests for the BRTI gateway client. NO NETWORK. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_brti_ws_gateway_client_v1.py")
s=p.read_text();ast.parse(s)
required=[
 'r=requests.get(b+"/state",timeout=timeout);r.raise_for_status();x=r.json()',
 'r=requests.get(b+"/ticks",timeout=timeout);r.raise_for_status();x=r.json()',
 'x.get("orders") is not False',
 'x.get("signal_only") is not True',
 'not x.get("ready")',
 'x.get("reason")!="PRIMARY_OK"',
 'not x.get("connected")',
 'o.get("index_id")!="BRTI"',
 'age<0 or age>5000',
]
for marker in required:
 if marker not in s: raise SystemExit("STOP missing client fail-closed invariant: "+marker)
if any(x in s for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]):
 raise SystemExit("STOP write-capable HTTP present")
print("BRTI_GATEWAY_CLIENT_FAIL_CLOSED_PASS | HTTP STATUS | SAFETY META | READY | PRIMARY_OK | CONNECTED | BRTI | <=5S | NO ORDERS")
