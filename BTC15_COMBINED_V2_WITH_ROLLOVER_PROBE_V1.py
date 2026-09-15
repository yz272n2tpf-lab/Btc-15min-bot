#!/usr/bin/env python3
"""
Run combined forward scorecard V2 with strict Kalshi rollover probe V2.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

The probe is a daemon diagnostic thread. If it fails, V2 scoring remains the
primary process and production/V5/V6/V12 are unaffected.
"""
from __future__ import annotations

import BTC15_COMBINED_FORWARD_SCORECARD_V2 as scorecard
import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2 as probe


def main() -> int:
    probe.start_probe_thread()
    print(
        "BTC15 COMBINED V2 + ROLLOVER PROBE V2 | READ ONLY | "
        "STRICT USABLE QUOTES | BROAD status=open VS EXACT NEXT TICKER | NO ORDERS",
        flush=True,
    )
    return scorecard.main()


if __name__ == "__main__":
    raise SystemExit(main())
