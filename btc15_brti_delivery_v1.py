"""Local receipt-aware BRTI qualification. No network, fitting or orders."""
from collections import deque
import math
import threading


class Delivery:
    def __init__(self):
        self.lock = threading.RLock()
        self.states = deque(maxlen=600)
        self.statuses = deque(maxlen=600)
        self.seen = {}
        self.epoch = None

    def accept(self, value, source, observed, epoch):
        value, source, observed = map(float, (value, source, observed))
        if (not all(math.isfinite(x) for x in (value, source, observed))
                or not 0 <= observed-source <= 5 or not epoch):
            raise ValueError('Unqualified BRTI receipt')
        with self.lock:
            if self.statuses and observed < self.statuses[-1][0]:
                raise ValueError('BRTI receipt clock moved backwards')
            if self.epoch != epoch:
                self.states.clear()
                self.statuses.clear()
                self.epoch = epoch
            if self.states:
                last = self.states[-1]
                if source < last['cf_ts'] or (source == last['cf_ts'] and value != last['value']):
                    raise ValueError('Conflicting or regressed BRTI source')
            if not self.states or source != self.states[-1]['cf_ts']:
                self.states.append(dict(value=value, cf_ts=source, observed_ts=observed, owner_epoch=epoch))
            self.statuses.append((observed, True))

    def fail(self, observed):
        with self.lock:
            self.statuses.append((float(observed), False))

    def remember(self, points, observed):
        with self.lock:
            for source, value in points:
                if math.isfinite(source) and math.isfinite(value) and 0 < source <= observed:
                    self.seen.setdefault((source, value), observed)
            self.seen = {k:v for k,v in self.seen.items() if k[0] >= observed-600}

    def known_at(self, source, value, cut):
        with self.lock:
            return source <= cut and self.seen.get((source, value), math.inf) <= cut

    def select(self, cut, now):
        """Never borrow a receipt after cut, or refresh an old decision clock."""
        with self.lock:
            points = [s for s in self.states if s['observed_ts'] <= cut and s['cf_ts'] <= cut]
            statuses = [s for s in self.statuses if s[0] <= cut]
            if not points:
                return None
            row = dict(points[-1])
            age, current_age = cut-row['cf_ts'], now-row['cf_ts']
            current_ok = bool(self.statuses and self.statuses[-1][1])
            cut_ok = bool(statuses and statuses[-1][1])
            ready = cut <= now and 0 <= age <= 5 and 0 <= current_age <= 5 and cut_ok and current_ok
            row.update(age=age, current_age=current_age, ready=ready,
                       decision_ts=cut, checked_ts=now,
                       reason='QUALIFIED' if ready else 'SOURCE_STALE_OR_PRIMARY_UNAVAILABLE')
            return row
