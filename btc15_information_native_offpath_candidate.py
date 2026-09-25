"""Opt-in read-only native export bridge. Does not change the stored PR36 file.

The launcher adds ONE observer call after the successful original try-body.
It never calls consume(), Delivery.accept(), strategy gates or model inference.
Only loopback GET is supported. No output files or native-state writes.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import uuid

from btc15_information_v1 import (
    ARTIFACT, WEIGHTS, BOT, PR36_BLOB, Unavailable, check_anchor,
    identity, iso, pack, unpack, validate,
)


def instrument(tree):
    """Exactly one added observer expression; the original statements survive."""
    tree = deepcopy(tree)
    loops = [node for node in tree.body if isinstance(node, ast.While)
             and isinstance(node.test, ast.Name) and node.test.id == 'running']
    if len(loops) != 1:
        raise RuntimeError('Pinned native loop missing')
    blocks = [node for node in loops[0].body if isinstance(node, ast.Try)]
    if len(blocks) != 1:
        raise RuntimeError('Pinned native try body missing')
    blocks[0].body.append(ast.parse('_btc15_information_offer(globals())').body[0])
    return ast.fix_missing_locations(tree)


class NativeExport:
    def __init__(self, clock=time.time, epoch=None, provider_reader=None):
        self.clock = clock
        self.epoch = epoch or str(uuid.uuid4())
        self.anchor = None  # Tuple of bytes and existing receipt-owner reference.
        self.provider_reader = provider_reader or self._provider
        self.last_offer_error = None

    @staticmethod
    def _provider():
        import btc15_kalshi_quote_provenance_v1 as quotes
        return getattr(quotes, '_provider', None)  # Never create or consume it.

    def offer(self, ns):
        """Called solely by the native loop. Copy a whitelist; all errors private."""
        try:
            at = ns['now_ts']; market = ns['market']; fair = ns['_ec_live']
            if not ns['_fair_ready'] or fair is None or not ns['_unified_rows']:
                raise Unavailable('NATIVE_ASSESSMENT_UNAVAILABLE')
            opened = ns['close_dt'].timestamp()-900
            completed = ns['_fair_btc']
            # At most 22 one-minute rows; no full 35-day copy on the action thread.
            base = completed.loc[(completed.index >= iso(opened-360)) & (completed.index <= iso(at))]
            rows = [[t.timestamp(), row['source_utc'].timestamp(),
                     *[float(row[name]) for name in ('Open','High','Low','Close','Volume')]]
                    for t, row in base.iterrows()]
            a = dict(schema='BTC15_NATIVE_INFORMATION_ANCHOR_V1', epoch=self.epoch,
                     decision=at, captured=self.clock(), ticker=market['ticker'], opened=opened,
                     closed=opened+900, target=float(ns['target']),
                     btc=dict(value=float(ns['btc']), source=ns['_btc_spot_provenance']['source_utc'].timestamp(),
                              received=ns['_btc_spot_provenance']['observed_utc'].timestamp()),
                     completed=rows, ticks=[[s.timestamp(), r.timestamp(), p] for s,r,p in ns['_ec_btc_ticks']],
                     probability_up=float(fair['up_fair']),
                     artifact=ns['_fair_model_artifact_sha256'], weights=ns['_fair_model_weights_sha256'])
            check_anchor(a)
            raw = pack(a)
            # One atomic reference exchange. Readers can retain old bytes safely.
            self.anchor = (raw, ns['_brti_delivery'])
            self.last_offer_error = None
        except Exception:
            self.anchor = None
            self.last_offer_error = 'NATIVE_EXPORT_UNAVAILABLE'

    def _owners(self, selected, with_events=False):
        if selected is None:
            raise Unavailable('NATIVE_ANCHOR_UNAVAILABLE')
        raw, delivery = selected
        a = unpack(raw)
        provider = self.provider_reader()
        if provider is None or not provider.lock.acquire(blocking=False):
            raise Unavailable('QUOTE_OWNER_BUSY_OR_UNAVAILABLE')
        try:
            book = provider.book
            if provider.ticker != a['ticker'] or book is None or not book.valid:
                raise Unavailable('QUOTE_OWNER_WAIT_OR_ROLLOVER')
            proof = dict(ticker=a['ticker'], epoch=provider.epoch,
                         identity=[book.market_id, book.sid, book.seq, book.ts_ms])
            if with_events:
                # Freeze only list membership under the owner lock. The native
                # decision path never serializes or writes the retained proof.
                # Detachment remains on the loopback capture request path.
                proof['events'] = tuple(provider.events)
        finally:
            provider.lock.release()
        if with_events:
            proof['events'] = deepcopy(list(proof['events']))
        if not delivery.lock.acquire(blocking=False):
            raise Unavailable('BRTI_OWNER_BUSY')
        try:
            if not delivery.states or not delivery.statuses or not delivery.statuses[-1][1]:
                raise Unavailable('BRTI_OWNER_UNAVAILABLE')
            point = dict(delivery.states[-1])
            if point['owner_epoch'] != delivery.epoch:
                raise Unavailable('BRTI_OWNER_RESTART')
            status_at = delivery.statuses[-1][0]
        finally:
            delivery.lock.release()
        checked = self.clock()
        if (self.anchor is not selected or status_at > checked
                or not 0 <= checked-point['cf_ts'] <= 5
                or not 0 <= checked-proof['identity'][3]/1000 <= 6):
            raise Unavailable('SOURCE_CHANGED_OR_EXPIRED')
        h = dict(ready=True, observed=checked, native_epoch=a['epoch'], anchor_id=identity(raw),
                 ticker=a['ticker'], brti_epoch=point['owner_epoch'], quote_epoch=proof['epoch'])
        return a, point, proof, h

    def health(self):
        return self._owners(self.anchor)[3]

    def capture(self):
        selected = self.anchor
        a, point, proof, health = self._owners(selected, with_events=True)
        cut = health['observed']
        # This receipt is conservative: all copied quote events existed by cut.
        # Only source sequence/exchange time provide novelty, never this clock.
        proof.update(source_time=iso(cut), consumed_ms=int(cut*1000))
        f = dict(schema='BTC15_INFORMATION_INPUT_V1', anchor=a, anchor_id=identity(selected[0]), cut=cut,
                 brti=dict(value=point['value'], source=point['cf_ts'], received=point['observed_ts'],
                           epoch=point['owner_epoch']), proof=proof, quote_received=cut)
        raw = pack(f)
        validate(raw, self.health(), self.clock())
        return raw


def server_for(export, port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path == '/information-input':
                    body = export.capture()
                elif self.path == '/information-health':
                    body = pack(export.health())
                else:
                    self.send_error(404); return
                code = 200
            except Exception:
                code, body = 503, b'{"status":"WAIT","reason":"INPUT_UNAVAILABLE"}'
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', port), Handler)
    # Do not let a stalled local client hold the only bounded request slot.
    original = server.get_request
    def get_request():
        sock, address = original(); sock.settimeout(1.0)
        return sock, address
    server.get_request = get_request
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if os.getenv('BTC15_ENABLE_INFORMATION_EXPORT') != '1':
        raise SystemExit('Explicit candidate export opt-in required; PR36 remains default')
    raw = BOT.read_bytes()
    if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != PR36_BLOB:
        raise SystemExit('Pinned PR36 byte identity required')
    export = NativeExport()
    server = server_for(export, args.port)
    threading.Thread(target=server.serve_forever, daemon=True, name='information-read-only-export').start()
    namespace = dict(__name__='__main__', __file__=str(BOT), _btc15_information_offer=export.offer)
    try:
        exec(compile(instrument(ast.parse(raw)), str(BOT), 'exec'), namespace)
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
