"""Opt-in read-only Kalshi orderbook provenance. NO ORDERS.

A proof contains upstream snapshot/deltas, not a second copy of bot prices.
The parity process replays it and joins the exact collector frame and market.
No REST seed, interpolation, timestamp tolerance, or recovery across gaps.
"""
import json
import os
import threading
import time
import uuid
from datetime import datetime
from decimal import Decimal
from btc15_data_paths_v1 import _btc15_data_path

FLAG = 'BTC15_KALSHI_QUOTE_PROVENANCE_CANARY'
MAX_BYTES = 2 * 1024 * 1024
MAX_AGE = 6.0  # Existing parity quote age ceiling; not a strategy threshold.
WS_URL = 'wss://external-api-ws.kalshi.com/trade-api/ws/v2'
WS_PATH = '/trade-api/ws/v2'


def enabled():
    # Historical env name retained for compatibility. The qualified quote
    # provenance path is read-only and may run against either the isolated
    # canary data root or the normal production data root.
    return os.getenv(FLAG, '').strip() == '1'


def proof_path():
    return _btc15_data_path('kalshi_quote_provenance_v1.json')


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('nonfinite book value')
    return result


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('invalid integer identity')
    return value


class MissingQuoteField(KeyError):
    """Only approved schema keys may appear in diagnostics; never raw values."""
    def __init__(self, key, event_type):
        allowed = {'msg', 'market_ticker', 'market_id', 'sid', 'seq', 'type',
                   'yes_dollars_fp', 'no_dollars_fp', 'ts_ms', 'ts',
                   'price_dollars', 'delta_fp', 'side'}
        self.field = key if isinstance(key, str) and key in allowed else 'UNKNOWN_FIELD'
        kind = event_type if event_type in {'orderbook_snapshot', 'orderbook_delta'} else 'unknown'
        self.path = 'Book.apply->Book._apply/' + kind
        super().__init__(self.field)

    def __str__(self):
        return 'missing_field=' + self.field + ' | path=' + self.path


class Book:
    def __init__(self, ticker):
        self.ticker = ticker
        self.market_id = self.sid = self.seq = self.ts_ms = None
        self.levels = {'yes': {}, 'no': {}}
        self.last = None
        self.valid = True

    def apply(self, event):
        try:
            return self._apply(event)
        except KeyError as exc:
            self.valid = False
            raise MissingQuoteField(exc.args[0] if exc.args else None, event.get("type")) from None
        except Exception:
            self.valid = False
            raise

    def _apply(self, event):
        if not self.valid:
            raise ValueError('invalidated book requires new connection snapshot')
        if event['type'] == 'ok':
            if (self.seq is None or integer(event['sid']) != self.sid
                    or integer(event['seq']) != self.seq + 1
                    or event.get('msg', {}).get('market_tickers', [self.ticker]) != [self.ticker]):
                raise ValueError('invalid sequenced snapshot acknowledgement')
            self.seq, self.last = event['seq'], event
            return True
        msg = event['msg']
        if msg['market_ticker'] != self.ticker or not msg.get('market_id'):
            raise ValueError('cross-market or missing identity')
        sid, seq = integer(event['sid']), integer(event['seq'])
        if self.seq is not None:
            if sid != self.sid or msg['market_id'] != self.market_id:
                raise ValueError('subscription or market identity changed')
            if seq == self.seq and event == self.last:
                return False  # Never renew a duplicate's exchange timestamp.
            if seq != self.seq + 1:
                raise ValueError('sequence gap, out of order, or conflicting duplicate')
        if event['type'] == 'orderbook_snapshot':
            if self.seq is not None:
                raise ValueError('unexpected snapshot')
            for side in ('yes', 'no'):
                # Official snapshots omit empty sides. Empty is never a quote.
                for price, quantity in msg.get(side + '_dollars_fp', []):
                    p, q = decimal(price), decimal(quantity)
                    if not 0 <= p <= 1 or q <= 0 or p in self.levels[side]:
                        raise ValueError('invalid or duplicate snapshot level')
                    self.levels[side][p] = q
            # Official snapshots have no timestamp. Never invent one.
        elif event['type'] == 'orderbook_delta':
            if self.seq is None:
                raise ValueError('delta without snapshot')
            ts_ms = integer(msg['ts_ms'])
            # Deprecated ts is optional; ts_ms remains mandatory for our evidence.
            if 'ts' in msg:
                ts = datetime.fromisoformat(msg['ts'].replace('Z', '+00:00'))
                if ts.tzinfo is None or int(ts.timestamp()) != ts_ms // 1000:
                    raise ValueError('ambiguous exchange timestamp')
            if self.ts_ms is not None and ts_ms < self.ts_ms:
                raise ValueError('exchange timestamp regression')
            p, delta = decimal(msg['price_dollars']), decimal(msg['delta_fp'])
            side = msg['side']
            if side not in self.levels or not 0 <= p <= 1:
                raise ValueError('invalid delta')
            quantity = self.levels[side].get(p, Decimal(0)) + delta
            if quantity < 0:
                raise ValueError('negative book level')
            if quantity:
                self.levels[side][p] = quantity
            else:
                self.levels[side].pop(p, None)
            self.ts_ms = ts_ms
        else:
            raise ValueError('not an orderbook event')
        self.market_id, self.sid, self.seq = msg['market_id'], sid, seq
        self.last = event
        return True

    def quotes(self, now_ms, close_ms):
        if not self.valid or self.ts_ms is None:
            raise ValueError('missing timestamped contiguous book')
        if not 0 <= now_ms - self.ts_ms <= MAX_AGE * 1000:
            raise ValueError('stale or future quote')
        if not close_ms - 900000 <= self.ts_ms <= now_ms < close_ms:
            raise ValueError('quote outside exact contract window')
        if not self.levels['yes'] or not self.levels['no']:
            raise ValueError('missing bid side')
        yes, no = max(self.levels['yes']), max(self.levels['no'])
        if yes + no > 1:
            raise ValueError('crossed book')
        return tuple(float(v) for v in (yes, 1-no, no, 1-yes))


def subscription(ticker):
    return {'id': 1, 'cmd': 'subscribe', 'params': {
        'channels': ['orderbook_delta'], 'market_tickers': [ticker]}}


def snapshot_request(ticker, sid, command_id):
    return {'id': command_id, 'cmd': 'update_subscription', 'params': {
        'sid': sid, 'market_tickers': [ticker], 'action': 'get_snapshot'}}


class Evidence:
    """Bounded replay segment renewed only from an actual exchange snapshot."""
    def __init__(self, ticker):
        self.book = Book(ticker)
        self.events = []
        self.size = 0
        self.pending = None
        self.requested_at = None
        self.command_id = 1
        self.last_request = None
        self.overflow = False
        self.rebases = 0

    def accept(self, event):
        try:
            return self._accept(event)
        except Exception:
            self.book.valid = False
            self.events, self.size, self.overflow = [], 0, True
            raise

    def _accept(self, event):
        if event == self.book.last:
            return False
        kind = event.get('type')
        if kind == 'ok':
            if event.get('id') not in {self.pending, self.last_request} or event.get('id') is None:
                raise ValueError('unsolicited acknowledgement')
            if 'seq' not in event and 'sid' not in event:
                return False  # Unsequenced reply, never quote evidence.
        rebased = kind == 'orderbook_snapshot' and self.book.seq is not None
        if rebased:
            if (self.pending is None or event.get('id') != self.pending
                    or event.get('sid') != self.book.sid
                    or event.get('seq') != self.book.seq + 1
                    or event.get('msg', {}).get('market_id') != self.book.market_id):
                raise ValueError('snapshot response identity/sequence mismatch')
            replacement = Book(self.book.ticker)
            replacement.apply(event)
            self.book = replacement
            self.events, self.size, self.overflow = [], 0, False
            self.last_request, self.pending = self.pending, None
            self.requested_at = None
            self.rebases += 1
        elif not self.book.apply(event):
            return False
        size = len(json.dumps(event, separators=(',', ':')).encode()) + 1
        if not self.overflow and self.size + size < MAX_BYTES - 4096:
            self.events.append(event)
            self.size += size
        else:
            # Keep reading contiguous updates, but publish no evidence until an
            # exchange snapshot supplies a complete new replay starting point.
            self.events, self.size, self.overflow = [], 0, True
        return rebased

    def refresh(self, now):
        if self.pending is not None:
            if now - self.requested_at > 10:
                self.book.valid = False
                raise ValueError('exchange snapshot response timeout')
            return None
        if self.size < MAX_BYTES // 4 and not self.overflow:
            return None
        self.command_id += 1
        self.pending, self.requested_at = self.command_id, now
        return snapshot_request(self.book.ticker, self.book.sid, self.pending)


def replay(proof, source_time, ticker, close_ms, now_ms):
    """Independent process reconstructs the exact consumed exchange state."""
    if proof['source_time'] != source_time or proof['ticker'] != ticker:
        raise ValueError('missing exact collector frame or contract')
    if not isinstance(proof['epoch'], str) or not proof['epoch']:
        raise ValueError('missing connection epoch')
    consumed = integer(proof['consumed_ms'])
    if not 0 <= now_ms - consumed <= MAX_AGE * 1000:
        raise ValueError('stale or future consumption')
    book = Book(ticker)
    for event in proof['events']:
        book.apply(event)
    if [book.market_id, book.sid, book.seq, book.ts_ms] != proof['identity']:
        raise ValueError('timestamp/sequence identity mismatch')
    quotes = book.quotes(consumed, close_ms)
    book.quotes(now_ms, close_ms)
    return quotes, 'epoch=%s,sid=%s,seq=%s,ts_ms=%s' % (
        proof['epoch'], book.sid, book.seq, book.ts_ms)


def validate(source_time, ticker, close_ms, now_ms):
    path = proof_path()
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('oversized quote proof')
    return replay(json.loads(raw), source_time, ticker, close_ms, now_ms)


class Provider:
    def __init__(self):
        self.lock = threading.Lock()
        self.ticker = None
        self.book = None
        self.events = []
        self.epoch = None
        self.close_ms = None
        threading.Thread(target=self.run, daemon=True, name='kalshi-read-only-quotes').start()

    def consume(self, ticker, source_time, close_ms):
        with self.lock:
            self.close_ms = close_ms
            if ticker != self.ticker:
                self.ticker, self.book, self.events = ticker, None, []
                return None
            if self.book is None:
                return None
            consumed = int(time.time() * 1000)
            try:
                quotes = self.book.quotes(consumed, close_ms)
            except ValueError:
                return None
            proof = dict(source_time=source_time, ticker=ticker, epoch=self.epoch,
                         consumed_ms=consumed, identity=[self.book.market_id,
                         self.book.sid, self.book.seq, self.book.ts_ms], events=self.events)
            raw = json.dumps(proof, separators=(',', ':'))
            if len(raw.encode()) > MAX_BYTES:
                self.book = None
                return None
            path = proof_path()
            tmp = path.with_suffix('.tmp')
            tmp.write_text(raw)
            tmp.replace(path)
            return quotes

    def session(self, ws, ticker):
        ws.send(json.dumps(subscription(ticker)))
        evidence = Evidence(ticker)
        epoch = str(uuid.uuid4())
        print('KALSHI QUOTE WS CONNECT | ' + ticker + ' | epoch=' + epoch + ' | NO ORDERS', flush=True)
        while True:
            with self.lock:
                if self.ticker != ticker or int(time.time() * 1000) >= self.close_ms:
                    return
            command = evidence.refresh(time.monotonic())
            if command is not None:
                ws.send(json.dumps(command))
            try:
                event = json.loads(ws.recv(timeout=1))
            except TimeoutError:
                continue
            if event.get('type') == 'subscribed':
                if event.get('msg', {}).get('channel') != 'orderbook_delta':
                    raise ValueError('unexpected subscription acknowledgement')
                continue
            if event.get('type') not in {'orderbook_snapshot', 'orderbook_delta', 'ok'}:
                raise ValueError('unexpected market-data message')
            with self.lock:
                if self.ticker != ticker:
                    return
                rebased = evidence.accept(event)
                self.book = None if evidence.overflow else evidence.book
                self.events, self.epoch = evidence.events, epoch
                if rebased:
                    print('KALSHI QUOTE EVIDENCE REBASE | ' + ticker + ' | epoch=' + epoch
                          + ' | seq=' + str(evidence.book.seq) + ' | count=' + str(evidence.rebases)
                          + ' | same connection | NO ORDERS', flush=True)
                if event.get('type') == 'orderbook_snapshot':
                    empty = [side for side in ('yes', 'no') if not evidence.book.levels[side]]
                    if empty:
                        print('KALSHI QUOTE EMPTY SIDE | ' + ','.join(empty)
                              + ' | real snapshot retained | quotes unverified | NO ORDERS', flush=True)

    def run(self):
        # Lazy dependencies: offline protocol regressions never load credentials.
        from websockets.sync.client import connect
        from btc15_kalshi_parity_shadow_v1 import auth_headers
        while True:
            with self.lock:
                ticker, close_ms = self.ticker, self.close_ms
                self.book = None
            if not ticker or close_ms is None or int(time.time() * 1000) >= close_ms:
                time.sleep(.2)
                continue
            try:
                with connect(WS_URL, additional_headers=auth_headers('GET', WS_PATH),
                             open_timeout=10, close_timeout=2, max_size=MAX_BYTES) as ws:
                    self.session(ws, ticker)
            except Exception as exc:
                status = getattr(getattr(exc, 'response', None), 'status_code', 'n/a')
                reason = str(exc) if type(exc) in (ValueError, MissingQuoteField) else type(exc).__name__
                print('KALSHI QUOTE UNVERIFIED | ' + reason + ' | http=' + str(status) + ' | reconnect requires snapshot | NO ORDERS', flush=True)
            finally:
                with self.lock:
                    self.book = None
            time.sleep(1)


_provider = None


def consume(ticker, source_time, close_ms):
    global _provider
    if not enabled():
        raise ValueError('quote canary is disabled')
    if _provider is None:
        _provider = Provider()
    return _provider.consume(ticker, source_time, close_ms)
