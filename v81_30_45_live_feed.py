#!/usr/bin/env python3
"""HTTP live feed for the graduated V8.1 30-45c scalp lane.

Signal-only. Manual execution only. No orders.

V8.1 gate logic is unchanged. This revision adds diagnostic-only visibility:
- why each 30-45c side is waiting/rejected
- current gate metrics and confirmation count
- persistent last_signal_event metadata so brief signals are not missed

No threshold, route, confirmation, timing, or trading rule is changed.
"""
import json, os, threading, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict, deque

_src=open('scalp_lead_unified_v8.py','r',encoding='utf-8').read()
_prefix=_src.split("def _self_test_unified_gate():",1)[0]
exec(compile(_prefix,'scalp_lead_unified_v8.py','exec'),globals())

STATE_LOCK=threading.Lock()
STATE={
  'version':'V8.1_GRADUATED_30_45','entry_band':'30-45c','graduated':True,
  'manual_execution_only':True,'order_action':None,
  'owns_final_outcome':False,'owns_early_opportunity':False,
  'active':False,'status':'WAIT','side':None,'route':None,'entry_price':None,
  'current_bid':None,'seconds_left':None,'contract':None,'signal_age_sec':None,
  'targets':None,'generated_utc':None,
  'diagnostic_version':'V81_GATE_DIAG_V1','primary_wait_reason':'STARTING',
  'diagnostics':[],'last_signal_event':None,
}

confirm=defaultdict(deque)
last_signal={}
active=None

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body=json.dumps(payload,separators=(',',':')).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path in ('/','/health'):
            return self._send(200,{
              'ok':True,'service':'v81-30-45-live-feed','signal_only':True,
              'orders':False,'diagnostic_version':'V81_GATE_DIAG_V1'
            })
        if self.path.startswith('/state'):
            with STATE_LOCK: payload=dict(STATE)
            return self._send(200,payload)
        return self._send(404,{'error':'not_found'})
    def log_message(self,*args): pass

def _r(v,d=4):
    try:
        x=float(v)
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
    # Prefer the in-band side closest to qualifying evidence.
    inside.sort(key=lambda d:(d.get('evidence_ratio') is not None,d.get('evidence_ratio') or -999),reverse=True)
    d=inside[0]
    return f"{d['side']}:{d['reason']}"

def publish_wait(contract=None, seconds_left=None, diagnostics=None, reason=None):
    now=time.time()
    with STATE_LOCK:
        STATE.update({
          'active':False,'status':'WAIT','side':None,'route':None,'entry_price':None,
          'current_bid':None,'seconds_left':seconds_left,'contract':contract,
          'signal_age_sec':None,'targets':None,
          'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
          'diagnostics':diagnostics or [],
          'primary_wait_reason':reason or _primary_reason(diagnostics or []),
        })

def publish_signal(row, side, route, entry, bid, ts, diagnostics=None):
    gain=None if bid is None else bid-entry
    if gain is None: status='WATCH'
    elif gain>=.20: status='PROTECT'
    elif gain>=.10: status='ACTIONABLE_EXPANSION'
    elif gain>=.05: status='ACTIONABLE'
    else: status='WATCH'
    now=time.time()
    event={
      'contract':row['ticker'],'side':side,'route':route,'entry_price':round(entry,4),
      'signal_timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(ts)),
      'seconds_left_at_signal':round(float(row['left']),1),
    }
    with STATE_LOCK:
        STATE.update({
          'active':True,'status':status,'side':side,'route':route,'entry_price':round(entry,4),
          'current_bid':None if bid is None else round(bid,4),'seconds_left':round(float(row['left']),1),
          'contract':row['ticker'],'signal_age_sec':round(max(0.0,now-ts),1),
          'targets':{'plus_5c':round(min(1.0,entry+.05),4),'plus_10c':round(min(1.0,entry+.10),4),'plus_20c':round(min(1.0,entry+.20),4)},
          'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
          'diagnostics':diagnostics or [],'primary_wait_reason':'ACTIVE_SIGNAL',
          'last_signal_event':event,
        })

def quality_30_45(row,side,f):
    # LOCKED V8.1 GATE — DO NOT RETUNE.
    ask=row[side.lower()+'_ask']
    if ask is None or ask<.30 or ask>.45:return False,None
    if not _fresh(f):return False,None
    if not f.get('v4') or not f.get('structure_ok'):return False,None
    route,_q=evidence_route(f)
    if route not in ('CORE','SURGE'):return False,None
    return True,route

def confirmed(row,side,route,ok):
    # LOCKED confirmation: 2 qualifying observations inside 4 seconds.
    k=(row['ticker'],side,route or 'NONE');q=confirm[k];now=row['ts']
    while q and q[0]<now-4.0:q.popleft()
    if not ok:q.clear();return False
    q.append(now);return len(q)>=2

def loop():
    global active
    last_contract=None
    print('V81 LIVE FEED START | 30-45 ONLY | CORE/SURGE | SIGNAL ONLY | NO ORDERS | GATE DIAG V1',flush=True)
    while True:
        t=time.time()
        try:
            row=snap()
            if row:
                if last_contract is not None and row['ticker']!=last_contract:
                    active=None
                last_contract=row['ticker']
                hist.append(row)
                while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()

                diagnostics=[]
                feature_map={}
                for side in ('UP','DOWN'):
                    f=features(row,side)
                    feature_map[side]=f
                    diagnostics.append(_diagnose_side(row,side,f))

                if active and active['ticker']==row['ticker']:
                    bid=row[active['side'].lower()+'_bid']
                    publish_signal(row,active['side'],active['route'],active['entry'],bid,active['ts'],diagnostics)
                    if row['left']<=0 or row['ts']-active['ts']>180:
                        active=None
                        publish_wait(row['ticker'],row['left'],diagnostics)

                if active is None:
                    for side in ('UP','DOWN'):
                        f=feature_map[side]
                        if not f:
                            continue
                        ok,route=quality_30_45(row,side,f)
                        fired=confirmed(row,side,route,ok)
                        for d in diagnostics:
                            if d['side']==side and d['in_30_45_band']:
                                q=confirm[(row['ticker'],side,route or 'NONE')]
                                d['confirm_count']=len(q)
                                if ok and not fired:
                                    d['reason']=f"CONFIRMING_{len(q)}_OF_2"
                                elif fired:
                                    d['reason']='QUALIFIED'
                        if fired:
                            ask=row[side.lower()+'_ask']; bid=row[side.lower()+'_bid']
                            k=(row['ticker'],side,'HIGH_30_45')
                            if row['ts']-last_signal.get(k,0)>=20:
                                last_signal[k]=row['ts']
                                active={'ticker':row['ticker'],'side':side,'route':route,'entry':ask,'ts':row['ts']}
                                publish_signal(row,side,route,ask,bid,row['ts'],diagnostics)
                                print('V81 FEED SIGNAL | %s | %s | %s | ask %.3f | left %.0fs'%(row['ticker'],side,route,ask,row['left']),flush=True)
                                break
                if active is None:
                    reason=_primary_reason(diagnostics)
                    publish_wait(row['ticker'],row['left'],diagnostics,reason)
                    if int(row['ts'])%30==0:
                        print('V81 GATE DIAG | %s | %s | %s'%(row['ticker'],reason,json.dumps(diagnostics,separators=(',',':'))),flush=True)
        except Exception as e:
            print('V81 FEED WARNING | %s: %s'%(type(e).__name__,e),flush=True)
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
    print('V81 GATE DIAG SELFTEST PASS | LOCKED 30-45 CORE/SURGE GATE UNCHANGED | NO ORDERS')
    return 0

def main():
    if '--self-test' in sys.argv:
        return self_test()
    port=int(os.getenv('PORT','8080'))
    threading.Thread(target=loop,daemon=True).start()
    srv=ThreadingHTTPServer(('0.0.0.0',port),Handler)
    print(f'V81 FEED HTTP | port {port} | GATE DIAG V1',flush=True)
    srv.serve_forever()

if __name__=='__main__': raise SystemExit(main())
