#!/usr/bin/env python3
"""
Run combined forward scorecard V2 with future-only Kalshi rollover Probe V3.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Probe V2's four-rollover decision is closed/rejected. This wrapper starts Probe
V3's physically separate >=20:00 UTC operational replication while preserving
the existing combined V2 process. No production behavior is changed.
"""
from __future__ import annotations

import BTC15_COMBINED_FORWARD_SCORECARD_V2 as scorecard
import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V3 as probe


def main() -> int:
    probe.start_probe_thread()
    print(
        "BTC15 COMBINED V2 + ROLLOVER PROBE V3 | cutoff=2026-09-15T20:00:00Z | "
        "FUTURE-ONLY 8-ROLLOVER OPERATIONAL REPLICATION | READ ONLY | NO ORDERS",
        flush=True,
    )
    return scorecard.main()


if __name__ == "__main__":
    raise SystemExit(main())
