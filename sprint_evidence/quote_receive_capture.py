"""Optional observation of the ORIGINAL websocket receive; no new subscription.

Records original text/bytes and a conservative local call bracket.  This is a
candidate composition seam, not an installed producer or a clock certificate.
The bracket includes any blocking receive time; parse/arrival time is not source
time and a captured message is not evidence that the native Book accepted it.
"""
import ast
import base64
import time

from .passive_capture import digest

SOURCE_SHA256 = '758e172fd5b6c31472a828676d7b00ab284438de95029a2d5f9c1c2efc06f247'
SCHEMA = 'BTC15_QUOTE_RECEIVE_OBSERVATION_V1'
MAX_RAW_BYTES = 96000


class QuoteReceiveCapture:
    def __init__(self, producer, *, time_namespace_id, clock=None):
        if producer.identity.source_sha256 != SOURCE_SHA256:
            raise ValueError('QUOTE_SOURCE_BINDING')
        if not isinstance(time_namespace_id, str) or not time_namespace_id:
            raise ValueError('ACTUAL_TIME_NAMESPACE_REQUIRED')
        self.producer = producer
        self.time_namespace_id = time_namespace_id
        self.clock = clock or (lambda: time.clock_gettime_ns(time.CLOCK_BOOTTIME))

    def _read(self):
        try:
            result = self.clock()
            return result if type(result) is int and result >= 0 else None
        except Exception:
            return None

    def _emit(self, raw, error, before, after, ticker, epoch):
        sequence_before = self.producer.sequence
        dropped_before = self.producer.dropped
        try:
            body = dict(schema=SCHEMA, ticker=ticker, connection_epoch=epoch,
                        time_namespace_id=self.time_namespace_id,
                        recv_call_before_boot_ns=before,
                        recv_return_after_boot_ns=after,
                        bracket_available=(before is not None and after is not None and before <= after),
                        source_timestamp=None, native_book_accepted=None,
                        source_clock_qualified=False, raw_base64=None,
                        raw_sha256=None, raw_bytes=None, raw_type=None,
                        status='RECEIVE_ERROR' if error else 'OBSERVED',
                        error_type=error, guidance=None, manual_fill=None)
            if error is None:
                if type(raw) is str:
                    # Bound allocation before encoding; original object is returned intact.
                    data = raw.encode('utf-8') if len(raw) <= MAX_RAW_BYTES else None
                    body['raw_type'] = 'str'
                elif type(raw) is bytes:
                    data = raw if len(raw) <= MAX_RAW_BYTES else None
                    body['raw_type'] = 'bytes'
                else:
                    data = None
                    body['status'] = 'UNAVAILABLE_RAW_TYPE'
                if data is None or len(data) > MAX_RAW_BYTES:
                    if body['status'] == 'OBSERVED':
                        body['status'] = 'UNAVAILABLE_OVERSIZE'
                else:
                    body.update(raw_base64=base64.b64encode(data).decode('ascii'),
                                raw_sha256=digest(data), raw_bytes=len(data))
            self.producer.lifecycle(body)
        except Exception:
            # Observer failure cannot alter the return/exception of the original recv.
            # Preserve a detectable missing sequence even when failure preceded offer.
            if self.producer.sequence == sequence_before:
                self.producer.sequence += 1
                self.producer.offered += 1
            if self.producer.dropped == dropped_before:
                self.producer.dropped += 1
            self.producer.last_error = 'QUOTE_CAPTURE_FAILED'
            return False

    def recv(self, ws, ticker, epoch, *args, **kwargs):
        before = self._read()
        try:
            raw = ws.recv(*args, **kwargs)
        except Exception as exc:
            after = self._read()
            self._emit(None, type(exc).__name__, before, after, ticker, epoch)
            raise
        after = self._read()
        self._emit(raw, None, before, after, ticker, epoch)
        return raw


def instrument(source, *, enabled=True):
    """Replace just the existing recv call, preserving every caller statement."""
    if digest(source) != SOURCE_SHA256:
        raise ValueError('QUOTE_SOURCE_CHANGED')
    tree = ast.parse(source)
    if not enabled:
        return tree
    providers = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Provider']
    sessions = [n for n in providers[0].body if isinstance(n, ast.FunctionDef) and n.name == 'session'] if len(providers) == 1 else []
    if len(sessions) != 1:
        raise ValueError('QUOTE_SESSION_SEAM')

    class ReplaceRecv(ast.NodeTransformer):
        count = 0

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Attribute) and node.func.attr == 'recv'
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'ws'):
                self.count += 1
                return ast.copy_location(ast.Call(
                    func=ast.Attribute(value=ast.Name(id='_ground_quote', ctx=ast.Load()), attr='recv', ctx=ast.Load()),
                    args=[ast.Name(id=n, ctx=ast.Load()) for n in ('ws', 'ticker', 'epoch')] + node.args,
                    keywords=node.keywords), node)
            return self.generic_visit(node)

    transform = ReplaceRecv()
    transform.visit(sessions[0])
    if transform.count != 1:
        raise ValueError('QUOTE_RECV_SEAM')
    return ast.fix_missing_locations(tree)


def strictly_after_publication(quote, publication):
    """Only verified same-domain disjoint brackets can establish local order.

    The caller must supply genuine producer identities. Independent run counters,
    receiver timestamps, and exchange timestamps are intentionally not compared.
    This predicate alone proves neither freshness nor continuous book coverage.
    """
    required = ('boot_id', 'time_namespace_id', 'clock_domain', 'ticker', 'connection_epoch')
    for key in required:
        if not quote.get(key) or quote.get(key) != publication.get(key):
            return False
    start = quote.get('recv_call_before_boot_ns')
    end = quote.get('recv_return_after_boot_ns')
    pub_start = publication.get('publication_before_boot_ns')
    pub_end = publication.get('publication_after_boot_ns')
    if not all(type(x) is int and x >= 0 for x in (start, end, pub_start, pub_end)):
        return False
    return pub_start <= pub_end < start <= end
