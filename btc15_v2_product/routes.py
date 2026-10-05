"""Read-only public routes; quote GET reads same-provider projection, never a strategy."""
import json
import os
from pathlib import Path
import threading
from urllib.request import urlopen
from .journal import public_view
from btc15_ladder_journal_v1 import coverage_view

from .quote_transport import QuoteTransport
QUOTES=QuoteTransport()
from .revalidation_transport import ConfirmationTransport
CONFIRMATIONS=ConfirmationTransport()

def serve(handler):
    path=handler.path.split('?',1)[0];root=Path(os.environ['BTC15_LADDER_DATA_ROOT'])
    if path=='/ladders':value=public_view(root,'main',confirmation=CONFIRMATIONS.capture)
    elif path=='/ladders/coverage':value=coverage_view(root,'main')
    elif path=='/ladders/panel.js':
        script=(Path(__file__).parent/'panel.js').read_text()
        url=os.getenv('BTC15_V81_LADDERS_URL','https://v81-live-diagnostics-production.up.railway.app/ladders')
        if not url.startswith('https://') or not url.endswith('/ladders'):raise ValueError('SCALP_PUBLIC_URL_INVALID')
        handler._send(200,'application/javascript',script.replace('__V81_LADDERS_URL__',json.dumps(url)).encode());return True
    elif path=='/ladders/quotes':
        value=QUOTES.capture()
    else:return False
    handler._send(200,'application/json',json.dumps(value,allow_nan=False,separators=(',',':')).encode());return True
