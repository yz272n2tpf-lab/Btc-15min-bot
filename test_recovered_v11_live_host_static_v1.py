#!/usr/bin/env python3
"""Static adversarial gate for recovered read-only live host."""
from pathlib import Path
import ast
src=Path("btc15_recovered_v11_live_host_v1.py").read_text()
ast.parse(src)
for required in (
 'MAIN="https://btc-15min-bot-production.up.railway.app"',
 'SCALP="https://scalp-display-bridge-v6-production.up.railway.app"',
 'path=="/dashboard_state.json"',
 'path=="/combined-state"',
 'path=="/information"',
 '"X-BTC15-Information-Nonce"',
 'r.headers.get("X-BTC15-Information-Nonce")!=nonce',
 'do_POST=reject;do_PUT=reject;do_PATCH=reject;do_DELETE=reject',
 '"orders":False',
 'candidate.build_dashboard()',
):assert required in src,required
for forbidden in ("KALSHI_PRIVATE_KEY","KALSHI_KEY_ID","place_order","order_action="):assert forbidden not in src,forbidden
print("RECOVERED V11 LIVE HOST STATIC PASS | MAIN+SCALP+INFORMATION READ ONLY | NONCE BOUND | WRITES REJECTED | NO ORDERS")
