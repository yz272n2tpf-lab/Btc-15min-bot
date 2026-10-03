"""Read-only public product state; reads only the small committed JSON snapshot."""
from pathlib import Path
import json
import os
import time
from btc15_ladder_journal_v1 import view, coverage_view

ROOT=Path(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v2'))


def serve(handler):
    path=handler.path.split('?',1)[0]
    if path=='/ladders/coverage':
        handler._send(200,'application/json',json.dumps(coverage_view(ROOT,'main'),separators=(',',':')).encode())
        return True
    if path=='/ladders':
        body=json.dumps(view(ROOT,'main'),separators=(',',':'),allow_nan=False).encode()
        handler._send(200,'application/json',body)
        return True
    if path=='/ladders/panel.js':
        script=(Path(__file__).parent/'btc15_ladder_panel_v1.js').read_text()
        url=os.getenv('BTC15_V81_LADDERS_URL','https://v81-live-diagnostics-production.up.railway.app/ladders')
        if not url.startswith('https://') or not url.endswith('/ladders'):raise ValueError('SCALP_PUBLIC_URL_INVALID')
        handler._send(200,'application/javascript',script.replace('__V81_LADDERS_URL__',json.dumps(url)).encode())
        return True
    return False
