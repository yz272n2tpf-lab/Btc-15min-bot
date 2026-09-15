#!/usr/bin/env python3
"""
BTC15 Kalshi rollover discovery Probe V3 — future-only operational replication.

READ ONLY | DIAGNOSTIC ONLY | SIGNAL ONLY | NO ORDERS

V3 starts a physically separate evidence store for boundaries at/after the frozen
2026-09-15T20:00:00Z cutoff. It reuses Probe V2's strict usable-book rule and
Probe V1's exact ticker/clock logic, but none of Probe V2's four decision rows
are imported into this replication.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2 as v2
import BTC15_KALSHI_ROLLOVER_OPERATIONAL_GATE_V3 as gate

VERSION = "BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V3"
CUTOFF = datetime(2026, 9, 15, 20, 0, 0, tzinfo=timezone.utc)
POLL_SEC = v2.v1.POLL_SEC
POST_WINDOW_SEC = v2.v1.POST_WINDOW_SEC

EVIDENCE: dict[str, v2.BoundaryEvidence] = {}
LOCK = threading.RLock()


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(v: Any) -> datetime | None:
    return v2.v1._parse_dt(v)


def probe_once(now: datetime | None = None) -> dict[str, Any] | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ctx = v2.boundary_context(now)
    if ctx is None:
        return None
    boundary, offset = ctx
    if boundary < CUTOFF:
        return None

    ticker = v2.ticker_for_boundary(boundary)
    broad = v2.v1.broad_open_search(ticker, now)
    exact = v2.v1.exact_market_fetch(ticker, now)
    exact["clock_match"] = bool(exact.get("exists") and v2.v1._clock_matches(exact, boundary))

    key = _iso(boundary)
    with LOCK:
        ev = EVIDENCE.setdefault(key, v2.BoundaryEvidence(key, ticker))
        ev.update(offset, broad, exact)

    return {
        "at": _iso(now),
        "boundary": key,
        "offset_sec": round(offset, 3),
        "ticker": ticker,
        "broad": broad,
        "exact": exact,
    }


def _log_sample(row: dict[str, Any]) -> None:
    b, e = row["broad"], row["exact"]
    print(
        "ROLLOVER PROBE V3 | "
        f"boundary={row['boundary']} | offset={row['offset_sec']:+.1f}s | target={row['ticker']} | "
        f"broad_http={b.get('http')} includes={b.get('includes_target')} active={b.get('active_target')} | "
        f"exact_http={e.get('http')} exists={e.get('exists')} identity={e.get('identity_match')} "
        f"active={e.get('active')} quotes={e.get('quotes_valid')} clock={e.get('clock_match')} | "
        f"yes={e.get('yes_bid')}/{e.get('yes_ask')} no={e.get('no_bid')}/{e.get('no_ask')} | "
        "FRESH OPERATIONAL REPLICATION | NO ORDERS",
        flush=True,
    )


def _gate_rows() -> list[dict[str, Any]]:
    with LOCK:
        items = [x for x in EVIDENCE.values() if x.summary_printed]
    items.sort(key=lambda x: x.boundary_utc)
    return [
        {
            "boundary_utc": ev.boundary_utc,
            "ticker": ev.ticker,
            "exact_active_quoted": ev.first_exact_active_quoted_offset,
            "broad_active": ev.first_broad_active_offset,
            "identity_all": ev.direct_identity_match_all,
            "clock_all": ev.direct_clock_match_all,
        }
        for ev in items
    ]


def _log_gate() -> None:
    s = gate.score(_gate_rows())
    fast = s.get("exact_active_quoted_by_15s_share")
    lead = s.get("median_lead_sec")
    print(
        "ROLLOVER OPERATIONAL V3 GATE | "
        f"status={s['status']} | cutoff={s['cutoff_utc']} | rollovers={s['rollovers']} | "
        f"comparisons={s['valid_comparisons']} | identity_all={s['identity_all']} | clock_all={s['clock_all']} | "
        f"by15={s['exact_active_quoted_by_15s_n']}/{s['rollovers']} "
        f"share={'NA' if fast is None else f'{fast:.3f}'} | "
        f"direct_before_broad={s['all_direct_before_broad']} | "
        f"median_lead={'NA' if lead is None else f'{lead:.3f}s'} | pass={s['pass']} | "
        "NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )


def _maybe_log_summaries(now: datetime) -> None:
    with LOCK:
        items = list(EVIDENCE.values())
    changed = False
    for ev in items:
        boundary = _parse(ev.boundary_utc)
        if boundary is None or ev.summary_printed or (now - boundary).total_seconds() < POST_WINDOW_SEC:
            continue
        print(
            "ROLLOVER PROBE V3 SUMMARY | "
            f"boundary={ev.boundary_utc} | target={ev.ticker} | samples={ev.samples} | "
            f"exact_active_quoted={ev.first_exact_active_quoted_offset} | "
            f"identity_all={ev.direct_identity_match_all} | clock_all={ev.direct_clock_match_all} | "
            f"broad_active={ev.first_broad_active_offset} | FRESH ONLY | NO ORDERS",
            flush=True,
        )
        with LOCK:
            ev.summary_printed = True
        changed = True
    if changed:
        _log_gate()


def probe_loop() -> None:
    print(
        f"{VERSION} START | cutoff={_iso(CUTOFF)} | strict Probe V2 book validity | "
        "8-rollover future-only operational replication | READ ONLY | NO ORDERS",
        flush=True,
    )
    while True:
        now = datetime.now(timezone.utc)
        try:
            row = probe_once(now)
            if row:
                _log_sample(row)
            _maybe_log_summaries(now)
        except Exception as exc:
            print(
                f"ROLLOVER PROBE V3 WARNING | {type(exc).__name__}:{exc} | FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


def start_probe_thread() -> threading.Thread:
    t = threading.Thread(target=probe_loop, name="btc15-kalshi-rollover-probe-v3", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    probe_loop()
