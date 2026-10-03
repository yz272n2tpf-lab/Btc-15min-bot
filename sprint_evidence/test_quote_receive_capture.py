import ast
import base64
import json
import threading
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from sprint_evidence.passive_capture import Identity, Producer
from sprint_evidence.quote_receive_capture import (
    QuoteReceiveCapture, instrument, SOURCE_SHA256, MAX_RAW_BYTES,
    strictly_after_publication,
)

ROOT = Path(__file__).resolve().parents[1]


class Socket:
    def __init__(self): self.packets = []
    def sendto(self, packet, *args): self.packets.append(packet); return len(packet)
    def close(self): pass


class Websocket:
    def __init__(self, result): self.result = result; self.calls = []
    def recv(self, *a, **k):
        self.calls.append((a, k))
        if isinstance(self.result, Exception): raise self.result
        return self.result


class QuoteCaptureTests(unittest.TestCase):
    def setUp(self):
        self.socket = Socket()
        self.producer = Producer('unused', Identity('synthetic-quote', 'synthetic-build', SOURCE_SHA256,
                                  'synthetic-run', 'synthetic-domain', 'synthetic-boot'), b'q'*32, sock=self.socket)
        ticks = iter((100, 200))
        self.capture = QuoteReceiveCapture(self.producer, time_namespace_id='synthetic-time-ns', clock=lambda: next(ticks))

    def body(self): return json.loads(self.socket.packets[-1])['event']['body']['emission']

    def test_exact_original_receive_once_and_raw_identity(self):
        for raw in ('{"type":"orderbook_delta","msg":{"ts_ms":123}}', b'raw bytes\x00'):
            with self.subTest(raw=raw):
                self.setUp(); ws = Websocket(raw)
                self.assertIs(self.capture.recv(ws, 'A', 'e', timeout=1), raw)
                self.assertEqual(ws.calls, [((), {'timeout': 1})])
                body = self.body()
                self.assertEqual(base64.b64decode(body['raw_base64']), raw.encode() if isinstance(raw, str) else raw)
                self.assertEqual((body['recv_call_before_boot_ns'], body['recv_return_after_boot_ns']), (100, 200))
                self.assertIsNone(body['source_timestamp']); self.assertIsNone(body['native_book_accepted'])
                self.assertFalse(body['source_clock_qualified'])

    def test_original_exception_identity_and_timeout_preserved(self):
        exc = TimeoutError('original timeout'); ws = Websocket(exc)
        with self.assertRaises(TimeoutError) as got: self.capture.recv(ws, 'A', 'e', timeout=1)
        self.assertIs(got.exception, exc); self.assertEqual(len(ws.calls), 1)
        self.assertEqual(self.body()['status'], 'RECEIVE_ERROR')

    def test_observer_failure_does_not_change_return_or_exception(self):
        raw = 'original'
        with patch.object(self.producer, 'lifecycle', side_effect=OSError('full')):
            self.assertIs(self.capture.recv(Websocket(raw), 'A', 'e'), raw)
        self.assertEqual((self.producer.sequence, self.producer.dropped), (1, 1))
        exc = ValueError('native')
        with patch.object(self.producer, 'lifecycle', side_effect=OSError('full')):
            with self.assertRaises(ValueError) as got: self.capture.recv(Websocket(exc), 'A', 'e')
        self.assertIs(got.exception, exc)

    def test_transport_drop_visible_and_no_retry(self):
        with patch.object(self.socket, 'sendto', side_effect=BlockingIOError('queue full')) as send:
            self.assertEqual(self.capture.recv(Websocket('raw'), 'A', 'e'), 'raw')
        self.assertEqual(send.call_count, 1)
        self.assertEqual((self.producer.offered, self.producer.dropped), (1, 1))

    def test_oversize_preserved_to_native_but_evidence_unavailable(self):
        raw = 'x'*(MAX_RAW_BYTES+1)
        self.assertIs(self.capture.recv(Websocket(raw), 'A', 'e'), raw)
        self.assertEqual(self.body()['status'], 'UNAVAILABLE_OVERSIZE')
        self.assertIsNone(self.body()['raw_base64'])

    def test_clock_failure_never_manufactures_bracket(self):
        self.capture.clock = lambda: (_ for _ in ()).throw(OSError('clock'))
        self.assertEqual(self.capture.recv(Websocket('raw'), 'A', 'e'), 'raw')
        self.assertFalse(self.body()['bracket_available'])
        self.assertIsNone(self.body()['recv_return_after_boot_ns'])

    def test_source_pin_and_only_one_call_changed(self):
        raw = (ROOT/'btc15_kalshi_quote_provenance_v1.py').read_bytes()
        original = ast.parse(raw); changed = instrument(raw)
        class Undo(ast.NodeTransformer):
            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == '_ground_quote':
                    return ast.Call(func=ast.Attribute(value=node.args[0], attr='recv', ctx=ast.Load()), args=node.args[3:], keywords=node.keywords)
                return self.generic_visit(node)
        self.assertEqual(ast.dump(original), ast.dump(Undo().visit(changed)))
        self.assertEqual(ast.dump(original), ast.dump(instrument(raw, enabled=False)))
        with self.assertRaises(ValueError): instrument(raw+b'\n')

    def test_overlap_equal_missing_and_other_epoch_fail_closed(self):
        shared = dict(boot_id='boot', time_namespace_id='ns', clock_domain='d', ticker='A', connection_epoch='e')
        publication = dict(shared, publication_before_boot_ns=120, publication_after_boot_ns=150)
        quote = dict(shared, recv_call_before_boot_ns=151, recv_return_after_boot_ns=200)
        self.assertTrue(strictly_after_publication(quote, publication))
        for update in ({'recv_call_before_boot_ns':100}, {'recv_call_before_boot_ns':150}, {'recv_call_before_boot_ns':None},
                       {'connection_epoch':'restart'}, {'ticker':'B'}, {'time_namespace_id':'other'}, {'boot_id':None}):
            self.assertFalse(strictly_after_publication(dict(quote, **update), publication))

    def test_actual_provider_session_off_on_equal_valid_and_bad_streams(self):
        raw = (ROOT/'btc15_kalshi_quote_provenance_v1.py').read_bytes()
        snapshot = dict(type='orderbook_snapshot', sid=1, seq=1,
                        msg=dict(market_ticker='A', market_id='market',
                                 yes_dollars_fp=[['0.30','2']], no_dollars_fp=[['0.60','2']]))
        delta = dict(type='orderbook_delta', sid=1, seq=2,
                     msg=dict(market_ticker='A', market_id='market', side='yes',
                              ts_ms=1000000, price_dollars='0.30', delta_fp='1'))
        gap = deepcopy(delta); gap['seq'] = 4
        bad = deepcopy(delta); bad['msg'].pop('ts_ms')
        wrong = deepcopy(delta); wrong['msg']['market_ticker'] = 'OTHER'
        cases = [[snapshot, delta], [snapshot, delta, delta], [snapshot, gap], [snapshot, bad], [snapshot, wrong]]
        for events in cases:
            results = []
            for enabled in (False, True):
                namespace = {'__name__':'quote_fixture', '__file__':str(ROOT/'btc15_kalshi_quote_provenance_v1.py'),
                             '_ground_quote': self.capture}
                exec(compile(instrument(raw, enabled=enabled), '<quote_fixture>', 'exec'), namespace)
                provider = namespace['Provider'].__new__(namespace['Provider'])
                provider.lock = threading.Lock(); provider.ticker = 'A'; provider.close_ms = 1500000
                provider.book = None; provider.events = []; provider.epoch = None
                class Stream:
                    def __init__(self): self.pending = iter(events); self.sent = []; self.receives = 0
                    def send(self, value): self.sent.append(value)
                    def recv(self, **kwargs):
                        self.receives += 1
                        try: return json.dumps(next(self.pending))
                        except StopIteration: raise RuntimeError('END_OF_FIXTURE')
                stream = Stream()
                with patch('time.time', return_value=1000), patch('time.monotonic', return_value=1000), \
                     patch('uuid.uuid4', return_value='same-epoch'), patch.object(namespace['rollover_diag'], 'emit'):
                    try: provider.session(stream, 'A')
                    except Exception as exc: error = (type(exc).__name__, str(exc))
                book = provider.book
                results.append((error, stream.sent, stream.receives, deepcopy(provider.events),
                                None if book is None else (book.valid, book.seq, book.ts_ms, book.levels)))
            self.assertEqual(results[0], results[1])


if __name__ == '__main__': unittest.main()
