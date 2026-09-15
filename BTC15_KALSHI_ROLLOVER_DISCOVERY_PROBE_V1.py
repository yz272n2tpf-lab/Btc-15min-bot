#!/usr/bin/env python3
"""
BTC15 Kalshi rollover discovery probe V1.

READ ONLY | DIAGNOSTIC ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Measure whether the next scheduled KXBTC15M contract is directly fetchable and
quoted before it appears in the production-style broad market search:

  GET /trade-api/v2/markets?status=open&series_ticker=KXBTC15M&limit=1000

versus:

  GET /trade-api/v2/markets/{exact_next_ticker}

The probe runs only near 15-minute boundaries and never changes qualification,
contract ownership, signal thresholds, dashboard state, or production behavior.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

VERSION = "BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V1"
BASE = "https://api.elections.kalshi.com"
NY = ZoneInfo("America/New_York")
POLL_SEC = 2.0
PRE_WINDOW_SEC = 20.0
POST_WINDOW_SEC = 50.0
TIMEOUT_SEC = 3.0

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _floor_quarter(d: datetime) -> datetime:
    d = d.astimezone(timezone.utc)
    return d.replace(minute=(d.minute // 15) * 15, second=0, microsecond=0)


def boundary_context(now: datetime) -> tuple[datetime, float] | None:
    """Return relevant rollover boundary and signed seconds from it."""
    now = now.astimezone(timezone.utc)
    floor = _floor_quarter(now)
    after = (now - floor).total_seconds()
    if 0.0 <= after <= POST_WINDOW_SEC:
        return floor, after
    nxt = floor + timedelta(minutes=15)
    before = (now - nxt).total_seconds()
    if -PRE_WINDOW_SEC <= before < 0.0:
        return nxt, before
    return None


def ticker_for_boundary(boundary_utc: datetime) -> str:
    """Target contract starts at boundary and closes 15m later."""
    close_local = (boundary_utc + timedelta(minutes=15)).astimezone(NY)
    mon = MONTHS[close_local.month - 1]
    minute = close_local.minute
    return (
        f"KXBTC15M-{close_local.year % 100:02d}{mon}{close_local.day:02d}"
        f"{close_local.hour:02d}{minute:02d}-{minute:02d}"
    )


def _valid_price(v: Any) -> bool:
    try:
        x = float(v)
        return 0.0 <= x <= 1.0
    except (TypeError, ValueError):
        return False


def _quotes_valid(market: dict[str, Any]) -> bool:
    vals = [
        market.get("yes_bid_dollars"), market.get("yes_ask_dollars"),
        market.get("no_bid_dollars"), market.get("no_ask_dollars"),
    ]
    return all(_valid_price(v) for v in vals)


def _market_active(market: dict[str, Any], now: datetime) -> bool:
    try:
        op = datetime.fromisoformat(str(market.get("open_time")).replace("Z", "+00:00"))
        cl = datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
        if op.tzinfo is None:
            op = op.replace(tzinfo=timezone.utc)
        if cl.tzinfo is None:
            cl = cl.replace(tzinfo=timezone.utc)
        return op.astimezone(timezone.utc) <= now.astimezone(timezone.utc) < cl.astimezone(timezone.utc)
    except Exception:
        return False


def broad_open_search(target_ticker: str, now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"http": None, "includes_target": False, "active_target": False, "count": None, "error": None}
    try:
        r = requests.get(
            BASE + "/trade-api/v2/markets",
            params={"status": "open", "series_ticker": "KXBTC15M", "limit": 1000},
            headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
            timeout=TIMEOUT_SEC,
        )
        out["http"] = r.status_code
        r.raise_for_status()
        markets = r.json().get("markets", [])
        out["count"] = len(markets)
        for m in markets:
            if str(m.get("ticker") or "") == target_ticker:
                out["includes_target"] = True
                out["active_target"] = _market_active(m, now)
                break
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}:{exc}"
    return out


def exact_market_fetch(target_ticker: str, now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {
        "http": None, "exists": False, "status": None, "active": False,
        "quotes_valid": False, "open_time": None, "close_time": None,
        "yes_bid": None, "yes_ask": None, "no_bid": None, "no_ask": None,
        "error": None,
    }
    try:
        r = requests.get(
            BASE + "/trade-api/v2/markets/" + target_ticker,
            headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
            timeout=TIMEOUT_SEC,
        )
        out["http"] = r.status_code
        if r.status_code != 200:
            return out
        d = r.json()
        market = d.get("market") if isinstance(d.get("market"), dict) else d
        if not isinstance(market, dict):
            return out
        out.update({
            "exists": True,
            "status": market.get("status"),
            "active": _market_active(market, now),
            "quotes_valid": _quotes_valid(market),
            "open_time": market.get("open_time"),
            "close_time": market.get("close_time"),
            "yes_bid": market.get("yes_bid_dollars"),
            "yes_ask": market.get("yes_ask_dollars"),
            "no_bid": market.get("no_bid_dollars"),
            "no_ask": market.get("no_ask_dollars"),
        })
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}:{exc}"
    return out


@dataclass
class BoundaryEvidence:
    boundary_utc: str
    ticker: str
    first_exact_exists_offset: float | None = None
    first_exact_active_offset: float | None = None
    first_exact_quoted_offset: float | None = None
    first_broad_includes_offset: float | None = None
    first_broad_active_offset: float | None = None
    samples: int = 0
    summary_printed: bool = False

    def update(self, offset: float, broad: dict[str, Any], exact: dict[str, Any]) -> None:
        self.samples += 1
        def first(attr: str, condition: bool):
            if condition and getattr(self, attr) is None:
                setattr(self, attr, round(offset, 3))
        first("first_exact_exists_offset", bool(exact.get("exists")))
        first("first_exact_active_offset", bool(exact.get("active")))
        first("first_exact_quoted_offset", bool(exact.get("quotes_valid")))
        first("first_broad_includes_offset", bool(broad.get("includes_target")))
        first("first_broad_active_offset", bool(broad.get("active_target")))


EVIDENCE: dict[str, BoundaryEvidence] = {}
LOCK = threading.RLock()


def probe_once(now: datetime | None = None) -> dict[str, Any] | None:
    now = now or _now()
    ctx = boundary_context(now)
    if ctx is None:
        return None
    boundary, offset = ctx
    ticker = ticker_for_boundary(boundary)
    broad = broad_open_search(ticker, now)
    exact = exact_market_fetch(ticker, now)
    key = _iso(boundary)
    with LOCK:
        ev = EVIDENCE.setdefault(key, BoundaryEvidence(key, ticker))
        ev.update(offset, broad, exact)
    return {
        "at": _iso(now), "boundary": key, "offset_sec": round(offset, 3),
        "ticker": ticker, "broad": broad, "exact": exact,
    }


def _log_sample(row: dict[str, Any]) -> None:
    b, e = row["broad"], row["exact"]
    print(
        "ROLLOVER PROBE | "
        f"boundary={row['boundary']} | offset={row['offset_sec']:+.1f}s | target={row['ticker']} | "
        f"broad_http={b.get('http')} includes={b.get('includes_target')} active={b.get('active_target')} count={b.get('count')} | "
        f"exact_http={e.get('http')} exists={e.get('exists')} status={e.get('status')} active={e.get('active')} quotes={e.get('quotes_valid')} | "
        f"yes={e.get('yes_bid')}/{e.get('yes_ask')} no={e.get('no_bid')}/{e.get('no_ask')} | "
        "READ ONLY | NO ORDERS",
        flush=True,
    )


def _maybe_log_summaries(now: datetime) -> None:
    with LOCK:
        items = list(EVIDENCE.values())
    for ev in items:
        boundary = datetime.fromisoformat(ev.boundary_utc.replace("Z", "+00:00"))
        if ev.summary_printed or (now - boundary).total_seconds() < POST_WINDOW_SEC:
            continue
        print(
            "ROLLOVER PROBE SUMMARY | "
            f"boundary={ev.boundary_utc} | target={ev.ticker} | samples={ev.samples} | "
            f"exact_exists={ev.first_exact_exists_offset} | exact_active={ev.first_exact_active_offset} | "
            f"exact_quoted={ev.first_exact_quoted_offset} | broad_includes={ev.first_broad_includes_offset} | "
            f"broad_active={ev.first_broad_active_offset} | READ ONLY | NO ORDERS",
            flush=True,
        )
        with LOCK:
            ev.summary_printed = True


def probe_loop() -> None:
    print(
        f"{VERSION} START | compare broad status=open listing vs exact next ticker | "
        f"window=-{PRE_WINDOW_SEC:.0f}s..+{POST_WINDOW_SEC:.0f}s | poll={POLL_SEC:.0f}s | READ ONLY | NO ORDERS",
        flush=True,
    )
    while True:
        now = _now()
        try:
            row = probe_once(now)
            if row:
                _log_sample(row)
            _maybe_log_summaries(now)
        except Exception as exc:
            print(f"ROLLOVER PROBE WARNING | {type(exc).__name__}:{exc} | READ ONLY | NO ORDERS", flush=True)
        time.sleep(POLL_SEC)


def start_probe_thread() -> threading.Thread:
    t = threading.Thread(target=probe_loop, name="btc15-kalshi-rollover-probe", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    probe_loop()
