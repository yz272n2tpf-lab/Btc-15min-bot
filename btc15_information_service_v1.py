"""Separate information inference process and read-only HTTP API. NO ORDERS.

No dashboard, native logs, source-owner writes, persistence or lifecycle API.
The ingress is loopback to the opt-in native bridge, never an upstream feed.
"""
import argparse
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import signal
import threading
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from btc15_information_v1 import (
    FIELD_CLASSES, MAX_BYTES, InformationPublisher, Unavailable, pack, unpack, wait_view,
)

JOURNAL_SCHEMA = 'BTC15_INFORMATION_JOURNAL_V1'
JOURNAL_PATH = Path(os.getenv('BTC15_INFORMATION_JOURNAL_PATH',
                              '/data/btc15_information_frames_v1.jsonl'))
_DIAGNOSTIC_LOCK = threading.Lock()
_DIAGNOSTIC_LAST = {}


def diagnostic(reason, exc=None):
    with _DIAGNOSTIC_LOCK:
        now = time.monotonic()
        if now-_DIAGNOSTIC_LAST.get(reason, -float('inf')) < 30:
            return
        _DIAGNOSTIC_LAST[reason] = now
    print('BTC15 INFORMATION WORKER | '+pack(dict(reason=reason,
          exception_type=type(exc).__name__ if exc else None)).decode(), flush=True)


class DurablePublisher(InformationPublisher):
    """Append exact qualified immutable frames after publication; never strategy authority."""
    def __init__(self, *args, journal_path=JOURNAL_PATH, compress_new=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal_path = Path(journal_path)
        self.compressed_journal = None
        if compress_new:
            from btc15_information_journal_v1 import CompressedJournal
            self.compressed_journal = CompressedJournal(self.journal_path)

    def offer(self, raw, health_reader, clock):
        published = super().offer(raw, health_reader, clock)
        if not published:
            return False
        with self.lock:
            frame_id = self.latest
            saved = self.frames.get(frame_id)
        if not frame_id or saved is None:
            raise RuntimeError('Published frame missing')
        _, encoded = saved
        frame = unpack(encoded)
        record = dict(schema=JOURNAL_SCHEMA, frame_id=frame_id, frame=frame)
        line = pack(record) + b'\n'
        if self.compressed_journal is not None:
            self.compressed_journal.append(line)
            return True
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            remaining = memoryview(line)
            while remaining:
                written = os.write(fd, remaining)
                if not written: raise OSError('Journal short write')
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        return True


class LocalIngress:
    def __init__(self, port=8766):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid native export port')
        self.base = 'http://127.0.0.1:' + str(port)

    def get(self, path):
        try:
            with urlopen(self.base+path, timeout=.8) as response:
                raw = response.read(MAX_BYTES+1)
        except HTTPError as exc:
            if exc.code == 503:
                raise Unavailable('SOURCE_INPUT_UNAVAILABLE') from None
            raise RuntimeError('INGRESS_HTTP_FAILURE') from None
        if len(raw) > MAX_BYTES:
            raise Unavailable('INGRESS_TOO_LARGE')
        return raw

    def capture(self):
        return self.get('/information-input')

    def health(self):
        return unpack(self.get('/information-health'))


class HealthMirror:
    """Display revalidation uses a bounded health lease, never client-driven polls.

    Only the sampler refreshes this snapshot (four reads/sec); observed remains
    the native owner's original timestamp. Outage clears it, slow sampling lets
    its original one-second lease expire. No request can extend that lease.
    """
    def __init__(self, ingress):
        self.ingress = ingress
        self.raw = None
        self.internal_failure = False

    def refresh(self):
        try:
            self.raw = pack(self.ingress.health())
            self.internal_failure = False
        except (Unavailable, OSError, URLError):
            self.raw = None
            self.internal_failure = False
        except Exception as exc:
            self.raw = None
            self.internal_failure = True
            diagnostic('HEALTH_INTERNAL_ERROR', exc)

    def health(self):
        if self.internal_failure: raise RuntimeError('HEALTH_INTERNAL_ERROR')
        raw = self.raw
        if raw is None: raise Unavailable('HEALTH_UNAVAILABLE')
        return unpack(raw)


def step(publisher, ingress, clock=time.time):
    try:
        raw = ingress.capture()
    except (Unavailable, OSError, URLError):
        publisher.unavailable('INPUT_UNAVAILABLE')
        return False
    except Exception as exc:
        diagnostic('INPUT_INTERNAL_ERROR', exc)
        publisher.unavailable('INPUT_INTERNAL_ERROR')
        return False
    def health_reader():
        try:
            return ingress.health()
        except (Unavailable, OSError, URLError):
            # Mark the failing boundary before the publisher's own fail-closed
            # validation catches Unavailable. Never expose exception details.
            raise Unavailable('HEALTH_UNAVAILABLE') from None
    try:
        return publisher.offer(raw, health_reader, clock)
    except Exception as exc:
        diagnostic('PUBLISH_INTERNAL_ERROR', exc)
        publisher.unavailable('PUBLISH_UNAVAILABLE')
        return False


def response(publisher, ingress, path, clock=time.time):
    if path == '/information/schema':
        return 200, pack(dict(schema='BTC15_INFORMATION_FIELD_CLASSES_V1', fields=FIELD_CLASSES,
                              signal_only=True, orders=False))
    frame_id = None
    if path != '/information':
        match = re.fullmatch(r'/information/frame/([0-9a-f]{64})', path)
        if not match:
            return 404, b'{"error":"NOT_FOUND"}'
        frame_id = match[1]
    try:
        health = ingress.health()
    except (Unavailable, OSError, URLError):
        result = wait_view(clock(), 'HEALTH_UNAVAILABLE')
    except Exception as exc:
        diagnostic('HEALTH_INTERNAL_ERROR', exc)
        return 500, b'{"error":"HEALTH_INTERNAL_ERROR"}'
    else:
        try:
            result = publisher.read(health, clock(), frame_id)
        except Unavailable:
            result = wait_view(clock(), 'READ_UNAVAILABLE')
        except Exception as exc:
            diagnostic('READ_INTERNAL_ERROR', exc)
            return 500, b'{"error":"READ_INTERNAL_ERROR"}'
    if result.get('status') == 'WAIT' and result.get('reason') in ('INPUT_INTERNAL_ERROR','PUBLISH_UNAVAILABLE'):
        return 500, pack(dict(error='INFORMATION_INTERNAL_ERROR', reason=result['reason']))
    return 200, pack(result)


def server_for(publisher, ingress, port=0, clock=time.time):
    # Revalidation may wait 200 ms. It must not block independent information
    # requests behind it. Threads are bounded within the existing FD envelope.
    class BoundedHTTPServer(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 16
        def __init__(self, *args):
            self.slots = threading.BoundedSemaphore(8)
            super().__init__(*args)
        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):
                diagnostic('REQUEST_CAPACITY_REACHED')
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, address)
            except Exception:
                self.slots.release()
                raise
        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.slots.release()
    read_lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError, TimeoutError) as exc:
                diagnostic('CLIENT_DISCONNECTED', exc)
        def do_GET(self):
            # Preserve the publisher's read-clock ordering under concurrency.
            with read_lock:
                code, body = response(publisher, ingress, self.path, clock)
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = BoundedHTTPServer(('127.0.0.1', port), Handler)
    original = server.get_request
    def get_request():
        sock, address = original(); sock.settimeout(1.0)
        return sock, address
    server.get_request = get_request
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-port', type=int, default=8766)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    ingress = LocalIngress(args.native_port)
    publisher = DurablePublisher(compress_new=os.getenv('BTC15_INFORMATION_COMPRESS_NEW') == '1')
    mirror = HealthMirror(ingress)
    server = server_for(publisher, mirror, args.port)
    stop = threading.Event()
    def worker():
        while not stop.is_set():
            start = time.monotonic()
            step(publisher, ingress)
            stop.wait(max(.05, .25-(time.monotonic()-start)))
    thread = threading.Thread(target=worker, daemon=True, name='information-inference')
    thread.start()
    def sample_health():
        while not stop.is_set():
            start = time.monotonic()
            mirror.refresh()
            stop.wait(max(.05, .25-(time.monotonic()-start)))
    threading.Thread(target=sample_health, daemon=True, name='information-health').start()
    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        stop.set(); server.server_close()


if __name__ == '__main__':
    main()
