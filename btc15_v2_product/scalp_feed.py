#!/usr/bin/env python3
"""Generalized serial native feed; current qualified inputs and original cadence.

Both sides / BTC30 >= $15 / new entry >=120s. Price is context only.
SIGNAL ONLY. MANUAL EXECUTION ONLY. NO ORDERS.
"""
import json, os, threading, time, sys, math
from copy import deepcopy
from btc15_v2_product.scalp import start as start_ladder_journal, offer as journal_offer
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict, deque

_src=open('scalp_lead_unified_v8.py','r',encoding='utf-8').read()
_prefix=_src.split("def _self_test_unified_gate():",1)[0]
exec(compile(_prefix,'scalp_lead_unified_v8.py','exec'),globals())
from btc15_v81_qualified_inputs_v1 import (
    QualifiedInputs, InputUnavailable, require_qualified, publication_view,
)

_qualified_inputs = QualifiedInputs(market, target, requests.get, CB)
snap = _qualified_inputs.snapshot

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body=json.dumps(payload,separators=(',',':'),allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == '/ladders/coverage':
            from btc15_ladder_journal_v1 import coverage_view
            return self._send(200,coverage_view(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v2'),'v81'))
        if self.path == '/ladders':
            from btc15_ladder_journal_v1 import view
            return self._send(200,view(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v2'),'v81'))
        if self.path in ('/','/health'):
            return self._send(200,{
              'ok':True,'service':'btc15-generalized-serial-feed','signal_only':True,
              'orders':False,'diagnostic_version':'INTEGRATED_FINISH_20261006'
            })
        if self.path.startswith('/state'):
            from btc15_ladder_journal_v1 import view
            return self._send(200,view(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v2'),'v81'))
        return self._send(404,{'error':'not_found','signal_only':True,'orders':False})
    def log_message(self,*args): pass

def _r(v,d=4):
    try:
        x=float(v)
        if not math.isfinite(x):
            return None
        return round(x,d)
    except Exception:
        return None

def loop():
    print('GENERALIZED SERIAL | ARM5 GIVEBACK4 | SIGNAL ONLY | NO ORDERS', flush=True)
    while True:
        t=time.time()
        try:
            row=snap()
            if row is None:
                raise InputUnavailable('SOURCE_UNAVAILABLE')
            hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:
                hist.popleft()
            from btc15_v2_product.scalp_policy import proposal_for
            old=ago(row,30)
            history={'30':dict(observed_ts=old['ts'],btc=old['btc'],input_provenance=old['input_provenance'])} if old else {}
            proposals={side:proposal_for(row,side,history) for side in ('UP','DOWN')}
            diagnostics=[dict(side=side,reason=proposal['reason']) for side,proposal in proposals.items()]
            journal_offer(dict(kind='SCALP_DECISION',contract=row['ticker'],row=row,
                captured_ts=time.time(),proposals=proposals,diagnostics=diagnostics))
        except Exception as e:
            reason=str(e) if isinstance(e,InputUnavailable) else 'SOURCE_READ_FAILED'
            journal_offer(dict(kind='UNAVAILABLE',contract=_qualified_inputs.last_ticker,reason=reason))
            if reason!=getattr(loop,'last_wait',None):
                print('V81 SOURCE WAIT | '+reason+' | NO ORDERS',flush=True)
            loop.last_wait=reason
        time.sleep(max(.05,POLL-(time.time()-t)))

def main():
    from btc15_verify_ladder_freeze_v2 import verify
    from pathlib import Path
    verify(Path(__file__).resolve().parents[1],'v81')
    if '--self-test' in sys.argv:
        raise SystemExit("Run test_btc15_integrated_finish.py offline")
    port=int(os.getenv('PORT','8080'))
    start_ladder_journal()
    threading.Thread(target=loop,daemon=True).start()
    srv=ThreadingHTTPServer(('0.0.0.0',port),Handler)
    print(f'GENERALIZED SERIAL FEED HTTP | port {port} | SIGNAL ONLY',flush=True)
    srv.serve_forever()

if __name__=='__main__': raise SystemExit(main())
