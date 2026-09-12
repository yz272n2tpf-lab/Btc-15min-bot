#!/usr/bin/env python3
"""Read-only regression guard for V8.1 scalp ladder candidates.

Purpose: before any graduated V8.1 logic is integrated, verify that the exact
non-negotiable behaviors we tested are still present. This script does not
place orders, connect to Kalshi, or modify runtime state.
"""
from pathlib import Path
import sys

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "scalp_lead_sub30_v8_1_locked.py")
text = TARGET.read_text(encoding="utf-8")

checks = {
    "signal_only_banner": "NO ORDERS" in text,
    "v81_start_banner": "SCALP V8.1 START" in text,
    "protected_30_45": "PROTECTED_HIGH" in text and "evidence_route(f)" in text,
    "reject_7_15": "REJECT_7_15C_CURRENT_GATE" in text,
    "sub30_time_guard": "SUB30_MIN_LEFT=240.0" in text,
    "sub30_strong_route": "SUB30_STRONG" in text,
    "sub30_confirmation": "CONFIRM_COUNT=3" in text and "CONFIRM_WINDOW=5.0" in text,
    "v81_heartbeat": "V81 HEARTBEAT" in text,
    "v81_results": "V81 RESULT" in text,
    "no_trade_placement_keywords": not any(k in text.lower() for k in (
        "place_order(", "create_order(", "submit_order(", "market_order(", "limit_order("
    )),
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} | {name}")

if failed:
    print("REGRESSION_GUARD=FAIL | " + ",".join(failed))
    raise SystemExit(1)

print("REGRESSION_GUARD=PASS | V8.1 tested invariants preserved")
