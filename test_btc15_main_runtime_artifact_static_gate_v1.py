#!/usr/bin/env python3
"""Static gate: artifact optimization may replace fitting only, never live semantics."""
from pathlib import Path
p=Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
s=p.read_text()
required=[
'get_kalshi_btc_markets','DIRECT_BRTI_AUTH_MAX_AGE_SECONDS = 5.0',
'DIRECT_BRTI_AUTH_WAIT_DOLLARS = 11.0','EARLY OPPORTUNITY — TARGET-AWARE / NOT FINAL OUTCOME',
'FINAL OUTCOME — END OF 15-MIN CONTRACT','_fair_features = [',
'RandomForestClassifier(','NO ORDERS'
]
for x in required:
 if x not in s:raise SystemExit("STOP protected semantic marker missing: "+x)
for x in ['requests.post(','requests.put(','requests.patch(','requests.delete(']:
 if x in s:raise SystemExit("STOP write-capable HTTP method present: "+x)
if '_BTC15_ARTIFACT_MODE' not in s or 'CERTIFIED ARTIFACT LOADED | SHA VERIFIED | NO ORDERS' not in s:
 raise SystemExit("STOP artifact gate missing")
print("MAIN_RUNTIME_ARTIFACT_STATIC_GATE_PASS | NO ORDERS")
