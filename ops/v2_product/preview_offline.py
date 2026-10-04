"""Loopback ONLY fixture preview of the assembled page. No external reads/writes."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'qualification/v2_product_20261004'
FIXTURE=json.loads((OUT/'ui_fixture.json').read_text())
START=time.monotonic()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path=='/':
            body=(OUT/'dashboard/BTC_Kalshi_App_Live_v13.html').read_text().replace('<body>','<body><div style="padding:12px;background:#675000;color:white">OFFLINE FIXTURES · NO LIVE INPUTS · NO ORDERS</div>').encode();kind='text/html'
        elif path=='/ladders/panel.js':
            body=(ROOT/'btc15_v2_product/panel.js').read_text().replace('__V81_LADDERS_URL__',json.dumps('/fixture-v81/ladders')).encode();kind='application/javascript'
        elif path in ('/information/view.js','/information/panel.js'):
            body=(ROOT/('btc15_information_view_v1.js' if path.endswith('view.js') else 'btc15_information_panel_v1.js')).read_bytes();kind='application/javascript'
        else:
            lane={'/ladders':'main','/fixture-v81/ladders':'scalp','/ladders/quotes':'quote'}.get(path)
            data=deepcopy(FIXTURE[lane]) if lane else dict(status='WAIT')
            if lane:
                delta=(time.monotonic()-START)%300
                for k in ('published_ts','served_ts','expires_at','exchange_ts','accepted_ts'):
                    if k in data:data[k]+=delta
            body=json.dumps(data).encode();kind='application/json'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except BrokenPipeError:pass
    def log_message(self,*args):pass

if __name__=='__main__':
    print('Offline fixture preview: http://127.0.0.1:8765/',flush=True)
    HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
