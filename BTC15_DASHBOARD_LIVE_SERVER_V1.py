#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, os, sys
from BTC15_DASHBOARD_STATE_V2 import build_state
ROOT = Path(__file__).resolve().parent
HTML = ROOT / 'BTC_Kalshi_App_Live_v13.html'
PORT = int(os.environ.get('PORT', '8080'))
class Handler(BaseHTTPRequestHandler):
 server_version = 'BTC15Dashboard/1.0'
 def _send(self, code, content_type, body):
 self.send_response(code); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store, max-age=0'); self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(body)
 def do_GET(self):
 path = self.path.split('?',1)[0]
 if path in {'/','/index.html'}:
 if not HTML.exists(): self._send(500,'text/plain; charset=utf-8',b'Dashboard HTML missing'); return
 self._send(200,'text/html; charset=utf-8',HTML.read_bytes()); return
 if path == '/dashboard_state.json':
 try:
 state = build_state(); body = json.dumps(state,separators=(',',':'),allow_nan=False).encode('utf-8'); self._send(200,'application/json; charset=utf-8',body)
 except Exception as e:
 err={'error':type(e).__name__,'message':str(e),'safety':{'read_only':True,'orders_enabled':False}}; self._send(500,'application/json; charset=utf-8',json.dumps(err).encode('utf-8'))
 return
 if path == '/health': self._send(200,'application/json; charset=utf-8',b'{"ok":true,"read_only":true}'); return
 self._send(404,'text/plain; charset=utf-8',b'Not found')
 def log_message(self, fmt, *args): print('DASHBOARD HTTP | '+(fmt % args), flush=True)
def main():
 if '--self-test' in sys.argv:
 if not HTML.exists(): raise SystemExit(f'SELF-TEST FAIL: missing {HTML.name}')
 state=build_state()
 if not state.get('safety',{}).get('read_only'): raise SystemExit('SELF-TEST FAIL: read_only safety flag missing')
 if state.get('safety',{}).get('orders_enabled'): raise SystemExit('SELF-TEST FAIL: orders must remain disabled')
 print('SELF-TEST: PASS'); print('Read-only: YES'); print('Orders enabled: NO'); return 0
 if not HTML.exists(): raise SystemExit(f'STOP: missing {HTML.name}')
 server=ThreadingHTTPServer(('0.0.0.0',PORT),Handler); print(f'BTC15 DASHBOARD LIVE SERVER: STARTING on port {PORT}',flush=True); print('READ-ONLY. NO ORDERS. NO TRADING LOGIC CHANGES.',flush=True)
 try: server.serve_forever(poll_interval=0.5)
 except KeyboardInterrupt: pass
 finally: server.server_close()
 return 0
if __name__ == '__main__': raise SystemExit(main())
