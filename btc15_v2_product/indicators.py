"""Display-only completed Coinbase BTC-USD one-minute candles.

RSI uses a 14-change SMA seed then Wilder smoothing. MACD uses SMA-seeded
12/26 EMAs and a nine-MACD-value SMA seed for its signal EMA. No partial bar,
interpolation, synthetic volume, strategy callback, or native-data mutation.
"""
from datetime import datetime, timezone
import math
import threading
import time

URL = 'https://api.exchange.coinbase.com/products/BTC-USD/candles'
SCHEMA = 'BTC15_DISPLAY_INDICATORS_R1'
MAX_CANDLES = 300
MAX_CLOSE_AGE = 75.  # Latest completed minute, with 15 seconds delivery grace.


def ema(values, period):
    if len(values) < period:
        raise ValueError('INSUFFICIENT_COMPLETED_HISTORY')
    result = [None] * (period-1)
    value = sum(values[:period]) / period
    result.append(value)
    alpha = 2. / (period+1)
    for observation in values[period:]:
        value += alpha * (observation-value)
        result.append(value)
    return result


def calculate(rows, cutoff, received):
    if not math.isfinite(cutoff) or not math.isfinite(received) or cutoff > received:
        raise ValueError('CANDLE_CAUSAL_ORDER')
    if not isinstance(rows, list) or len(rows) > MAX_CANDLES+1:
        raise ValueError('CANDLE_PAYLOAD_BOUND')
    completed = {}
    for row in rows:
        if not isinstance(row, (list,tuple)) or len(row) != 6:
            raise ValueError('CANDLE_SHAPE')
        if not all(type(x) in (int,float) and math.isfinite(x) for x in row):
            raise ValueError('CANDLE_NONFINITE')
        opened, low, high, op, close, volume = row
        if opened % 60 or opened > received or not 0 < low <= min(op,close) <= max(op,close) <= high or volume < 0:
            raise ValueError('CANDLE_INVALID')
        if opened+60 > cutoff:
            continue  # The endpoint can include the current unfinished minute.
        if opened in completed and completed[opened] != row:
            raise ValueError('CANDLE_DUPLICATE_CONFLICT')
        completed[opened] = row
    bars = sorted(completed.values())[-MAX_CANDLES:]
    if not bars:
        raise ValueError('INSUFFICIENT_COMPLETED_HISTORY')
    if any(b[0]-a[0] != 60 for a,b in zip(bars,bars[1:])):
        raise ValueError('COMPLETED_HISTORY_GAP')
    end = bars[-1][0]+60
    if not 0 <= received-end < MAX_CLOSE_AGE:
        raise ValueError('COMPLETED_CANDLE_STALE')
    prices = [bar[4] for bar in bars]
    rsi = macd = signal = histogram = None
    if len(prices) >= 15:
        changes = [b-a for a,b in zip(prices,prices[1:])]
        gain = sum(max(d,0) for d in changes[:14])/14
        loss = sum(max(-d,0) for d in changes[:14])/14
        for delta in changes[14:]:
            gain = (13*gain+max(delta,0))/14
            loss = (13*loss+max(-delta,0))/14
        rsi = 50. if gain == loss == 0 else 100. if loss == 0 else 100.-100./(1.+gain/loss)
    if len(prices) >= 34:
        fast, slow = ema(prices,12), ema(prices,26)
        macds = [a-b for a,b in zip(fast[25:],slow[25:])]
        macd, signal = macds[-1], ema(macds,9)[-1]
        histogram = macd-signal
    return dict(schema=SCHEMA, status='AVAILABLE', authority='DISPLAY_ONLY',
        provider='COINBASE_EXCHANGE', product='BTC-USD', granularity=60,
        candle_open=bars[-1][0], candle_close=end, request_cutoff=cutoff, received_ts=received,
        expires_at=end+MAX_CLOSE_AGE, history_start=bars[0][0], completed_count=len(bars),
        rsi=rsi, macd=macd, signal=signal, histogram=histogram, volume=bars[-1][5],
        volume_unit='BTC', signal_only=True, orders=False)


class IndicatorFeed:
    def __init__(self, get=None, clock=time.time):
        self.get, self.clock = get, clock
        self.latest = None
        self.reason = 'COMPLETED_CANDLES_STARTING'
        self.stop = threading.Event()
        self.thread = None
        self.start_lock = threading.Lock()
        self.requests = 0
        self.last_cutoff = None

    def sample(self):
        if self.get is None:
            import requests
            self.get = requests.get
        started = self.clock()
        cutoff = int(started//60)*60
        self.last_cutoff = cutoff
        iso = lambda t: datetime.fromtimestamp(t,timezone.utc).isoformat()
        try:
            self.requests += 1
            response = self.get(URL, params=dict(granularity=60,
                start=iso(cutoff-MAX_CANDLES*60),end=iso(cutoff)), timeout=5)
            response.raise_for_status()
            value = calculate(response.json(), cutoff, self.clock())
            if self.latest and value['candle_close'] < self.latest['candle_close']:
                raise ValueError('CANDLE_TIME_ROLLBACK')
            self.latest, self.reason = value, None
        except Exception as exc:
            # A failed refresh never re-stamps or prolongs the last observation.
            self.reason = str(exc) if isinstance(exc,ValueError) else 'COMPLETED_CANDLE_TRANSPORT'
            if isinstance(exc,ValueError):
                self.latest = None

    def capture(self):
        now = self.clock()
        value = self.latest
        if value and value['received_ts'] <= now < value['expires_at']:
            return dict(value, served_ts=now)
        return dict(schema=SCHEMA, status='UNAVAILABLE', authority='DISPLAY_ONLY',
            reason=self.reason or 'COMPLETED_CANDLE_STALE', served_ts=now,
            signal_only=True, orders=False)

    def start(self):
        with self.start_lock:
            if self.thread is not None:
                return
            def run():
                while not self.stop.is_set():
                    self.sample()
                    # One request/minute, two seconds after the boundary. No
                    # retries, per-browser polling, or native strategy work.
                    now = self.clock()
                    due = self.last_cutoff+62
                    self.stop.wait(max(1.,due-now))
            self.thread = threading.Thread(target=run,daemon=True,name='display-completed-candles')
            self.thread.start()


FEED = IndicatorFeed()
