#!/usr/bin/env python3
"""
Off-production dashboard shadow V9 using V13 plain-language SCALP UI + V6 display bridge.

DISPLAY / ACCEPTANCE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS
"""
from __future__ import annotations

import btc15_combined_dashboard_shadow_v7 as v7
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 import build_dashboard

# Reuse V7's V6 safety envelope, canonical timer, EARLY/FINAL ownership, and
# live-status protections. Replace only the off-production HTML builder.
v7.base.build_dashboard = build_dashboard


def main():
    print(
        "BTC15 COMBINED DASHBOARD SHADOW V9 | UI V13 + DISPLAY BRIDGE V6 | "
        "PLAIN-LANGUAGE SCALP COPY | COMPLETED CONTEXT | NO-POSITION TRACKING | "
        "SINGLE VISIBLE CONTRACT TIMER | NO ORDERS",
        flush=True,
    )
    return v7.base.main()


if __name__ == "__main__":
    raise SystemExit(main())
