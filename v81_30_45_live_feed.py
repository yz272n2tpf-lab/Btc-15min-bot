#!/usr/bin/env python3
"""HTTP live feed for the graduated V8.1 30-45c scalp lane.

Signal-only. Manual execution only. No orders.

Existing V8.1 numerical entry gates are retained. The committed ladder
processor owns confirmation, origins, recovered protection, EXIT and serial
handoffs. The feed supplies native causal evaluations, never HTTP events.
"""
import json, os, threading, time, sys, math
from copy import deepcopy
from btc15_scalp_journal_v1 import start as start_ladder_journal, offer as journal_offer
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
              'ok':True,'service':'v81-30-45-live-feed','signal_only':True,
              'orders':False,'diagnostic_version':'V81_GATE_DIAG_V1'
            })
        if self.path.startswith('/state'):
            from btc15_ladder_journal_v1 import view
            return self._send(200,view(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v2'),'v81'))
        return self._send(404,{'error':'not_found'})
    def log_message(self,*args): pass

def _r(v,d=4):
    try:
        x=float(v)
        if not math.isfinite(x):
            return None
        return round(x,d)
    except Exception:
        return None

def _diagnose_side(row,side,f):
    ask=row.get(side.lower()+'_ask')
    in_band=ask is not None and .30<=ask<=.45
    out={
      'side':side,'ask':_r(ask),'in_30_45_band':bool(in_band),
      'features_ready':f is not None,'brti_fresh':False,'base_v4':False,
      'structure_ok':False,'route':None,'evidence_ratio':None,
      'confirm_count':0,'reason':'PRICE_OUTSIDE_30_45C',
      'btc5':None,'btc15':None,'btc30':None,'brti5':None,'brti15':None,
      'accel':None,'ask5':None,'ask15':None,
    }
    if not in_band:
        return out
    if f is None:
        out['reason']='FEATURES_NOT_READY'
        return out

    out.update({
      'brti_fresh':bool(_fresh(f)),
      'base_v4':bool(f.get('v4')),
      'structure_ok':bool(f.get('structure_ok')),
      'btc5':_r(f.get('btc5'),2),'btc15':_r(f.get('btc15'),2),
      'btc30':_r(f.get('btc30'),2),'brti5':_r(f.get('brti5'),2),
      'brti15':_r(f.get('brti15'),2),'accel':_r(f.get('accel'),2),
      'ask5':_r(f.get('ask5'),4),'ask15':_r(f.get('ask15'),4),
    })
    route,q=evidence_route(f)
    out['route']=route
    out['evidence_ratio']=_r(q,3)

    if not out['brti_fresh']:
        out['reason']='BRTI_NOT_FRESH'
    elif not out['base_v4']:
        out['reason']='BASE_NOT_READY'
    elif not out['structure_ok']:
        out['reason']='STRUCTURE_BLOCK'
    elif route not in ('CORE','SURGE'):
        out['reason']='EVIDENCE_BELOW_CORE_SURGE'
    else:
        out['reason']='READY_CONFIRMING'
    return out

def _primary_reason(diags):
    inside=[d for d in diags if d.get('in_30_45_band')]
    if not inside:
        return 'NO_SIDE_IN_30_45C'
    inside.sort(key=lambda d:(d.get('evidence_ratio') is not None,d.get('evidence_ratio') or -999),reverse=True)
    d=inside[0]
    return f"{d['side']}:{d['reason']}"

def quality_30_45(row,side,f):
    # LOCKED V8.1 GATE — DO NOT RETUNE.
    ask=row[side.lower()+'_ask']
    if ask is None or ask<.30 or ask>.45:return False,None
    if not _fresh(f):return False,None
    if not f.get('v4') or not f.get('structure_ok'):return False,None
    route,_q=evidence_route(f)
    if route not in ('CORE','SURGE'):return False,None
    return True,route

def loop():
    print('V81 | RECOVERED LIFECYCLE V2 | SIGNAL ONLY | NO ORDERS', flush=True)
    while True:
        t=time.time()
        try:
            row=snap()
            if row is None:
                raise InputUnavailable('SOURCE_UNAVAILABLE')
            hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:
                hist.popleft()
            diagnostics=[];proposals={}
            for side in ('UP','DOWN'):
                f=features(row,side)
                diagnostics.append(_diagnose_side(row,side,f))
                ok,route=quality_30_45(row,side,f) if f else (False,None)
                history={}
                if ok:
                    for seconds in (5,15,30):
                        old=ago(row,seconds)
                        if old is not None:
                            history[str(seconds)]=dict(observed_ts=old['ts'],btc=old['btc'],input_provenance=old['input_provenance'])
                proposals[side]=dict(ok=ok,route=route,features=f,history=history)
            journal_offer(dict(kind='SCALP_DECISION',contract=row['ticker'],row=row,
                captured_ts=time.time(),proposals=proposals,diagnostics=diagnostics))
        except Exception as e:
            reason=str(e) if isinstance(e,InputUnavailable) else 'SOURCE_READ_FAILED'
            journal_offer(dict(kind='UNAVAILABLE',contract=_qualified_inputs.last_ticker,reason=reason))
            if reason!=getattr(loop,'last_wait',None):
                print('V81 SOURCE WAIT | '+reason+' | NO ORDERS',flush=True)
            loop.last_wait=reason
        time.sleep(max(.05,POLL-(time.time()-t)))

def self_test():
    core={'btc5':20.0,'btc15':25.0,'brti5':15.0,'brti15':5.0,'accel':10.0,'btc30':0.0,
          'ask5':0.0,'ask15':0.0,'v4':True,'structure_ok':True}
    weak=dict(core);weak['btc15']=21.0
    row={'ticker':'TEST','ts':1000.0,'left':600.0,'up_ask':.35,'up_bid':.34,'down_ask':.66,'down_bid':.65}
    ok,route=quality_30_45(row,'UP',core)
    assert ok and route=='CORE'
    d=_diagnose_side(row,'UP',core)
    assert d['reason']=='READY_CONFIRMING' and d['in_30_45_band']
    ok2,_=quality_30_45(row,'UP',weak)
    assert not ok2
    d2=_diagnose_side(row,'UP',weak)
    assert d2['reason'] in ('BASE_NOT_READY','EVIDENCE_BELOW_CORE_SURGE')
    d3=_diagnose_side(row,'DOWN',core)
    assert d3['reason']=='PRICE_OUTSIDE_30_45C'
    assert _primary_reason([d,d3]).startswith('UP:')
    payload={'x':_r(float('-inf'))}
    assert payload['x'] is None
    json.dumps(payload,allow_nan=False)
    print('V81 GATE DIAG SELFTEST PASS | LOCKED 30-45 CORE/SURGE GATE UNCHANGED | STRICT JSON | NO ORDERS')
    return 0

def main():
    from btc15_verify_ladder_freeze_v2 import verify
    from pathlib import Path
    verify(Path(__file__).parent,'v81')
    if '--self-test' in sys.argv:
        return self_test()
    port=int(os.getenv('PORT','8080'))
    start_ladder_journal()
    threading.Thread(target=loop,daemon=True).start()
    srv=ThreadingHTTPServer(('0.0.0.0',port),Handler)
    print(f'V81 FEED HTTP | port {port} | GATE DIAG V1',flush=True)
    srv.serve_forever()

if __name__=='__main__': raise SystemExit(main())
