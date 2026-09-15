#!/usr/bin/env python3
"""Off-production V13 dashboard shadow using clean combined SCALP UI V8. NO ORDERS."""
import btc15_combined_dashboard_shadow_v1 as base
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V8 import build_dashboard

# Replace only the shadow dashboard builder. HTTP proxy, safety status, write
# rejection, protected-main adapter, and all trading logic remain in V1.
base.build_dashboard = build_dashboard


def main():
    print("BTC15 COMBINED DASHBOARD SHADOW V4 | CLEAN SCALP UI V8 | VISIBLE TIMER MIRROR + GUARD DIAGNOSTICS | NO ORDERS", flush=True)
    return base.main()


if __name__ == '__main__':
    raise SystemExit(main())
