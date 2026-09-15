#!/usr/bin/env python3
"""
Off-production V13 dashboard shadow V8 using V12 scalp clarity UI + V6 display bridge.

DISPLAY / ACCEPTANCE ONLY | SIGNAL ONLY | NO ORDERS
"""
from __future__ import annotations

import btc15_combined_dashboard_shadow_v7 as v7
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V12 import build_dashboard

# Reuse V7's V6 safety envelope and live-status protections. Replace only the
# off-production HTML builder with V12 wording/presentation.
v7.base.build_dashboard = build_dashboard


def main():
    print(
        "BTC15 COMBINED DASHBOARD SHADOW V8 | UI V12 + DISPLAY BRIDGE V6 | "
        "EXPENSIVE ENTRY = TRACKING / NO MANUAL POSITION | "
        "COMPLETED SCALP PERSISTENCE | SINGLE VISIBLE CONTRACT TIMER | NO ORDERS",
        flush=True,
    )
    return v7.base.main()


if __name__ == "__main__":
    raise SystemExit(main())
