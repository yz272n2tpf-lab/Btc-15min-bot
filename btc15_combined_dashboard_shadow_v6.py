#!/usr/bin/env python3
"""Off-production V13 dashboard shadow using serial SCALP UI V10. NO ORDERS."""
import btc15_combined_dashboard_shadow_v1 as base
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V10 import build_dashboard

# Replace only the off-production shadow dashboard builder. Protected main
# EARLY/FINAL/Kalshi/timer state, HTTP write rejection, and safety checks remain
# in the base shadow server.
base.build_dashboard = build_dashboard


def main():
    print(
        "BTC15 COMBINED DASHBOARD SHADOW V6 | SERIAL SCALP UI V10 | "
        "ENDED_UNARMED CONTEXT NON-ACTIONABLE | SINGLE VISIBLE CONTRACT TIMER | NO ORDERS",
        flush=True,
    )
    return base.main()


if __name__ == '__main__':
    raise SystemExit(main())
