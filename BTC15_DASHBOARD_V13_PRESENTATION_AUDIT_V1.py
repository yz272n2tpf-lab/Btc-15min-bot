#!/usr/bin/env python3
"""Static audit for V13 presentation-only dashboard changes. No imports from runtime stack."""
from pathlib import Path

TARGET = Path("BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py")


def main() -> int:
    text = TARGET.read_text(encoding="utf-8", errors="replace")
    required = [
        "import BTC15_DASHBOARD_COMBINED_SCALP_UI_V12 as v12",
        "SHADOW PRESENTATION ONLY",
        "SIGNAL ONLY",
        "NO ORDERS",
        "scalp_entry_price_filter_applied===false",
        "scalp_entry_guidance_is_display_only===true",
        "scalp_completed_display_actionable===false",
        "scalp_ended_unarmed_is_actionable_exit===false",
        "TRACKING ONLY · DON'T CHASE",
        "WAIT · DATA NOT FRESH",
        "WAIT · SYNCING CONTRACT",
    ]
    forbidden = [
        "import requests",
        "from requests",
        "import socket",
        "import subprocess",
        "place_order",
        "create_order",
        "submit_order",
        "SCALP_MIN_BTC30 =",
        "SCALP_MIN_SECONDS_LEFT =",
        "SCALP_ARM_GAIN =",
        "SCALP_GIVEBACK =",
        "FINAL_THRESHOLD =",
        "EARLY_THRESHOLD =",
        "BTC15_COMBINED_V6_URL",
        "BTC15_SCALP_V5_URL",
    ]
    failures = []
    for s in required:
        if s not in text:
            failures.append("missing required invariant: " + s)
    for s in forbidden:
        if s in text:
            failures.append("forbidden runtime/strategy token present: " + s)

    # V13 must wrap V12 rather than alter any lower layer.
    if "html = v12.build_dashboard()" not in text:
        failures.append("V13 does not wrap V12 build_dashboard")
    if "patch_v13(html)" not in text:
        failures.append("V13 presentation patch not applied after V12 render")

    print("BTC15 V13 PRESENTATION AUDIT V1")
    print("target=", TARGET)
    print("presentation_only=True")
    print("network_code_added=False")
    print("strategy_thresholds_added=False")
    print("order_code_added=False")
    if failures:
        for f in failures:
            print("FAIL |", f)
        return 1
    print("RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
