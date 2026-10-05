"""Run exact isolated worker + assembled HTTP handler + real browser, synthetic feeds.

No provider credentials, upstream requests, deployment or real-volume writes.
"""
import ast
from contextlib import ExitStack
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from btc15_v2_product.journal import RevisionWorker,RevisionJournal,public_view,ADMINS
from btc15_v2_product.admin import Admin
from btc15_v2_product.installer import assemble
from btc15_information_v1 import FairAssessment
from btc15_ladder_product_v1 import Directional
from btc15_scalp_journal_v1 import Scalp
import btc15_ladder_journal_v1 as frozen
from test_btc15_read_only_revalidation import source
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_scalp_journal_v1 import state
from test_btc15_v2_product_r1 import shifted

OUT=ROOT/'qualification/v2_product_20261004'


def run():
    with ExitStack() as scope:
        # Real elapsed seconds, fixed UTC placement away from genuine strategy
        # time-gate boundaries. Both OS processes share this fixture clock.
        mono=time.monotonic();base=OPEN+305.5
        scope.enter_context(patch('time.time',side_effect=lambda:base+time.monotonic()-mono))
        root=Path(scope.enter_context(tempfile.TemporaryDirectory()));generated=assemble(root/'dashboard')
        sys.path.insert(0,str(generated))
        scope.enter_context(patch.dict(os.environ,BTC15_LADDER_DATA_ROOT=str(root),BTC15_V81_LADDERS_URL='https://fixture-v81.test/ladders'))
        scope.enter_context(patch.object(frozen,'Journal',RevisionJournal))
        admins={lane:Admin(root,lane,clock=lambda:time.time()) for lane in ('main','v81')}
        scope.enter_context(patch.dict(ADMINS,admins,clear=True))
        workers={lane:RevisionWorker(root,lane,cls(),clock=lambda:time.time()) for lane,cls in [('main',Directional),('v81',Scalp)]}
        model=FairAssessment();latest=[None];stop=threading.Event();errors=[]
        def owner_source():
            f=latest[0]
            if f is None:raise ValueError('STARTING')
            now=time.time();s=source(f,now,age=now-max(f['brti']['cf_ts'],math.floor(now)-2))
            return s
        class Native(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    s=owner_source()
                    if self.path=='/revalidation-input':body=s
                    elif self.path=='/executable-quote':
                        from btc15_v2_product import REVISION
                        body=dict(s['quote'],schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,
                            authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False)
                    else:self.send_error(503);return
                    raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)))
                    self.end_headers();self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception:self.send_error(503)
            def log_message(self,*a):pass
        tree=ast.parse((generated/'BTC15_DASHBOARD_LIVE_SERVER_V1.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Handler')
        ns=dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler,json=json,os=os,
            HTML=generated/'BTC_Kalshi_App_Live_v13.html',build_state=lambda **kw:{})
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'<assembled-handler>','exec'),ns)
        class Dashboard(ns['Handler']):
            def do_GET(self):
                if self.path=='/fixture-v81':
                    self._send(200,'application/json',json.dumps(public_view(root,'v81')).encode());return
                return super().do_GET()
            def log_message(self,*a):pass
        servers=[ThreadingHTTPServer(('127.0.0.1',8766),Native),ThreadingHTTPServer(('127.0.0.1',0),Dashboard)]
        for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
        def native_loop():
            sequence=0
            try:
                while not stop.is_set():
                    started=time.monotonic();now=time.time();opened=math.floor(now/900)*900;sequence+=1
                    f=shifted(frame(offset=now-opened,sequence=sequence,p=.6,ask=.7),int(opened-OPEN))
                    f['brti']['cf_ts']=now-4.9
                    s=source(f,now,age=2)
                    # Causal synthetic completed history; exact frozen fitted
                    # model computes the native value AND read-only confirmations.
                    rows=[]
                    for i,t in enumerate(range(int(opened-360),int(f['feature_cutoff']//60)*60+1,60)):
                        price=80000+5*i+(-1)**i*2
                        rows.append([t,t,price,price+2,price-2,price,1.])
                    s['anchor']['completed']=rows[-32:]
                    assessment=model.evaluate(dict(anchor=s['anchor'],cut=f['feature_cutoff'],brti=dict(value=f['brti']['value'])),f['quote']['quotes'])
                    up=assessment['probability_up'];side='UP' if up>=.5 else 'DOWN';p=max(up,1-up);ask=f[side.lower()+'_ask']
                    f['fair']=dict(up_fair=up,down_fair=1-up,side=side,fair=p,ask=ask,edge=p-ask,dist_over_range5=assessment['dist_over_range5'])
                    f['_completed']=rows[-32:]
                    # Source fixture retains this exact native history until
                    # the next five-second tick, just like NativeExport.
                    latest[0]=f
                    admins['main'].begin();assert workers['main'].offer(f);admins['main'].finish()
                    workers['main'].queue.join()
                    # V81 is exercised on its original one-second fixture cadence.
                    for j in range(5):
                        at=time.time();opened2=math.floor(at/900)*900
                        sf=shifted(state(OPEN+at-opened2,.34,sequence*5+j,eligible=False),int(opened2-OPEN))
                        admins['v81'].begin();assert workers['v81'].offer(sf);admins['v81'].finish()
                        workers['v81'].queue.join()
                        sv=json.loads((root/'v81.json').read_text())
                        if sv['status']=='UNAVAILABLE':raise ValueError('V81_FIXTURE:'+str(sv.get('reason')))
                        if stop.wait(max(0,started+j+1-time.monotonic())):break
            except Exception as exc:errors.append(repr(exc));stop.set()
        original_source=owner_source
        def owner_source():
            s=original_source();s['anchor']['completed']=latest[0]['_completed'];return s
        thread=threading.Thread(target=native_loop,daemon=True);thread.start()
        env={k:v for k,v in os.environ.items() if not k.startswith(('KALSHI_','BTC15_BRTI_'))}
        env.update(PYTHONPATH=str(ROOT),BTC15_INFORMATION_JOURNAL_PATH=str(root/'information.jsonl'))
        env.update(BTC15_FIXTURE_MONOTONIC=str(mono),BTC15_FIXTURE_UTC=str(base))
        log=(OUT/'assembled_worker.log').open('w')
        launch="import os,time,runpy; origin=float(os.environ['BTC15_FIXTURE_MONOTONIC']); base=float(os.environ['BTC15_FIXTURE_UTC']); time.time=lambda:base+time.monotonic()-origin; runpy.run_path('btc15_v2_product/worker.py',run_name='__main__')"
        proc=subprocess.Popen([sys.executable,'-u','-c',launch],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            result=subprocess.run(['node','ops/v2_product/test_live_fixture.cjs','http://127.0.0.1:'+str(servers[1].server_port),str(OUT/'assembled_continuity.json')],cwd=ROOT,timeout=40)
            assert not errors,errors
            assert result.returncode==0,'Assembled browser continuity failed'
            for w in workers.values():w.queue.join();assert w.failed is None and w.dropped==0
            report=json.loads((OUT/'assembled_continuity.json').read_text())
            report['native_journals']={lane:dict(written=w.written,drops=w.dropped) for lane,w in workers.items()}
            report['read_only_worker_exit_before_stop']=proc.poll()
            assert proc.poll() is None
            (OUT/'assembled_continuity.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            stop.set();proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close();thread.join(timeout=2)
            for server in servers:server.shutdown();server.server_close()


if __name__=='__main__':run()
