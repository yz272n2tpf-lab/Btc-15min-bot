#!/usr/bin/env python3
"""Static safety gate for shared-BRTI main cutover candidate. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
s=p.read_text();ast.parse(s)
must=['BTC15_USE_SHARED_BRTI','btc15_brti_shared_consumer_v1','DIRECT_BRTI_AUTH_MAX_AGE_SECONDS = 5.0',
'DIRECT_BRTI_AUTH_WAIT_DOLLARS = 11.0','series_ticker": "KXBTC15M"','NO ORDERS']
for x in must:
 if x not in s:raise SystemExit("STOP missing protected marker: "+x)
# Direct CF endpoint may remain as OFF-mode rollback control, but every production
# shared-mode fetch site must have an explicit shared-mode branch.
for fn in ['def _direct_brti_authority_fetch():','def _fetch_direct_brti_once():']:
 i=s.index(fn);j=s.find('\ndef ',i+5);block=s[i:j if j>0 else len(s)]
 if 'BTC15_USE_SHARED_BRTI' not in block or 'read_shared_brti' not in block:
  raise SystemExit("STOP shared branch absent in "+fn)
if 'RAILWAY AUTH BRTI HTTP: SKIPPED | shared BRTI transport owns upstream' not in s:
 raise SystemExit("STOP startup BRTI suppression absent")
for x in ['requests.post(','requests.put(','requests.patch(','requests.delete(']:
 if x in s:raise SystemExit("STOP write-capable HTTP present: "+x)
print("BRTI_MAIN_CUTOVER_STATIC_GATE_PASS | 5S AGE | $11 WAIT | NO ORDERS")
