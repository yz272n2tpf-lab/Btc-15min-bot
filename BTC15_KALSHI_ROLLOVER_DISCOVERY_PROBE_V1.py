#!/usr/bin/env python3
"""
BTC15 Kalshi rollover discovery probe V1.

READ ONLY | DIAGNOSTIC ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Measure whether the exact scheduled KXBTC15M contract is directly fetchable and
ACTIVE+QUOTED before it appears in the production-style broad market search:

  GET /trade-api/v2/markets?status=open&series_ticker=KXBTC15M&limit=1000

versus:

  GET /trade-api/v2/markets/{exact_next_ticker}

ACTIVE+QUOTED evidence is accepted only when ticker identity, open/close clock,
active window, and all four bid/ask fields are valid.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
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


def _parse_dt(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _floor_quarter(d: datetime) -> datetime:
    d = d.astimezone(timezone.utc)
    return d.replace(minute=(d.minute // 15) * 15, second=0, microsecond=0)


def boundary_context(now: datetime) -> tuple[datetime, float] | None:
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
    return all(_valid_price(v) for v in (
        market.get("yes_bid_dollars"), market.get("yes_ask_dollars"),
        market.get("no_bid_dollars"), market.get("no_ask_dollars"),
    ))


def _market_active(market: dict[str, Any], now: datetime) -> bool:
    op = _parse_dt(market.get("open_time"))
    cl = _parse_dt(market.get("close_time"))
    return bool(op and cl and op <= now.astimezone(timezone.utc) < cl)


def _clock_matches(exact: dict[str, Any], boundary: datetime) -> bool:
    op = _parse_dt(exact.get("open_time"))
    cl = _parse_dt(exact.get("close_time"))
    expected_open = boundary.astimezone(timezone.utc)
    return bool(op == expected_open and cl == expected_open + timedelta(minutes=15))


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
        "http": None, "exists": False, "returned_ticker": None, "identity_match": False,
        "status": None, "active": False, "quotes_valid": False, "clock_match": False,
        "open_time": None, "close_time": None,
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
        returned = str(market.get("ticker") or "")
        out.update({
            "exists": True,
            "returned_ticker": returned,
            "identity_match": returned == target_ticker,
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
    first_exact_active_quoted_offset: float | None = None
    first_broad_includes_offset: float | None = None
    first_broad_active_offset: float | None = None
    direct_clock_match_all: bool = True
    direct_identity_match_all: bool = True
    wrong_clock_seen: bool = False
    wrong_identity_seen: bool = False
    samples: int = 0
    summary_printed: bool = False

    def update(self, offset: float, broad: dict[str, Any], exact: dict[str, Any]) -> None:
        self.samples += 1
        boundary = _parse_dt(self.boundary_utc)
        clock_ok = bool(boundary and exact.get("exists") and _clock_matches(exact, boundary))
        identity_ok = bool(exact.get("exists") and exact.get("identity_match") is True)
        if exact.get("exists") and not clock_ok:
            self.direct_clock_match_all = False
            self.wrong_clock_seen = True
        if exact.get("exists") and not identity_ok:
            self.direct_identity_match_all = False
            self.wrong_identity_seen = True

        def first(attr: str, condition: bool):
            if condition and getattr(self, attr) is None:
                setattr(self, attr, round(offset, 3))

        first("first_exact_exists_offset", bool(exact.get("exists")))
        first("first_exact_active_offset", bool(exact.get("active") and identity_ok and clock_ok))
        first("first_exact_quoted_offset", bool(exact.get("quotes_valid") and identity_ok and clock_ok))
        first(
            "first_exact_active_quoted_offset",
            bool(exact.get("active") and exact.get("quotes_valid") and identity_ok and clock_ok),
        )
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
    exact["clock_match"] = bool(exact.get("exists") and _clock_matches(exact, boundary))
    key = _iso(boundary)
    with LOCK:
        ev = EVIDENCE.setdefault(key, BoundaryEvidence(key, ticker))
        ev.update(offset, broad, exact)
    return {"at": _iso(now), "boundary": key, "offset_sec": round(offset, 3), "ticker": ticker, "broad": broad, "exact": exact}


def _log_sample(row: dict[str, Any]) -> None:
    b, e = row["broad"], row["exact"]
    print(
        "ROLLOVER PROBE | "
        f"boundary={row['boundary']} | offset={row['offset_sec']:+.1f}s | target={row['ticker']} | "
        f"broad_http={b.get('http')} includes={b.get('includes_target')} active={b.get('active_target')} count={b.get('count')} | "
        f"exact_http={e.get('http')} exists={e.get('exists')} returned={e.get('returned_ticker')} identity={e.get('identity_match')} "
        f"status={e.get('status')} active={e.get('active')} quotes={e.get('quotes_valid')} clock={e.get('clock_match')} | "
        f"yes={e.get('yes_bid')}/{e.get('yes_ask')} no={e.get('no_bid')}/{e.get('no_ask')} | READ ONLY | NO ORDERS",
        flush=True,
    )


def _maybe_log_summaries(now: datetime) -> None:
    with LOCK:
        items = list(EVIDENCE.values())
    for ev in items:
        boundary = _parse_dt(ev.boundary_utc)
        if boundary is None or ev.summary_printed or (now - boundary).total_seconds() < POST_WINDOW_SEC:
            continue
        print(
            "ROLLOVER PROBE SUMMARY | "
            f"boundary={ev.boundary_utc} | target={ev.ticker} | samples={ev.samples} | "
            f"exact_exists={ev.first_exact_exists_offset} | exact_active={ev.first_exact_active_offset} | "
            f"exact_quoted={ev.first_exact_quoted_offset} | exact_active_quoted={ev.first_exact_active_quoted_offset} | "
            f"identity_all={ev.direct_identity_match_all} wrong_identity={ev.wrong_identity_seen} | "
            f"clock_all={ev.direct_clock_match_all} wrong_clock={ev.wrong_clock_seen} | "
            f"broad_includes={ev.first_broad_includes_offset} | broad_active={ev.first_broad_active_offset} | READ ONLY | NO ORDERS",
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
