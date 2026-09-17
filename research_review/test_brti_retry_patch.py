"""Exercise the actual drafted poller with a fake clock and fetch function.

No bot imports, credentials, network requests, service operations or real sleeps.
"""
import ast
from collections import deque
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research_review.brti_retry_patch import SOURCE_NAME, draft

SOURCE = (Path(__file__).resolve().parents[1] / SOURCE_NAME).read_bytes()


def function(text, name):
    node = next(n for n in ast.parse(text).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


class HttpError(Exception):
    def __init__(self, code):
        super().__init__('test HTTP ' + str(code))
        self.response = SimpleNamespace(status_code=code)


def run(events, *, candidate=True, latency=0.0, jitter=0.0, horizon=None):
    ns = {'running': True, 'BRTI_POLL_SECONDS': 1.0,
          '_brti_lock': threading.Lock(), '_brti_samples': deque(maxlen=600),
          '_brti_last_error': None, '_brti_last_error_print': 0.0}
    clock = SimpleNamespace(now=0.0, sleeps=[], attempts=[], wall=1_000.0)
    logs = []

    def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += seconds
        if horizon is not None and clock.now >= horizon:
            ns['running'] = False

    def fetch():
        i = len(clock.attempts)
        clock.attempts.append(clock.now)
        clock.now += latency
        if i + 1 >= len(events):
            ns['running'] = False
        event = events[i]
        if isinstance(event, Exception):
            raise event
        return event

    ns.update(time=SimpleNamespace(monotonic=lambda: clock.now,
                                   time=lambda: clock.wall + clock.now,
                                   sleep=sleep),
              _fetch_direct_brti_once=fetch,
              print=lambda *args: logs.append(args))
    text = draft(SOURCE) if candidate else SOURCE.decode()
    exec(function(text, '_brti_poller'), ns)
    with patch('random.uniform', return_value=jitter):
        ns['_brti_poller']()
    return ns, clock, logs


class RetryDraftTests(unittest.TestCase):
    def test_fingerprint_rejects_source_drift(self):
        with self.assertRaises(ValueError):
            draft(SOURCE + b'\n')

    def test_only_poller_changes(self):
        old = ast.parse(SOURCE.decode())
        new = ast.parse(draft(SOURCE))
        def outside(tree):
            return [ast.dump(n, include_attributes=False) for n in tree.body
                    if not (isinstance(n, ast.FunctionDef) and n.name == '_brti_poller')]
        self.assertEqual(outside(old), outside(new))

    def test_429_delays_grow_and_cap(self):
        ns, clock, _ = run([HttpError(429) for _ in range(9)])
        self.assertEqual(clock.sleeps, [2, 4, 8, 16, 30, 30, 30, 30, 30])
        self.assertEqual(list(ns['_brti_samples']), [])

    def test_backoff_follows_slow_response(self):
        _, clock, _ = run([HttpError(429), HttpError(429)], latency=8)
        self.assertEqual(clock.attempts, [0, 10])
        self.assertEqual(clock.sleeps, [2, 4])

    def test_positive_jitter_never_shortens_backoff(self):
        _, clock, _ = run([HttpError(429), HttpError(429)], jitter=0.25)
        self.assertEqual(clock.sleeps, [2.25, 4.25])

    def test_success_resets_backoff_and_retains_timestamps(self):
        ns, clock, _ = run([HttpError(429), HttpError(429), (76000, 123),
                            (76001, 123), HttpError(429)])
        self.assertEqual(clock.sleeps, [2, 4, 1, 1, 2])
        self.assertEqual(list(ns['_brti_samples']), [(123, 76000)])

    def test_success_path_matches_original(self):
        events = [(76000, 1), (76001, 1), (76002, 2)]
        new, nc, _ = run(events, latency=0.2)
        old, oc, _ = run(events, candidate=False, latency=0.2)
        self.assertEqual(list(new['_brti_samples']), list(old['_brti_samples']))
        for a, b in zip(nc.sleeps, oc.sleeps):
            self.assertAlmostEqual(a, b)
        self.assertIsNone(new['_brti_last_error'])

    def test_other_errors_do_not_claim_rate_limiting(self):
        _, clock, _ = run([HttpError(400), TimeoutError('timeout'),
                           RuntimeError('429 appears in an unrelated message')])
        self.assertEqual(clock.sleeps, [1, 1, 1])

    def test_old_samples_not_redated_on_error(self):
        ns, _, _ = run([(76000, 123), HttpError(429), HttpError(429)])
        self.assertEqual(list(ns['_brti_samples']), [(123, 76000)])
        self.assertIn('429', ns['_brti_last_error'])

    def test_synthetic_one_minute_request_pressure(self):
        failures = [HttpError(429) for _ in range(100)]
        _, new, _ = run(failures, horizon=60)
        _, old, _ = run(failures, candidate=False, horizon=60)
        self.assertEqual(len(old.attempts), 60)
        self.assertEqual(new.attempts, [0, 2, 6, 14, 30])


if __name__ == '__main__':
    unittest.main()
