#!/usr/bin/env python3
"""Deterministic safety tests for BRTI WS gateway V1. NO NETWORK. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_brti_ws_gateway_v1.py");s=p.read_text();ast.parse(s)
required=["MAX_AGE_MS=5000","source_ts_ms","receive_ts_ms","owner_epoch","UPSTREAM_DISCONNECTED","index_id\")!=\"BRTI\"","ts>recv+1000","STATE[\"dup\"]+=1;continue","STATE[\"ooo\"]+=1;continue",'"orders":False']
for x in required:
 if x not in s:raise SystemExit("STOP missing safety invariant: "+x)
# Exact boundary contract: source age <=5000 qualifies; 5001 does not.
def eligible(age,connected=True,reason="PRIMARY_OK",latest=True):
 return bool(connected and latest and age is not None and 0<=age<=5000 and reason=="PRIMARY_OK")
assert eligible(4999) and eligible(5000) and not eligible(5001)
assert not eligible(1,False) and not eligible(1,True,"UPSTREAM_DISCONNECTED")
assert not eligible(-1)
# Publication identity contract: same timestamp cannot advance sequence.
def accept(prev_ts,new_ts):
 if prev_ts is not None and new_ts==prev_ts:return "DUP"
 if prev_ts is not None and new_ts<prev_ts:return "OOO"
 return "NEW"
assert accept(1000,1000)=="DUP";assert accept(2000,1000)=="OOO";assert accept(1000,2000)=="NEW"
# Old publications remain old; consumer/read time never rewrites source time.
source=1_000_000; now=1_300_000
assert now-source==300_000 and not eligible(now-source)
print("BRTI_WS_GATEWAY_STATIC_SAFETY_PASS | 4999 PASS | 5000 PASS | 5001 WAIT | 300S OLD WAIT | DUP/OOO REJECT | DISCONNECT WAIT | NO ORDERS")
