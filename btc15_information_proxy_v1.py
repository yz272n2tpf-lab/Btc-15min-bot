"""Closed, bounded public information route; never touches native cards or logs."""
import json
import math
from pathlib import Path
import re
import threading
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
FIELDS = json.loads((ROOT/'btc15_information_fields_v1.json').read_text())
SLOTS = threading.BoundedSemaphore(2)
RATE_LOCK = threading.Lock()
NEXT = 0.
MAX_BYTES = 16384
ASSETS = {'/information/view.js':'btc15_information_view_v1.js',
          '/information/panel.js':'btc15_information_panel_v1.js'}


def closed(raw, now):
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != set(FIELDS)
            or value.get('authority') != 'INFORMATIONAL_READ_ONLY'
            or value.get('schema') != 'BTC15_INFORMATION_V1'
            or value.get('orders') is not False or value.get('signal_only') is not True):
        raise ValueError('Closed information contract')
    if value['status'] not in ('WAIT', 'AVAILABLE'): raise ValueError('Invalid status')
    if value['status'] == 'WAIT':
        metadata={'schema','authority','status','reason','signal_only','orders','checked_ts'}
        if any(v is not None for k,v in value.items() if k not in metadata):
            raise ValueError('WAIT must redact source values')
    if value['status'] == 'AVAILABLE':
        for key in ('checked_ts','expires_at','display_until','brti_source_ts'):
            if type(value[key]) not in (int,float) or not math.isfinite(value[key]):
                raise ValueError('Invalid clock')
        if not value['brti_source_ts'] <= value['checked_ts'] <= now < min(value['expires_at'],value['display_until']):
            raise ValueError('Transport expiry')
        if now-value['brti_source_ts'] > 5: raise ValueError('BRTI expired')
        # Account for worker->dashboard transport without renewing either deadline.
        value['checked_ts'] = now
        value['brti_age_seconds'] = now-value['brti_source_ts']
    return json.dumps(value,allow_nan=False,separators=(',',':')).encode()


def reply(handler, code, kind, body):
    nonce = handler.headers.get('X-BTC15-Information-Nonce', '') if hasattr(handler,'headers') else ''
    if not nonce:
        handler._send(code, kind, body); return
    if not re.fullmatch('[0-9a-f]{32}', nonce):
        handler._send(400,'application/json',b'{"error":"INVALID_INFORMATION_NONCE"}'); return
    handler.send_response(code)
    for key,value in {'Content-Type':kind,'Content-Length':str(len(body)),
                      'Cache-Control':'no-store, max-age=0','X-Content-Type-Options':'nosniff',
                      'X-BTC15-Information-Nonce':nonce}.items():handler.send_header(key,value)
    handler.end_headers();handler.wfile.write(body)


def serve(handler):
    global NEXT
    path = handler.path
    if not (path == '/information' or path.startswith('/information/') or path.startswith('/information?')):
        return False
    if path in ASSETS:
        handler._send(200,'application/javascript; charset=utf-8',(ROOT/ASSETS[path]).read_bytes()); return True
    if path == '/information/schema':
        body = json.dumps(dict(schema='BTC15_INFORMATION_FIELD_CLASSES_V1',fields=FIELDS,
                               signal_only=True,orders=False)).encode()
        handler._send(200,'application/json',body); return True
    if path != '/information' and not re.fullmatch('/information/frame/[0-9a-f]{64}',path):
        handler._send(404,'application/json',b'{"error":"NOT_FOUND"}'); return True
    with RATE_LOCK:
        now = time.monotonic()
        allowed = now >= NEXT
        if allowed: NEXT = now+.05  # Whole dashboard <=20 information requests/s.
    if not allowed or not SLOTS.acquire(blocking=False):
        handler._send(429,'application/json',b'{"status":"WAIT","error":"INFORMATION_BUSY"}'); return True
    try:
        with urlopen('http://127.0.0.1:8767'+path, timeout=.4) as response:
            raw = response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('Oversize output')
        body=closed(raw,time.time()); status=200
    except Exception:
        status,body=503,b'{"status":"WAIT","error":"INFORMATION_UNAVAILABLE"}'
    finally: SLOTS.release()
    reply(handler,status,'application/json',body); return True
