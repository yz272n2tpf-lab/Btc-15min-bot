"""Network-free tests; compile extracted functions, NEVER import production."""
import ast
import copy
import json
import os
import queue
import sys
import time
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import btc15_rollover_discovery_diag_v2 as d
import apply_btc15_rollover_discovery_diag_v2 as p

UTC = timezone.utc
OPEN = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
PATH = '/trade-api/v2/markets'
PARAMS = {'status': 'open', 'series_ticker': 'KXBTC15M', 'limit': 1000}
TICKER = 'KXBTC15M-26SEP211115-15'
ROW = {'ticker': TICKER, 'open_time': '2026-09-21T15:00:00Z',
       'close_time': '2026-09-21T15:15:00Z'}


def compile_fn(source, response, transport_error=None):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if transport_error:
            raise transport_error
        return response
    env = {'requests': types.SimpleNamespace(get=get), 'KALSHI_BASE_URL': 'https://example.invalid',
           'kalshi_headers': lambda *args: {'signed': 'SENTINEL_NEVER_LOG'}}
    exec(compile(source, '<extracted-kalshi-get>', 'exec'), env)
    return env['kalshi_get'], calls


class Response:
    def __init__(self, data, status_error=None, json_error=None):
        self.data = data
        self.status_error, self.json_error = status_error, json_error
        self.status_code = 503 if status_error else 200
        self.headers = {'cache-control': 'public, max-age=15', 'age': '12',
                        'authorization': 'SENTINEL_NEVER_LOG', 'set-cookie': 'SECRET_COOKIE'}
        self.events = []
    def raise_for_status(self):
        self.events.append('raise_for_status')
        if self.status_error:
            raise self.status_error
    def json(self):
        self.events.append('json')
        if self.json_error:
            raise self.json_error
        return self.data


class DiagTests(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.enqueue = patch.object(d, '_enqueue', side_effect=self.output.append)
        self.enqueue.start()
        self.addCleanup(self.enqueue.stop)
        self.clock = patch.object(d, '_clock', return_value=(OPEN + timedelta(seconds=1), 1000000000))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def context(self):
        return d.begin(PATH, dict(PARAMS))

    def test_original_duplicate_definition_reproduces_missing_logger(self):
        # Pinned continuous-loop binding replaces an earlier same-named definition.
        src = 'def kalshi_get(path, params=None):\n    raise AssertionError("EARLIER LOGGER")\n\n' + p.OLD
        r = Response({'markets': [ROW]})
        fn, calls = compile_fn(src, r)
        self.assertIs(fn(PATH, PARAMS), r.data)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.output, [])

    def test_patch_targets_last_binding_and_preserves_surrounding_source(self):
        prefix = 'def kalshi_get(path, params=None):\n    return "earlier"\n\n'
        suffix = '\n\nPOLL_SECONDS = 5\n'
        src = prefix + p.OLD + suffix
        out = p.replace_last_binding(src)
        self.assertEqual(out, prefix + p.NEW + suffix)

    def test_unexpected_runtime_function_refused(self):
        with self.assertRaises(ValueError):
            p.replace_last_binding('def kalshi_get(path, params=None):\n    return None\n')

    def test_modified_runtime_function_refused(self):
        src = p.OLD + '\n\n' + p.OLD.replace('timeout=10', 'timeout=20') + '\n'
        with self.assertRaises(ValueError):
            p.replace_last_binding(src)

    def test_corrected_runtime_logs_and_preserves_result_identity(self):
        data = {'markets': [dict(ROW)], 'untouched': object()}
        r = Response(data)
        fn, calls = compile_fn(p.NEW, r)
        result = fn(PATH, PARAMS)
        self.assertIs(result, data)
        self.assertIs(calls[0][1]['params'], PARAMS)
        self.assertEqual(r.events, ['raise_for_status', 'json'])
        self.assertEqual([x['event'] for x in self.output],
                         ['REQUEST_STARTED', 'RESPONSE_RECEIVED', 'MARKET_LIST_DECODED'])
        self.assertTrue(self.output[-1]['details']['expected_open_present'])

    def test_original_request_arguments_and_number_preserved(self):
        old, old_calls = compile_fn(p.OLD, Response({'markets': []}))
        new, new_calls = compile_fn(p.NEW, Response({'markets': []}))
        old(PATH, PARAMS); new(PATH, PARAMS)
        self.assertEqual(old_calls, new_calls)
        self.assertEqual(len(new_calls), 1)
        self.assertEqual(new_calls[0][1]['timeout'], 10)

    def test_transport_exception_identity_preserved(self):
        error = TimeoutError('transport failure secret must not be logged')
        fn, calls = compile_fn(p.NEW, None, error)
        with self.assertRaises(TimeoutError) as raised:
            fn(PATH, PARAMS)
        self.assertIs(raised.exception, error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.output[-1]['details']['phase'], 'transport')
        self.assertNotIn('transport failure secret', json.dumps(self.output))

    def test_http_error_logged_before_same_exception_reraised(self):
        error = RuntimeError('bad status')
        response = Response(None, status_error=error)
        fn, _ = compile_fn(p.NEW, response)
        with self.assertRaises(RuntimeError) as raised:
            fn(PATH, PARAMS)
        self.assertIs(raised.exception, error)
        self.assertEqual(response.events, ['raise_for_status'])
        self.assertEqual(self.output[1]['details']['http_status'], 503)
        self.assertEqual(self.output[-1]['details']['phase'], 'http_status')

    def test_json_error_logged_without_second_decode(self):
        error = ValueError('decode failure')
        response = Response(None, json_error=error)
        fn, _ = compile_fn(p.NEW, response)
        with self.assertRaises(ValueError) as raised:
            fn(PATH, PARAMS)
        self.assertIs(raised.exception, error)
        self.assertEqual(response.events, ['raise_for_status', 'json'])
        self.assertEqual(self.output[-1]['details']['phase'], 'json_decode')

    def test_broken_diagnostic_entry_does_not_break_request(self):
        r = Response({'markets': []}); fn, _ = compile_fn(p.NEW, r)
        with patch.object(d, 'begin', side_effect=RuntimeError):
            self.assertIs(fn(PATH, PARAMS), r.data)

    def test_broken_diagnostic_receipt_does_not_break_request(self):
        r = Response({'markets': []}); fn, _ = compile_fn(p.NEW, r)
        with patch.object(d, 'response', side_effect=RuntimeError):
            self.assertIs(fn(PATH, PARAMS), r.data)

    def test_broken_diagnostic_body_does_not_break_request(self):
        r = Response({'markets': []}); fn, _ = compile_fn(p.NEW, r)
        with patch.object(d, 'decoded', side_effect=RuntimeError):
            self.assertIs(fn(PATH, PARAMS), r.data)

    def test_missing_helper_does_not_break_request(self):
        r = Response({'markets': []}); fn, _ = compile_fn(p.NEW, r)
        with patch.dict(sys.modules, {'btc15_rollover_discovery_diag_v2': None}):
            self.assertIs(fn(PATH, PARAMS), r.data)

    def test_diagnostic_failure_does_not_mask_original_failure(self):
        error = ValueError('original')
        fn, _ = compile_fn(p.NEW, Response(None, json_error=error))
        with patch.object(d, 'failed', side_effect=RuntimeError):
            with self.assertRaises(ValueError) as raised:
                fn(PATH, PARAMS)
            self.assertIs(raised.exception, error)

    def test_successful_empty_list_is_absent_not_error(self):
        d.decoded(self.context(), {'markets': []})
        self.assertIs(self.output[-1]['details']['expected_open_present'], False)

    def test_malformed_payload_is_unknown_not_false_absence(self):
        for data in ({}, None, {'markets': [None]}, {'markets': [{'ticker': 'bad'}]}):
            d.decoded(self.context(), data)
            self.assertIsNone(self.output[-1]['details']['expected_open_present'])

    def test_naive_dates_unknown(self):
        row = dict(ROW, open_time='2026-09-21T15:00:00')
        d.decoded(self.context(), {'markets': [row]})
        self.assertIsNone(self.output[-1]['details']['expected_open_present'])

    def test_present_despite_other_malformed_rows(self):
        d.decoded(self.context(), {'markets': [ROW, None]})
        self.assertIs(self.output[-1]['details']['expected_open_present'], True)
        self.assertEqual(self.output[-1]['details']['unresolved_metadata_rows'], 1)

    def test_prior_ticker_not_mislabeled_as_new(self):
        row = dict(ROW, open_time='2026-09-21T14:45:00Z', close_time='2026-09-21T15:00:00Z')
        d.decoded(self.context(), {'markets': [row]})
        self.assertIs(self.output[-1]['details']['expected_open_present'], False)

    def test_original_payload_unmodified_and_only_metadata_emitted(self):
        data = {'markets': [dict(ROW, result='SECRET_RESULT', floor_strike=80000,
                                 title='SECRET_TITLE', private_key='SECRET_KEY')]}
        before = copy.deepcopy(data)
        d.decoded(self.context(), data)
        self.assertEqual(before, data)
        text = json.dumps(self.output)
        for term in ('SECRET_RESULT', 'SECRET_TITLE', 'SECRET_KEY', '80000'):
            self.assertNotIn(term, text)

    def test_headers_allowlisted_and_bounded(self):
        ctx = self.context(); r = Response({})
        r.headers['etag'] = 'a' * 2000
        d.response(ctx, r)
        text = json.dumps(self.output)
        self.assertNotIn('SENTINEL_NEVER_LOG', text)
        self.assertNotIn('SECRET_COOKIE', text)
        headers = self.output[-1]['details']['safe_cache_headers']
        self.assertEqual(headers['age'], '12')
        self.assertEqual(len(headers['etag']), 256)

    def test_monotonic_duration_not_wall_clock(self):
        ctx = self.context()
        with patch.object(d, '_clock', return_value=(OPEN - timedelta(seconds=30), 1123000000)):
            d.response(ctx, Response({}))
        self.assertEqual(self.output[-1]['details']['latency_ms_monotonic'], 123.0)

    def test_preopen_boundary(self):
        with patch.object(d, '_clock', return_value=(OPEN - timedelta(seconds=2), 1)):
            ctx = self.context()
        self.assertEqual(ctx['boundary'], OPEN)
        self.assertEqual(self.output[-1]['ms_from_open'], -2000)

    def test_midcontract_no_events(self):
        with patch.object(d, '_clock', return_value=(OPEN + timedelta(seconds=300), 1)):
            ctx = self.context()
            d.response(ctx, Response({'markets': []}))
            d.decoded(ctx, {'markets': []})
        self.assertEqual(self.output, [])

    def test_slow_request_crossing_into_opening_window_is_captured(self):
        with patch.object(d, '_clock', return_value=(OPEN - timedelta(seconds=8), 1)):
            ctx = self.context()
        self.assertEqual(self.output, [])
        d.response(ctx, Response({'markets': [ROW]}))
        d.decoded(ctx, {'markets': [ROW]})
        self.assertEqual(self.output[0]['ms_from_open'], -8000)
        self.assertTrue(self.output[0]['details']['recorded_after_response'])
        self.assertTrue(self.output[-1]['details']['expected_open_present'])

    def test_other_endpoints_do_not_log(self):
        self.assertIsNone(d.begin('/something-else', PARAMS))
        self.assertIsNone(d.begin(PATH, {'series_ticker': 'OTHER'}))
        self.assertEqual(self.output, [])

    def test_no_order_paths_or_network_client_in_helper(self):
        tree = ast.parse(Path(d.__file__).read_text())
        imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]
        self.assertNotIn('requests', imports)
        self.assertNotIn('socket', imports)
        for event in [self.context()] + self.output:
            if 'orders' in event:
                self.assertFalse(event['orders'])


class QueueTests(unittest.TestCase):
    def test_full_queue_drops_without_waiting(self):
        small = queue.Queue(maxsize=1); small.put({'existing': True})
        worker = types.SimpleNamespace(is_alive=lambda: True)
        with patch.object(d, '_QUEUE', small), patch.object(d, '_WORKER', worker):
            before = d._DROPPED
            start = time.perf_counter()
            for _ in range(1000):
                d._enqueue({})
            elapsed = time.perf_counter() - start
            self.assertEqual(d._DROPPED - before, 1000)
            self.assertEqual(small.qsize(), 1)
            self.assertLess(elapsed, 1.0)

    def test_slow_writer_is_not_called_by_producer(self):
        worker = types.SimpleNamespace(is_alive=lambda: True)
        small = queue.Queue(maxsize=10)
        with patch.object(d, '_QUEUE', small), patch.object(d, '_WORKER', worker), patch('builtins.print') as printer:
            d._enqueue({'test': True})
            printer.assert_not_called()
            self.assertEqual(small.qsize(), 1)


class FullSourceGate(unittest.TestCase):
    @unittest.skipUnless(Path(p.MAIN).is_file(), 'full repository checkout required')
    def test_exact_repo_source_and_only_last_binding_changed(self):
        raw = Path(p.MAIN).read_bytes()
        self.assertEqual(p.blob_sha(raw), p.EXPECTED_BLOB)
        source = raw.decode()
        self.assertEqual(len([n for n in ast.parse(source).body
                              if isinstance(n, ast.FunctionDef) and n.name == 'kalshi_get']), 2)
        changed = p.replace_last_binding(source)
        before_nodes, after_nodes = ast.parse(source).body, ast.parse(changed).body
        self.assertEqual(len(before_nodes), len(after_nodes))
        altered = [i for i, (a, b) in enumerate(zip(before_nodes, after_nodes))
                   if ast.dump(a) != ast.dump(b)]
        expected = [i for i, n in enumerate(before_nodes) if isinstance(n, ast.FunctionDef)
                    and n.name == 'kalshi_get'][-1]
        self.assertEqual(altered, [expected])
        compile(changed, p.MAIN, 'exec')


if __name__ == '__main__':
    if os.getenv('BTC15_REQUIRE_FULL_SOURCE') == '1' and not Path(p.MAIN).is_file():
        raise SystemExit('FAIL: full source required, not found')
    unittest.main()
