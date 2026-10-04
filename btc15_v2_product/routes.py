"""Read-only public routes; quote GET reads same-provider projection, never a strategy."""
import json
import os
from pathlib import Path
import threading
from urllib.request import urlopen
from .journal import public_view
from btc15_ladder_journal_v1 import coverage_view

SLOTS=threading.BoundedSemaphore(2)

def serve(handler):
    path=handler.path.split('?',1)[0];root=Path(os.environ['BTC15_LADDER_DATA_ROOT'])
    if path=='/ladders':value=public_view(root,'main')
    elif path=='/ladders/coverage':value=coverage_view(root,'main')
    elif path=='/ladders/panel.js':
        script=(Path(__file__).parent/'panel.js').read_text()
        url=os.getenv('BTC15_V81_LADDERS_URL','https://v81-live-diagnostics-production.up.railway.app/ladders')
        if not url.startswith('https://') or not url.endswith('/ladders'):raise ValueError('SCALP_PUBLIC_URL_INVALID')
        handler._send(200,'application/javascript',script.replace('__V81_LADDERS_URL__',json.dumps(url)).encode());return True
    elif path=='/ladders/quotes':
        if not SLOTS.acquire(blocking=False):handler._send(503,'application/json',b'{"status":"UNAVAILABLE"}');return True
        try:
            with urlopen('http://127.0.0.1:8766/executable-quote',timeout=.4) as response:raw=response.read(8193)
            if len(raw)>8192:raise ValueError('OVERSIZE_QUOTE')
            value=json.loads(raw)
        except Exception:value=dict(status='UNAVAILABLE',reason='QUOTE_PROJECTION_UNAVAILABLE')
        finally:SLOTS.release()
    else:return False
    handler._send(200,'application/json',json.dumps(value,allow_nan=False,separators=(',',':')).encode());return True
