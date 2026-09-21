"""Passive discovery diagnostics. No requests, credentials, or trading code.

Events are queued without waiting for stdout. A full queue loses diagnostics,
not production work. Unknown/malformed metadata is never labelled as absence.
SIGNAL ONLY / NO ORDERS. Runtime integration is a separate, hash-guarded patch.
"""
from __future__ import annotations

import itertools
import json
import queue
import re
import threading
import time
from datetime import datetime, timezone

PREFIX = 'BTC15_DISCOVERY_DIAG_V2'
SAFE_HEADERS = ('age', 'cache-control', 'date', 'expires', 'etag', 'via',
                'x-cache', 'cf-cache-status')
_TICKER = re.compile(r'^KXBTC15M-[A-Z0-9-]{1,48}$')
_QUEUE = queue.Queue(maxsize=256)
_START_LOCK = threading.Lock()
_WORKER = None
_IDS = itertools.count(1)
_DROPPED = 0


def _clock():
    return datetime.now(timezone.utc), time.monotonic_ns()


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _boundary(at):
    floor = int(at.timestamp()) // 900 * 900
    seconds = at.timestamp() - floor
    if seconds <= 90:
        return datetime.fromtimestamp(floor, timezone.utc)
    if seconds >= 895:
        return datetime.fromtimestamp(floor + 900, timezone.utc)
    return None


def _writer():
    while True:
        item = _QUEUE.get()
        try:
            print(PREFIX + ' | ' + json.dumps(item, separators=(',', ':'),
                                             sort_keys=True, allow_nan=False), flush=True)
        except Exception:
            pass
        finally:
            _QUEUE.task_done()


def _enqueue(item):
    global _WORKER, _DROPPED
    try:
        if _WORKER is None or not _WORKER.is_alive():
            if not _START_LOCK.acquire(blocking=False):
                _DROPPED += 1
                return
            try:
                if _WORKER is None or not _WORKER.is_alive():
                    _WORKER = threading.Thread(target=_writer, daemon=True,
                                               name='btc15-discovery-diag')
                    _WORKER.start()
            finally:
                _START_LOCK.release()
        item['dropped_events_total'] = _DROPPED
        _QUEUE.put_nowait(item)
    except Exception:
        _DROPPED += 1


def _event(ctx, event, at, details):
    _enqueue({'event': event, 'component': 'main.runtime_market_discovery',
              'request_id': ctx['id'], 'timestamp_utc': _iso(at),
              'expected_open_utc': _iso(ctx['boundary']),
              'ms_from_open': round((at - ctx['boundary']).total_seconds() * 1000, 3),
              'details': details, 'signal_only': True, 'orders': False})


def begin(path, params):
    """Best effort. No HTTP operation, auth object, or mutable source retained."""
    try:
        if (path != '/trade-api/v2/markets' or not isinstance(params, dict)
                or params.get('series_ticker') != 'KXBTC15M'):
            return None
        wall, mono = _clock()
        boundary = _boundary(wall)
        ctx = {'id': f'{mono}-{next(_IDS)}', 'wall': wall, 'mono': mono,
               'boundary': boundary, 'announced': boundary is not None}
        if boundary is not None:
            _event(ctx, 'REQUEST_STARTED', wall, {'recorded_after_response': False})
        return ctx
    except Exception:
        return None


def response(ctx, raw_response):
    """Receipt time precedes raise_for_status/json; only allowlisted headers."""
    if ctx is None:
        return
    try:
        wall, mono = _clock()
        if ctx['boundary'] is None:
            ctx['boundary'] = _boundary(wall)
            if ctx['boundary'] is None:
                return
        if not ctx['announced']:
            _event(ctx, 'REQUEST_STARTED', ctx['wall'], {'recorded_after_response': True})
            ctx['announced'] = True
        status = raw_response.status_code
        safe = {}
        for name in SAFE_HEADERS:
            value = raw_response.headers.get(name)
            if isinstance(value, str):
                safe[name] = value[:256]
        _event(ctx, 'RESPONSE_RECEIVED', wall,
               {'http_status': status if type(status) is int else None,
                'request_started_utc': _iso(ctx['wall']),
                'latency_ms_monotonic': round((mono - ctx['mono']) / 1e6, 3),
                'safe_cache_headers': safe})
    except Exception:
        pass


def decoded(ctx, data):
    """Inspect only ticker/open/close metadata, never labels, orders, or prices."""
    if ctx is None or ctx['boundary'] is None:
        return
    try:
        wall, _ = _clock()
        markets = data.get('markets') if isinstance(data, dict) else None
        valid_container = isinstance(markets, list)
        rows = markets[:1000] if valid_container else []
        unresolved = 0
        if not valid_container:
            unresolved = 1
        if valid_container and len(markets) > 1000:
            unresolved += len(markets) - 1000
        found = []
        active = []
        for row in rows:
            if not isinstance(row, dict):
                unresolved += 1
                continue
            ticker = row.get('ticker')
            op, cl = _date(row.get('open_time')), _date(row.get('close_time'))
            if not isinstance(ticker, str) or not _TICKER.fullmatch(ticker) or op is None or cl is None or op >= cl:
                unresolved += 1
                continue
            if abs((op - ctx['boundary']).total_seconds()) <= 1:
                found.append(ticker)
            if op <= wall < cl:
                active.append(ticker)
        presence = True if found else (False if unresolved == 0 else None)
        _event(ctx, 'MARKET_LIST_DECODED', wall,
               {'market_count': len(markets) if valid_container else None,
                'unresolved_metadata_rows': unresolved,
                'expected_open_present': presence,
                'opening_tickers': found[:20],
                'active_tickers_at_decode': active[:20]})
    except Exception:
        pass


def failed(ctx, phase):
    if ctx is None:
        return
    try:
        if phase not in ('transport', 'http_status', 'json_decode'):
            phase = 'unknown'
        wall, _ = _clock()
        if ctx['boundary'] is None:
            ctx['boundary'] = _boundary(wall)
            if ctx['boundary'] is None:
                return
        _event(ctx, 'REQUEST_FAILED', wall, {'phase': phase})
    except Exception:
        pass
