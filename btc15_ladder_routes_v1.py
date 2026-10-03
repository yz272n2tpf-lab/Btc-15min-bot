"""Read-only public product state; reads only the small committed JSON snapshot."""
from pathlib import Path
import json
import os
import time
from btc15_ladder_journal_v1 import view

ROOT=Path(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v1'))


def serve(handler):
    path=handler.path.split('?',1)[0]
    if path=='/ladders':
        body=json.dumps(view(ROOT,'main'),separators=(',',':'),allow_nan=False).encode()
        handler._send(200,'application/json',body)
        return True
    if path=='/ladders/panel.js':
        handler._send(200,'application/javascript',(Path(__file__).parent/'btc15_ladder_panel_v1.js').read_bytes())
        return True
    return False
