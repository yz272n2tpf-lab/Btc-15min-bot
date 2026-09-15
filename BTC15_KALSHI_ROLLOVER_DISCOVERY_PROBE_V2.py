#!/usr/bin/env python3
"""
BTC15 Kalshi rollover discovery probe V2.

READ ONLY | DIAGNOSTIC ONLY | SIGNAL ONLY | NO ORDERS

V2 preserves V1 ticker identity, clock, active-window, broad-vs-exact, and timing
logic, but hardens quote usability after the first diagnostic rollover exposed
Kalshi pre/open placeholders such as YES 0/0 and NO 1/1.

A usable four-sided book must now have every bid/ask strictly inside (0, 1) and
bid <= ask on both YES and NO. The 18:45 UTC V1 rollover is diagnostic only and
is not part of the frozen V2 four-rollover gate.
"""
from __future__ import annotations

from typing import Any

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V1 as v1

VERSION = "BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2"


def _usable_price(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0.0 < x < 1.0 else None


def _usable_quotes(market: dict[str, Any]) -> bool:
    yb = _usable_price(market.get("yes_bid_dollars"))
    ya = _usable_price(market.get("yes_ask_dollars"))
    nb = _usable_price(market.get("no_bid_dollars"))
    na = _usable_price(market.get("no_ask_dollars"))
    if None in (yb, ya, nb, na):
        return False
    return bool(yb <= ya and nb <= na)


# Patch only the V1 read-only quote-validity function. All identity, clock,
# boundary, exact-fetch, broad-search, evidence, and summary logic stays frozen.
v1.VERSION = VERSION
v1._quotes_valid = _usable_quotes

boundary_context = v1.boundary_context
ticker_for_boundary = v1.ticker_for_boundary
_market_active = v1._market_active
_clock_matches = v1._clock_matches
BoundaryEvidence = v1.BoundaryEvidence
EVIDENCE = v1.EVIDENCE
LOCK = v1.LOCK
probe_once = v1.probe_once
probe_loop = v1.probe_loop
start_probe_thread = v1.start_probe_thread


if __name__ == "__main__":
    probe_loop()
