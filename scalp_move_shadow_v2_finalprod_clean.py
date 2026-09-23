#!/usr/bin/env python3
"""Clean prospective scalp-move collector on the final production data plumbing.

Frozen detector/event logic is the exact historical full-time V2 transform.
Only the snapshot plumbing is replaced:
- BRTI: qualified websocket gateway consumer used by production.
- Kalshi quotes: timestamped/sequence-aware websocket provenance used by production.
- Production dashboard: read-only PASS/alignment/safety guard.
- BTC: unchanged Coinbase spot source.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS.
"""
from __future__ import annotations
import ast, base64, gzip, hashlib, os, time
from pathlib import Path
from datetime import datetime, timezone
import requests

BASE = Path(__file__).with_name("scalp_move_shadow_v1.py")
V1_SHA256 = "3fdb2ef60f184e1ce2cef306c1db2a9de03b3e7b1a27c32b6bfffabb2cf60c48"
V2_SHA256 = "52b79e239c0be2b5ece93e3387063185ce51be8a01413f6b76bc5939924fb3ad"
PROD_STATE_URL = os.getenv(
    "BTC15_FINAL_PROD_STATE_URL",
    "https://btc-15min-bot-production.up.railway.app/dashboard_state.json",
).strip()

src = BASE.read_text(encoding="utf-8")
tree = ast.parse(src, filename=str(BASE))
payload = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "PAYLOAD" for t in node.targets
    ):
        payload = ast.literal_eval(node.value)
        break
if payload is None:
    raise RuntimeError("frozen V1 payload missing")
raw = gzip.decompress(base64.b64decode(payload)).decode("utf-8")
if hashlib.sha256(raw.encode()).hexdigest() != V1_SHA256:
    raise RuntimeError("frozen V1 payload SHA mismatch")

replacements = (
    ("PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V1", "PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V2 FULL-TIME"),
    ("MIN_LEFT = 120.0", "MIN_LEFT = 0.0"),
    ("MOVE_BASED_PRICE_AGNOSTIC|SIGNAL_ONLY|NO_ORDERS", "MOVE_BASED_PRICE_AGNOSTIC|FULL_TIME_V2|SIGNAL_ONLY|NO_ORDERS"),
    ("PATH_TELEMETRY|PRICE_AGNOSTIC|NO_ORDERS", "PATH_TELEMETRY|PRICE_AGNOSTIC|FULL_TIME_V2|NO_ORDERS"),
    ("SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|NO_ORDERS", "SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|FULL_TIME_V2|NO_ORDERS"),
    ("SCALP MOVE SHADOW V1 START | PRICE-AGNOSTIC | EXECUTABLE ASK->BID | ",
     "SCALP MOVE SHADOW V2 START | PRICE-AGNOSTIC | FULL-TIME 15:00->0:00 | EXECUTABLE ASK->BID | "),
)
for old, new in replacements:
    if raw.count(old) != 1:
        raise RuntimeError("unexpected frozen V2 transform source")
    raw = raw.replace(old, new)
if hashlib.sha256(raw.encode()).hexdigest() != V2_SHA256:
    raise RuntimeError("frozen V2 payload SHA mismatch")

marker = "def main():"
if raw.count(marker) != 1:
    raise RuntimeError("frozen main boundary mismatch")
prefix, suffix = raw.split(marker, 1)
exec(compile(prefix, "scalp_move_shadow_v2_frozen_prefix.py", "exec"), globals())

from btc15_brti_shared_consumer_v1 import read_shared_brti
from btc15_kalshi_quote_provenance_v1 import consume as consume_ws_quotes

EVENTS = Path(os.getenv("SCALP_EVENT_CSV", "scalp_finalprod_clean_events_v1.csv"))
STATE = Path(os.getenv("SCALP_STATE_JSON", "scalp_finalprod_clean_state_v1.json"))
_clean_http = requests.Session()
_clean_prod_guard = {"at": 0.0, "ticker": None, "target": None, "ok": False}
_clean_stats = {
    "accepted_frames": 0,
    "prod_guard_waits": 0,
    "brti_waits": 0,
    "quote_waits": 0,
    "metadata_waits": 0,
}

def _truth(v):
    return v is True or str(v).strip().lower() == "true"

def _production_guard(ticker, target):
    now = time.time()
    cached = (
        _clean_prod_guard["ok"]
        and _clean_prod_guard["ticker"] == ticker
        and abs(float(_clean_prod_guard["target"]) - float(target)) <= 0.01
        and now - _clean_prod_guard["at"] <= 2.0
    )
    if cached:
        return True
    try:
        r = _clean_http.get(
            PROD_STATE_URL,
            timeout=2.0,
            headers={"Cache-Control": "no-cache", "User-Agent": "btc15-clean-ladder-v1"},
        )
        r.raise_for_status()
        d = r.json()
        p = d.get("parity") or {}
        h = d.get("health") or {}
        s = d.get("safety") or {}
        m = d.get("market") or {}
        pt = dt(p.get("timestamp_utc"))
        parity_age = None if pt is None else (datetime.now(timezone.utc) - pt).total_seconds()
        ok = bool(
            d.get("contract") == ticker
            and num(m.get("target")) is not None
            and abs(float(m["target"]) - float(target)) <= 0.01
            and p.get("status") == "PASS"
            and all(_truth(p.get(k)) for k in (
                "contract_match", "clock_match", "target_match", "quote_match", "brti_match"
            ))
            and h.get("brti_fresh") is True
            and h.get("paired_quotes") is True
            and h.get("source_fresh") is True
            and h.get("market_open") is True
            and s.get("orders_enabled") is False
            and s.get("read_only") is True
            and s.get("trading_logic_changed") is False
            and parity_age is not None and 0 <= parity_age <= 30
        )
        _clean_prod_guard.update(at=now, ticker=ticker, target=target, ok=ok)
        return ok
    except Exception:
        _clean_prod_guard.update(at=now, ticker=ticker, target=target, ok=False)
        return False

def snap():
    m = active_market()
    if not m:
        _clean_stats["metadata_waits"] += 1
        return None
    now = datetime.now(timezone.utc)
    close = dt(m.get("close_time"))
    target = target_from_market(m)
    ticker = str(m.get("ticker") or "")
    if not ticker.startswith("KXBTC15M") or close is None or target is None:
        _clean_stats["metadata_waits"] += 1
        return None
    if not _production_guard(ticker, target):
        _clean_stats["prod_guard_waits"] += 1
        return None

    try:
        b = read_shared_brti(timeout_s=0.8)
        bage = num(b.get("age_seconds"))
        if (
            b.get("status") != "PRIMARY_OK"
            or bage is None or not 0 <= bage <= 5
            or b.get("orders") is not False
        ):
            raise RuntimeError("BRTI not qualified")
        bval = float(b["value"])
    except Exception:
        _clean_stats["brti_waits"] += 1
        return None

    frame_time = datetime.now(timezone.utc)
    quotes = consume_ws_quotes(
        ticker,
        frame_time.isoformat(),
        int(close.timestamp() * 1000),
    )
    if quotes is None:
        _clean_stats["quote_waits"] += 1
        return None
    ub, ua, db, da = quotes
    if not all(valid_quote(v) for v in (ub, ua, db, da)) or ub > ua or db > da:
        _clean_stats["quote_waits"] += 1
        return None

    try:
        c = _clean_http.get(CB, timeout=3.0)
        c.raise_for_status()
        btc_response = c.json()
        btc = float(btc_response["price"])
        btc_received_utc = datetime.now(timezone.utc).isoformat()
    except Exception:
        return None

    # Recheck source age after the BTC request; receipt time never refreshes BRTI.
    final_time = datetime.now(timezone.utc)
    source_ms = b.get('source_ts_ms')
    if type(source_ms) is not int or not 0 <= final_time.timestamp()-source_ms/1000.0 <= 5:
        _clean_stats['brti_waits'] += 1
        return None
    if not 0 < (close-final_time).total_seconds() <= 900:
        _clean_stats['metadata_waits'] += 1
        return None
    quotes = consume_ws_quotes(ticker, final_time.isoformat(), int(close.timestamp()*1000))
    if quotes is None:
        _clean_stats['quote_waits'] += 1
        return None
    ub,ua,db,da=quotes
    if not all(valid_quote(v) for v in quotes) or ub>ua or db>da:
        _clean_stats['quote_waits'] += 1
        return None
    final_time = datetime.now(timezone.utc)
    if not 0 <= final_time.timestamp()-source_ms/1000.0 <= 5:
        _clean_stats['brti_waits'] += 1
        return None
    if not 0 < (close-final_time).total_seconds() <= 900:
        _clean_stats['metadata_waits'] += 1
        return None

    evidence_path = os.getenv('BTC15_COMMON_OBSERVATIONS')
    if evidence_path:
        from btc15_common_observer_v1 import append_record
        append_record(evidence_path, dict(schema_version=1, record_type='SNAPSHOT_INPUT',
            run_id=os.getenv('BTC15_CLEAN_RUN_ID'), observed_utc=final_time.isoformat(),
            ticker=ticker, target=target, close_utc=close.isoformat(),
            brti_source_ts_ms=source_ms, brti_value=bval, owner_epoch=b.get('owner_epoch'),
            btc_price=btc, btc_source_utc=btc_response.get('time'), btc_received_utc=btc_received_utc,
            quote_validation_utc=final_time.isoformat(), quote_transport='timestamped_contiguous_ws',
            up_bid=ub, up_ask=ua, down_bid=db, down_ask=da,
            source_time_missing_is_not_replaced=True, signal_only=True, orders=False))

    _clean_stats["accepted_frames"] += 1
    health["snapshots"] += 1
    health["brti_clean_snapshots"] += 1
    return {
        "ts": time.time(),
        "ticker": ticker,
        "contract_close_utc": close.isoformat(),
        "left": max(0.0, (close - final_time).total_seconds()),
        "target": float(target),
        "btc": btc,
        "brti": bval,
        "brti_status": "PRIMARY_OK",
        "brti_attempts": 0,
        "brti_latency_ms": None,
        "brti_error_type": "",
        "up_bid": float(ub),
        "up_ask": float(ua),
        "down_bid": float(db),
        "down_ask": float(da),
    }

print(
    "SCALP FINALPROD CLEAN SOURCE | frozen_v2_sha=" + V2_SHA256
    + " | qualified shared BRTI source v2 | timestamped Kalshi quote WS | production PASS guard"
    + " | SIGNAL ONLY | NO ORDERS",
    flush=True,
)
exec(compile(marker + suffix, "scalp_move_shadow_v2_finalprod_clean.py", "exec"), globals())
