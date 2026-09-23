"""V8.1 source integrity only. Existing detector rules remain unchanged.

Reuse the production contiguous-book decoder. REST markets identify contracts;
their untimestamped prices never enter the detector. Shared BRTI cache only.
SIGNAL ONLY / NO ORDERS.
"""
from datetime import datetime, timezone
import math
import os
import time

from btc15_brti_shared_consumer_v1 import read_shared_brti
from btc15_kalshi_quote_provenance_v1 import Provider, MAX_AGE

BRTI_MAX_AGE = 5.0
SCHEMA = 'V81_TIMESTAMPED_INPUTS_V1'


class InputUnavailable(ValueError):
    pass


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def epoch(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise InputUnavailable('OFFICIAL_CLOCK_MISSING_TIMEZONE')
    return parsed.timestamp()


class QuoteProvider(Provider):
    def frame(self, ticker, close_ms):
        """Copy a validated frame atomically, without a disk proof per poll."""
        with self.lock:
            self.close_ms = close_ms
            if self.ticker != ticker:
                self.ticker, self.book, self.events = ticker, None, []
                return None
            if self.book is None or not self.epoch:
                return None
            now_ms = int(time.time() * 1000)
            try:
                quotes = self.book.quotes(now_ms, close_ms)
            except ValueError:
                return None
            return dict(ticker=ticker, epoch=self.epoch, market_id=self.book.market_id,
                        sid=self.book.sid, sequence=self.book.seq,
                        source_ts_ms=self.book.ts_ms, validated_at_ms=now_ms,
                        transport='timestamped_contiguous_ws',
                        up_bid=quotes[0], up_ask=quotes[1],
                        down_bid=quotes[2], down_ask=quotes[3])


def require_qualified(row, now):
    """Recheck true source ages at the actual qualification/publication time."""
    p = row.get('input_provenance')
    if not isinstance(p, dict) or p.get('schema') != SCHEMA:
        raise InputUnavailable('SOURCE_PROVENANCE_MISSING')
    if p.get('signal_only') is not True or p.get('orders') is not False:
        raise InputUnavailable('SOURCE_SAFETY_SCHEMA_MISMATCH')
    q, b = p.get('quote', {}), p.get('brti', {})
    opened, closed = p.get('open_ts'), p.get('close_ts')
    if (not finite(now) or not finite(opened) or not finite(closed)
            or closed - opened != 900 or opened % 900 != 0
            or not opened <= now < closed or row.get('ticker') != p.get('ticker')
            or not str(row.get('ticker', '')).startswith('KXBTC15M-')
            or q.get('ticker') != row['ticker'] or not finite(row.get('target'))
            or row['target'] <= 0 or p.get('target') != row['target']):
        raise InputUnavailable('CONTRACT_IDENTITY_UNQUALIFIED')
    if (q.get('transport') != 'timestamped_contiguous_ws'
            or not q.get('epoch') or not q.get('market_id')
            or any(type(q.get(k)) is not int for k in ('sid', 'sequence', 'source_ts_ms', 'validated_at_ms'))
            or not opened <= q['source_ts_ms'] / 1000 <= q['validated_at_ms'] / 1000 <= now
            or not 0 <= now - q['source_ts_ms'] / 1000 <= MAX_AGE):
        raise InputUnavailable('QUOTE_SOURCE_UNQUALIFIED')
    vals = [q.get(k) for k in ('up_bid', 'up_ask', 'down_bid', 'down_ask')]
    if (not all(finite(v) and 0 <= v <= 1 for v in vals)
            or vals[0] > vals[1] or vals[2] > vals[3]
            or any(row.get(k) != q[k] for k in ('up_bid','up_ask','down_bid','down_ask'))):
        raise InputUnavailable('QUOTE_VALUE_MISMATCH')
    if (b.get('status') != 'PRIMARY_OK' or b.get('clean_for_qualification') is not True
            or not b.get('owner_epoch') or type(b.get('source_ts_ms')) is not int
            or not 0 <= now - b['source_ts_ms'] / 1000 <= BRTI_MAX_AGE
            or not finite(b.get('value')) or not 1000 < b['value'] < 1_000_000
            or row.get('brti') != b['value']):
        raise InputUnavailable('BRTI_SOURCE_UNQUALIFIED')
    return p


def publication_view(state, now):
    """HTTP reads cannot renew source clocks or revive an expired signal."""
    out = dict(state)
    if out.get('active') is not True:
        return out
    try:
        p = out.get('input_provenance') or {}
        q = p.get('quote') or {}
        row = dict(q, ticker=out.get('contract'), target=p.get('target'),
                   brti=(p.get('brti') or {}).get('value'), input_provenance=p)
        require_qualified(row, now)
        if not 0 <= now - epoch(out.get('generated_utc')) <= 3.5:
            raise InputUnavailable('PUBLICATION_STALE')
        event = out.get('last_signal_event') or {}
        started = event.get('signal_ts')
        if not finite(started) or not 0 <= now - started <= 180:
            raise InputUnavailable('SIGNAL_HORIZON_EXPIRED')
    except (ValueError, KeyError, TypeError):
        out.update(active=False, status='WAIT', primary_wait_reason='SOURCE_UNQUALIFIED_AT_READ',
                   side=None, route=None, entry_price=None, current_bid=None, targets=None)
    return out


class QualifiedInputs:
    def __init__(self, market, target, http_get, btc_url, *, provider=None,
                 brti_read=read_shared_brti, clock=time.time):
        self.market, self.target = market, target
        self.get, self.btc_url = http_get, btc_url
        self.provider, self.brti_read, self.clock = provider, brti_read, clock
        self.fixed = None
        self.last_ticker = None

    def snapshot(self):
        # This service must never fall back to authenticated upstream BRTI.
        if os.getenv('BTC15_USE_SHARED_BRTI', '').strip() != '1':
            raise InputUnavailable('SHARED_BRTI_REQUIRED')
        market = self.market()
        if not isinstance(market, dict):
            raise InputUnavailable('OFFICIAL_MARKET_UNAVAILABLE')
        ticker = market.get('ticker')
        opened, closed = epoch(market.get('open_time')), epoch(market.get('close_time'))
        target = self.target(market)
        now = self.clock()
        if (not isinstance(ticker, str) or not ticker.startswith('KXBTC15M-')
                or closed - opened != 900 or opened % 900 != 0
                or not opened <= now < closed or not finite(target) or target <= 0):
            raise InputUnavailable('OFFICIAL_MARKET_UNQUALIFIED')
        identity = (ticker, opened, closed, target)
        if self.fixed and self.fixed[0] == ticker and self.fixed != identity:
            raise InputUnavailable('FIXED_TARGET_OR_CLOCK_CHANGED')
        self.fixed, self.last_ticker = identity, ticker
        if self.provider is None:
            self.provider = QuoteProvider()
        # Start the exact-market subscription promptly; never use REST prices.
        quote = self.provider.frame(ticker, int(closed * 1000))
        if quote is None:
            raise InputUnavailable('TIMESTAMPED_QUOTES_UNAVAILABLE')
        response = self.get(self.btc_url, timeout=5)
        response.raise_for_status()
        btc = response.json()
        price = float(btc['price'])
        if not math.isfinite(price) or price <= 0:
            raise InputUnavailable('BTC_PRICE_UNQUALIFIED')
        point = self.brti_read()
        # Network waits may age or replace the book; copy it again afterwards.
        quote = self.provider.frame(ticker, int(closed * 1000))
        if quote is None:
            raise InputUnavailable('TIMESTAMPED_QUOTES_UNAVAILABLE')
        now = self.clock()
        p = dict(schema=SCHEMA, ticker=ticker, open_ts=opened, close_ts=closed,
                 target=target, quote=quote,
                 brti={k:point.get(k) for k in ('value','source_ts_ms','owner_epoch','sequence',
                       'status','clean_for_qualification')},
                 btc_source_utc=btc.get('time'), signal_only=True, orders=False)
        row = dict(ts=now, ticker=ticker, left=closed-now, target=target,
                   btc=price, brti=point.get('value'), input_provenance=p,
                   **{k:quote[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
        require_qualified(row, now)
        return row
