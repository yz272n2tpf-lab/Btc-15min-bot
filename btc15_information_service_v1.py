"""Separate information inference process and read-only HTTP API. NO ORDERS.

No dashboard, native logs, source-owner writes, persistence or lifecycle API.
The ingress is loopback to the opt-in native bridge, never an upstream feed.
"""
import argparse
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import re
import signal
import threading
import time
from urllib.request import urlopen

from btc15_information_v1 import (
    FIELD_CLASSES, MAX_BYTES, InformationPublisher, Unavailable, pack, unpack, wait_view,
)

JOURNAL_SCHEMA = 'BTC15_INFORMATION_JOURNAL_V1'
JOURNAL_PATH = Path(os.getenv('BTC15_INFORMATION_JOURNAL_PATH',
                              '/data/btc15_information_frames_v1.jsonl'))


class DurablePublisher(InformationPublisher):
    """Append exact qualified immutable frames after publication; never strategy authority."""
    def __init__(self, *args, journal_path=JOURNAL_PATH, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal_path = Path(journal_path)

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
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
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
        with urlopen(self.base+path, timeout=.8) as response:
            raw = response.read(MAX_BYTES+1)
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

    def refresh(self):
        try: self.raw = pack(self.ingress.health())
        except Exception: self.raw = None

    def health(self):
        raw = self.raw
        if raw is None: raise Unavailable('HEALTH_UNAVAILABLE')
        return unpack(raw)


def step(publisher, ingress, clock=time.time):
    try:
        return publisher.offer(ingress.capture(), ingress.health, clock)
    except Exception:
        publisher.unavailable('INGRESS_UNAVAILABLE')
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
        result = publisher.read(health, clock(), frame_id)
    except Exception:
        result = wait_view(clock(), 'INGRESS_UNAVAILABLE')
    return 200, pack(result)


def server_for(publisher, ingress, port=0, clock=time.time):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            code, body = response(publisher, ingress, self.path, clock)
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', port), Handler)
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
    publisher = DurablePublisher()
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
