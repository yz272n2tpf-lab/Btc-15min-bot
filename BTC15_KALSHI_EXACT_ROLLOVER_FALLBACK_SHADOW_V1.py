#!/usr/bin/env python3
"""
BTC15 exact-ticker rollover fallback shadow V1.

READ ONLY | SHADOW ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Purpose
-------
Evaluate whether the exact scheduled KXBTC15M contract can safely serve as a
rollover handoff source before the existing production broad status=open market
discovery updates. This module NEVER switches production state and NEVER
qualifies EARLY, SCALP, or FINAL signals.

A shadow fallback can be considered available only when:
- the exact ticker matches the deterministic 15-minute ticker for the boundary;
- exact open/close clock matches the boundary and boundary+15m;
- the exact market is ACTIVE at the observation time;
- YES and NO bid/ask are all strictly inside (0,1) with bid <= ask;
- production is still advertising a different/previous contract.

A positive shadow decision is evidence only. Promotion requires a separate
fresh shadow validation and explicit manual review.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2 as probe

VERSION = "BTC15_KALSHI_EXACT_ROLLOVER_FALLBACK_SHADOW_V1"


def _side_price(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0.0 < x < 1.0 else None


def _book_usable(exact: Mapping[str, Any]) -> bool:
    yb = _side_price(exact.get("yes_bid"))
    ya = _side_price(exact.get("yes_ask"))
    nb = _side_price(exact.get("no_bid"))
    na = _side_price(exact.get("no_ask"))
    return bool(None not in (yb, ya, nb, na) and yb <= ya and nb <= na)


@dataclass(frozen=True)
class ShadowDecision:
    version: str
    observed_at_utc: str
    boundary_utc: str
    expected_ticker: str
    production_contract: str | None
    exact_returned_ticker: str | None
    identity_ok: bool
    clock_ok: bool
    active_ok: bool
    usable_book_ok: bool
    production_already_on_expected: bool
    shadow_fallback_available: bool
    reason: str
    exact_yes_bid: float | None
    exact_yes_ask: float | None
    exact_no_bid: float | None
    exact_no_ask: float | None
    production_behavior_changed: bool = False
    manual_execution_only: bool = True
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_shadow(
    *,
    now: datetime,
    boundary: datetime,
    production_contract: str | None,
    exact: Mapping[str, Any],
) -> ShadowDecision:
    now = now.astimezone(timezone.utc)
    boundary = boundary.astimezone(timezone.utc)
    expected = probe.ticker_for_boundary(boundary)
    returned = str(exact.get("returned_ticker") or "").strip() or None

    identity_ok = bool(exact.get("exists") is True and returned == expected and exact.get("identity_match") is True)
    clock_ok = bool(exact.get("clock_match") is True)
    active_ok = bool(exact.get("active") is True)
    usable_book_ok = _book_usable(exact)
    prod = str(production_contract or "").strip() or None
    production_already = bool(prod == expected)

    available = bool(
        identity_ok
        and clock_ok
        and active_ok
        and usable_book_ok
        and not production_already
    )

    if production_already:
        reason = "PRODUCTION_ALREADY_ON_EXPECTED_CONTRACT"
    elif not identity_ok:
        reason = "WAIT_EXACT_IDENTITY"
    elif not clock_ok:
        reason = "WAIT_EXACT_CLOCK"
    elif not active_ok:
        reason = "WAIT_EXACT_ACTIVE"
    elif not usable_book_ok:
        reason = "WAIT_USABLE_BOOK"
    else:
        reason = "SHADOW_FALLBACK_AVAILABLE"

    return ShadowDecision(
        version=VERSION,
        observed_at_utc=now.isoformat().replace("+00:00", "Z"),
        boundary_utc=boundary.isoformat().replace("+00:00", "Z"),
        expected_ticker=expected,
        production_contract=prod,
        exact_returned_ticker=returned,
        identity_ok=identity_ok,
        clock_ok=clock_ok,
        active_ok=active_ok,
        usable_book_ok=usable_book_ok,
        production_already_on_expected=production_already,
        shadow_fallback_available=available,
        reason=reason,
        exact_yes_bid=_side_price(exact.get("yes_bid")),
        exact_yes_ask=_side_price(exact.get("yes_ask")),
        exact_no_bid=_side_price(exact.get("no_bid")),
        exact_no_ask=_side_price(exact.get("no_ask")),
    )


def evaluate_live_once(now: datetime | None = None, production_contract: str | None = None) -> dict[str, Any] | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ctx = probe.boundary_context(now)
    if ctx is None:
        return None
    boundary, _ = ctx
    ticker = probe.ticker_for_boundary(boundary)
    exact = probe.v1.exact_market_fetch(ticker, now)
    exact["clock_match"] = bool(exact.get("exists") and probe.v1._clock_matches(exact, boundary))
    return evaluate_shadow(
        now=now,
        boundary=boundary,
        production_contract=production_contract,
        exact=exact,
    ).to_dict()


if __name__ == "__main__":
    print(f"{VERSION} | pure/read-only shadow evaluator | NO PRODUCTION SWITCH | NO ORDERS")
