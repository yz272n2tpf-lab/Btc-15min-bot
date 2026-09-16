#!/usr/bin/env python3
"""
Off-production dashboard shadow V10 using V14 presentation-stability UI + V6 display bridge.

DISPLAY / ACCEPTANCE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS
"""
from __future__ import annotations

import btc15_combined_dashboard_shadow_v7 as v7
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 import build_dashboard

# Reuse V7's V6 safety envelope, canonical timer, EARLY/FINAL ownership, and
# live-status protections. Replace only the off-production HTML builder.
v7.base.build_dashboard = build_dashboard


def main():
    print(
        "BTC15 COMBINED DASHBOARD SHADOW V10 | UI V14 + DISPLAY BRIDGE V6 | "
        "PRESENTATION STABILITY · PLAIN LANGUAGE · SINGLE TIMER | NO ORDERS",
        flush=True,
    )
    return v7.base.main()


if __name__ == "__main__":
    raise SystemExit(main())
