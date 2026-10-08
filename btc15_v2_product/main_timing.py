"""MAIN-only fresh-receipt scheduling. No new source, thread, lease or orders.

One serial native evaluator, at most once/second, using the existing BRTI
receipt owner. HTTP reads remain at most once/five seconds per source. Every
admitted evaluation runs the original model, reducers and durable journals.
"""
from copy import deepcopy
import math
import time
from .bootstrap import identity

MIN_INTERVAL = 1.0
MAINTENANCE_INTERVAL = 5.0
HTTP_INTERVAL = 5.0


class ReadCadence:
    """Reuse original receipts, never their validity or their receipt clocks."""
    def __init__(self, read, validate, clock=time.monotonic, context=lambda:None):
        self.read, self.validate, self.clock = read, validate, clock
        self.context, self.last_context = context, context()
        self.next_read = -math.inf
        self.value = None
        self.requests = self.reuses = 0

    def __call__(self):
        context = self.context()
        if context != self.last_context:
            # One necessary official read at rollover, never an old market
            # reused under a new window. Failed reads still respect retry delay.
            self.last_context, self.next_read, self.value = context, -math.inf, None
        if self.clock() >= self.next_read:
            self.next_read = self.clock() + HTTP_INTERVAL
            self.value = None  # A failed refresh cannot silently revive old data.
            self.requests += 1
            value = self.read()
            self.validate(value)
            self.value = deepcopy(value)
        else:
            self.reuses += 1
        self.validate(self.value)  # Recheck expiry/official window on EVERY use.
        return deepcopy(self.value)


class Scheduler:
    def __init__(self, ns, healthy, clock=time.time, monotonic=time.monotonic,
                 sleep=time.sleep):
        self.ns, self.healthy = ns, healthy
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.last_at = -math.inf
        self.last_key = None
        self.last_slot = None
        self.attempts = self.fresh_wakes = self.pressure_waits = 0
        self.reason = 'STARTUP'
        self.next_heartbeat = self.monotonic() + 30.

    def key(self):
        at = self.clock()
        # Existing qualification also checks current failure state and causal cut.
        row = self.ns['_brti_delivery'].select(at, at)
        if not row or not row['ready']:
            return None
        return row['owner_epoch'], row['cf_ts'], row['value']

    def ready(self):
        now = self.monotonic()
        elapsed = now - self.last_at
        slot = int(self.clock() // 900)
        key = self.key()
        if elapsed < MIN_INTERVAL:
            return False
        if not self.healthy():
            self.reason = 'PUBLICATION_BACKPRESSURE'
            self.pressure_waits += 1
            return False
        fresh = key is not None and key != self.last_key
        if not (fresh or slot != self.last_slot or elapsed >= MAINTENANCE_INTERVAL):
            return False
        self.reason = 'FRESH_BRTI' if fresh else 'ROLLOVER_OR_MAINTENANCE'
        self.last_at, self.last_key, self.last_slot = now, key, slot
        self.attempts += 1
        self.fresh_wakes += int(fresh)
        return True

    def wait(self):
        while self.ns.get('running', False):
            if self.ready():
                return True
            # Inspect local memory only; this is NOT another source API poller.
            self.sleep(.05)
        return False

    def after_attempt(self):
        # All normal, exception and early-continue paths return to wait().
        # There is no catch-up burst after blocked work or a slow journal.
        pass

    def heartbeat(self):
        if self.monotonic() < self.next_heartbeat:
            return False
        self.next_heartbeat = self.monotonic() + 30.
        return True

    def annotate(self):
        # Attach counters to the existing attempt row, never another journal
        # stream. They are diagnostic only and cannot enter native qualification.
        from .admin import LOCAL
        attempt = getattr(LOCAL, 'attempt', None)
        if attempt is not None:
            attempt['scheduling'] = dict(policy='FRESH_BRTI_MAX_1HZ_HTTP_5S',
                trigger=self.reason, attempts=self.attempts, fresh_wakes=self.fresh_wakes,
                pressure_waits=self.pressure_waits, market_reads=self.market.requests,
                market_reuses=self.market.reuses, btc_reads=self.btc.requests,
                btc_reuses=self.btc.reuses)


def install(ns, pool, worker, admin, clock=time.time, monotonic=time.monotonic,
            sleep=time.sleep):
    original_market, original_btc = ns['get_active_market'], ns['get_btc_spot']

    def market_ok(value):
        if value is None:
            raise ValueError('OFFICIAL_MARKET_UNAVAILABLE')
        target = ns['extract_target'](value)
        current = identity(value, target)
        if (target is None or current != pool.official
                or not current['official_open'] <= clock() < current['official_close']):
            raise ValueError('OFFICIAL_MARKET_UNAVAILABLE')

    def read_btc():
        price = original_btc()
        return dict(price=price, provenance=deepcopy(ns['_btc_spot_provenance']))

    def btc_ok(value):
        if not value or not value.get('provenance'):
            raise ValueError('BTC_SOURCE_UNQUALIFIED')
        p = value['provenance']
        source, received = p['source_utc'].timestamp(), p['observed_utc'].timestamp()
        if (not math.isfinite(value['price']) or value['price'] <= 0
                or not source <= received <= clock() or clock()-source > 10):
            raise ValueError('BTC_SOURCE_UNQUALIFIED')

    market = ReadCadence(original_market, market_ok, monotonic, lambda:int(clock()//900))
    btc = ReadCadence(read_btc, btc_ok, monotonic)

    def spot():
        try:
            sample = btc()
        except Exception:
            ns['_btc_spot_provenance'] = None
            raise
        ns['_btc_spot_provenance'] = sample['provenance']
        return sample['price']

    def healthy():
        # Reserve room for a concurrent closeout; do not size up any queue.
        # unfinished_tasks includes the record currently being committed.
        proof = getattr(pool.current, 'proof_writer', None)
        return (not worker.failed and worker.thread.is_alive()
                and worker.queue.unfinished_tasks == 0
                and not admin.failed and admin.thread.is_alive()
                and admin.queue.qsize() <= admin.queue.maxsize-4
                and (proof is None or proof.queue.unfinished_tasks == 0))

    scheduler = Scheduler(ns, healthy, clock, monotonic, sleep)
    scheduler.market, scheduler.btc = market, btc
    ns['get_active_market'], ns['get_btc_spot'] = market, spot
    ns['_v2_timing'] = scheduler
    return scheduler


def instrument(tree):
    """Replace ONLY the MAIN loop's sleeps, leaving background cadences intact."""
    import ast
    tree = deepcopy(tree)
    loops = [n for n in tree.body if isinstance(n, ast.While)
             and isinstance(n.test, ast.Name) and n.test.id == 'running']
    if len(loops) != 1:
        raise ValueError('PINNED_MAIN_TIMING_LOOP')
    loop = loops[0]

    class Sleeps(ast.NodeTransformer):
        count = 0
        def visit_Call(self, node):
            self.generic_visit(node)
            if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'time' and node.func.attr == 'sleep'):
                self.count += 1
                return ast.copy_location(ast.parse('_v2_timing.after_attempt()').body[0].value, node)
            return node

    sleeps = Sleeps()
    sleeps.visit(loop)
    if sleeps.count != 3:
        raise ValueError('PINNED_MAIN_SLEEP_SEAMS')
    heartbeats = [n for n in ast.walk(loop) if isinstance(n, ast.If)
                  and ast.unparse(n.test) == 'iteration % 6 == 0']
    if len(heartbeats) != 1:
        raise ValueError('PINNED_MAIN_HEARTBEAT_SEAM')
    heartbeats[0].test = ast.parse('_v2_timing.heartbeat()', mode='eval').body
    loop.body[:0] = ast.parse('if not _v2_timing.wait():\n    break').body
    return ast.fix_missing_locations(tree)
