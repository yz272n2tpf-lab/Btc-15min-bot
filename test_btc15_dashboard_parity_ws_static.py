#!/usr/bin/env python3
"""Static gate: dashboard parity BRTI must use qualified adapter in shared mode. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_kalshi_parity_shadow_v1.py")
s=p.read_text();ast.parse(s)
i=s.index("def direct_brti_payload():");j=s.find("\ndef ",i+5);b=s[i:j if j>0 else len(s)]
for x in ["BTC15_USE_SHARED_BRTI","btc15_brti_shared_consumer_v1","BTC15_BRTI_TRANSPORT","websocket_gateway","btc15_brti_ws_gateway_client_v1","source_ts_ms","PRIMARY_OK","5.0"]:
 if x not in b: raise SystemExit("STOP parity WS invariant missing: "+x)
if b.index("BTC15_USE_SHARED_BRTI") > b.index("kalshi_get(BRTI_PATH"):
 raise SystemExit("STOP direct BRTI HTTP precedes shared-mode branch")
if b.index("point = read_shared_brti()") > b.index("raw = ticks(timeout=0.8)"):
 raise SystemExit("STOP tick history bypasses current gateway qualification")
for x in ['t == publication_ts', 'parse_dt(r.get("timestamp_utc")) == source_ts',
          'str(r.get("contract", "")).strip() == contract',
          'bot.get("brti_timestamp_utc")', 'bot.get("direct_brti_ready", "")',
          '0.0 <= bot_age <= 5.0', '0.0 <= age <= SOURCE_MAX_AGE_SEC',
          'quote_scorable = False', 'QUOTES_ASYNC_UNVERIFIED']:
 if x not in s: raise SystemExit("STOP parity measurement invariant missing: "+x)
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
 if x in s: raise SystemExit("STOP write-capable HTTP in parity")
print("BTC15_DASHBOARD_PARITY_WS_GATE_PASS | EXACT PUBLICATION/CONTRACT/FRAME | PRIMARY_OK | <=5S | QUOTES UNVERIFIED | HTTP ROLLBACK OFF-MODE ONLY | NO ORDERS")
