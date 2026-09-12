#!/usr/bin/env python3
"""HTTP live feed for the graduated V8.1 30-45c scalp lane.

Signal-only. Manual execution only. No orders. Exposes only the currently active
30-45c CORE/SURGE candidate as JSON for dashboard consumption.
"""
import json, os, threading, time
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
            return self._send(200,{'ok':True,'service':'v81-30-45-live-feed','signal_only':True,'orders':False})
        if self.path.startswith('/state'):
            with STATE_LOCK: payload=dict(STATE)
            return self._send(200,payload)
        return self._send(404,{'error':'not_found'})
    def log_message(self,*args): pass

def publish_wait(contract=None, seconds_left=None):
    now=time.time()
    with STATE_LOCK:
        STATE.update({'active':False,'status':'WAIT','side':None,'route':None,'entry_price':None,'current_bid':None,
          'seconds_left':seconds_left,'contract':contract,'signal_age_sec':None,'targets':None,
          'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now))})

def publish_signal(row, side, route, entry, bid, ts):
    gain=None if bid is None else bid-entry
    if gain is None: status='WATCH'
    elif gain>=.20: status='PROTECT'
    elif gain>=.10: status='ACTIONABLE_EXPANSION'
    elif gain>=.05: status='ACTIONABLE'
    else: status='WATCH'
    now=time.time()
    with STATE_LOCK:
        STATE.update({
          'active':True,'status':status,'side':side,'route':route,'entry_price':round(entry,4),
          'current_bid':None if bid is None else round(bid,4),'seconds_left':round(float(row['left']),1),
          'contract':row['ticker'],'signal_age_sec':round(max(0.0,now-ts),1),
          'targets':{'plus_5c':round(min(1.0,entry+.05),4),'plus_10c':round(min(1.0,entry+.10),4),'plus_20c':round(min(1.0,entry+.20),4)},
          'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
        })

def quality_30_45(row,side,f):
    ask=row[side.lower()+'_ask']
    if ask is None or ask<.30 or ask>.45:return False,None
    if not _fresh(f):return False,None
    if not f.get('v4') or not f.get('structure_ok'):return False,None
    route,_q=evidence_route(f)
    if route not in ('CORE','SURGE'):return False,None
    return True,route

def confirmed(row,side,route,ok):
    k=(row['ticker'],side,route or 'NONE');q=confirm[k];now=row['ts']
    while q and q[0]<now-4.0:q.popleft()
    if not ok:q.clear();return False
    q.append(now);return len(q)>=2

def loop():
    global active
    last_contract=None
    print('V81 LIVE FEED START | 30-45 ONLY | CORE/SURGE | SIGNAL ONLY | NO ORDERS',flush=True)
    while True:
        t=time.time()
        try:
            row=snap()
            if row:
                if last_contract is not None and row['ticker']!=last_contract:
                    active=None; publish_wait(row['ticker'],row['left'])
                last_contract=row['ticker']
                hist.append(row)
                while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()

                if active and active['ticker']==row['ticker']:
                    bid=row[active['side'].lower()+'_bid']
                    publish_signal(row,active['side'],active['route'],active['entry'],bid,active['ts'])
                    if row['left']<=0 or row['ts']-active['ts']>180:
                        active=None; publish_wait(row['ticker'],row['left'])

                if active is None:
                    for side in ('UP','DOWN'):
                        f=features(row,side)
                        if not f: continue
                        ok,route=quality_30_45(row,side,f)
                        if confirmed(row,side,route,ok):
                            ask=row[side.lower()+'_ask']; bid=row[side.lower()+'_bid']
                            k=(row['ticker'],side,'HIGH_30_45')
                            if row['ts']-last_signal.get(k,0)>=20:
                                last_signal[k]=row['ts']
                                active={'ticker':row['ticker'],'side':side,'route':route,'entry':ask,'ts':row['ts']}
                                publish_signal(row,side,route,ask,bid,row['ts'])
                                print('V81 FEED SIGNAL | %s | %s | %s | ask %.3f | left %.0fs'%(row['ticker'],side,route,ask,row['left']),flush=True)
                                break
                if active is None:
                    publish_wait(row['ticker'],row['left'])
        except Exception as e:
            print('V81 FEED WARNING | %s: %s'%(type(e).__name__,e),flush=True)
        time.sleep(max(.05,POLL-(time.time()-t)))

def main():
    port=int(os.getenv('PORT','8080'))
    threading.Thread(target=loop,daemon=True).start()
    srv=ThreadingHTTPServer(('0.0.0.0',port),Handler)
    print(f'V81 FEED HTTP | port {port}',flush=True)
    srv.serve_forever()

if __name__=='__main__': main()
