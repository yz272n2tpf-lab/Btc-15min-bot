"""Retired qualification collector: no feeds, inference, file writes or orders.

Retain the existing Railway service and historical volume. Expose explicit
paused status while its old collector processes are stopped by deployment.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        raw=json.dumps(dict(status='PAUSED',reason='OBSOLETE_QUALIFICATION_COLLECTOR_DISABLED',
                            evidence='EXISTING_VOLUME_PRESERVED',signal_only=True,orders=False)).encode()
        self.send_response(200 if self.path=='/health' else 503)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def log_message(self,*args):pass


if __name__=='__main__':
    if os.environ.get('RAILWAY_SERVICE_ID')!='e6101c69-18df-4522-99d8-94e363ad8b92':
        raise SystemExit('RETIREMENT_RESTRICTED_TO_OBSOLETE_QUALIFICATION_SERVICE')
    print('BTC15 QUALIFICATION PAUSED | historical volume untouched | no source connections | NO ORDERS',flush=True)
    HTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),Handler).serve_forever()
