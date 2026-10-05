"""Only MAIN/quote transport regressions, full windows and native equivalence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from test_btc15_read_only_revalidation import Evaluator,source,view
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_v2_product_r1 import market,InertProvider,book_for
from btc15_v2_product.bootstrap import Pool
from btc15_v2_product.quote_view import QuoteProjection
from btc15_v2_product.quote_transport import QuoteTransport
from btc15_v2_product.revalidation import Revalidator,apply,agrees,fresh_frame
from btc15_v2_product.journal import ProcessorEnvelope
from btc15_ladder_product_v1 import Directional,iso
from btc15_information_v1 import pack
from ops.btc15_v2_scoring.bridge import ticker

OUT=Path('qualification/narrow_continuity_20261005')

class NarrowContinuity(unittest.TestCase):
    def test_two_complete_contracts_and_rollover(self):
        results=[]
        for age in (.5,1.,2.,4.,4.9):
          for qage in (.1,5.85):
            engines=[ProcessorEnvelope(Directional(),'main') for _ in range(2)]
            for e in engines:e.restore({})
            now=[OPEN];r=Revalidator(Evaluator(),lambda:now[0]);samples=holes=confirmed=boundary_pending=0
            identities=[];native_count=0;old=None
            for contract in range(2):
              opened=OPEN+900*contract
              for n in range(180):
                at=opened+.1+5*n
                f=frame(offset=at-OPEN,sequence=n+1+180*contract,p=.6,ask=.6)
                f.update(official_open=opened,official_close=opened+900,contract=ticker(opened),btc_source=at-4.9,btc_received=at-.1)
                f['quote'].update(ticker=f['contract'],close_ms=int((opened+900)*1000),exchange_ts_ms=max(opened,at-qage)*1000)
                f['brti']['cf_ts']=at-age;f['brti']['delivery']['observed_ts']=at-.06
                now[0]=at+.001
                a,b=[e.process((deepcopy(f),'native'),now[0]) for e in engines]
                self.assertEqual(pack(a),pack(b));v=a[2];native_count+=1
                self.assertNotEqual(v['status'],'UNAVAILABLE',v)
                if n==0:
                    identities.append(v['official_identity'])
                    if old:self.assertIsNone(apply(v,old,now[0]))
                checkpoint=pack(engines[0].processor.checkpoint());original=pack(v)
                for k in range(1,100):
                    now[0]=at+k*.05
                    if now[0]>=opened+900:break
                    s=source(f,now[0],age=min(now[0]-f['brti']['cf_ts'],.5))
                    qt=max(opened,f['quote']['exchange_ts_ms']/1000,now[0]-qage)
                    s['quote'].update(exchange_ts=qt,expires_at=min(opened+900,qt+6))
                    p=r.step(v,s);shown=apply(v,p,now[0]);samples+=1
                    expected=agrees(v,fresh_frame(v,s,Evaluator(),now[0]),now[0])
                    if expected:
                        holes+=shown['status']=='UNAVAILABLE';self.assertEqual(p['status'],'CONFIRMED',p);confirmed+=1
                        self.assertLess(now[0],shown['expires_at'])
                        self.assertLessEqual(shown['expires_at'],min(s['brti']['cf_ts']+5,f['btc_source']+10,qt+6,opened+900))
                        for key in ('native_epoch','native_sequence','published_ts','origin','early','final','context','position_path'):
                            self.assertEqual(shown[key],v[key])
                    else:
                        boundary_pending+=1;self.assertEqual(p['status'],'PENDING')
                        self.assertEqual(shown['status'],'UNAVAILABLE')
                    old=p
                self.assertEqual(checkpoint,pack(engines[0].processor.checkpoint()));self.assertEqual(original,pack(v))
            self.assertEqual(holes,0);self.assertEqual(native_count,360)
            self.assertEqual(engines[0].processor.checkpoint(),engines[1].processor.checkpoint())
            results.append(dict(brti_age=age,quote_age=qage,btc_age=4.9,native_decisions=native_count,
              samples=samples,confirmed=confirmed,false_holes=holes,required_boundary_pending=boundary_pending,
              contracts=identities,native_records_byte_identical=True))
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'full_contract_continuity.json').write_text(json.dumps(dict(status='PASS',results=results),indent=2))

    def test_btc_near_limit_cannot_be_renewed_without_new_causal_source(self):
        f=frame(offset=305,p=.6,ask=.6);f['btc_source']=OPEN+295.11;v=view(f);now=[OPEN+305.05]
        r=Revalidator(Evaluator(),lambda:now[0]);p=r.step(v,source(f,now[0],age=1))
        self.assertEqual(p['status'],'CONFIRMED');self.assertAlmostEqual(p['expires_at'],OPEN+305.11)
        now[0]=OPEN+305.12;self.assertEqual(r.step(v,source(f,now[0]))['status'],'PENDING')
        self.assertEqual(apply(v,p,now[0])['status'],'UNAVAILABLE')

    def test_mixed_route_concurrency_and_500ms_quotes(self):
        from btc15_v2_product import routes
        from btc15_ladder_journal_v1 import atomic_json
        at=[OPEN+300];pool=Pool(InertProvider,lambda:at[0]);pool.select(market(),80000)
        owner=pool.current;book_for(owner,at[0]);projection=QuoteProjection(pool,lambda:at[0])
        calls=[0];busy=[False];entered=threading.Event();release=threading.Event()
        def read():
            calls[0]+=1
            if busy[0]:entered.set();release.wait(2);raise TimeoutError('local transport')
            return projection.capture()
        transport=QuoteTransport(read,lambda:at[0]);transport.capture()
        class Handler:
            def __init__(self,path):self.path=path;self.result=None
            def _send(self,code,kind,body):self.result=(code,json.loads(body))
        count=0
        with tempfile.TemporaryDirectory() as td,patch.dict('os.environ',{'BTC15_LADDER_DATA_ROOT':td}),patch.object(routes,'QUOTES',transport),patch.object(routes.CONFIRMATIONS,'capture',return_value=None):
            atomic_json(Path(td)/'main.json',view(frame(p=.6,ask=.6)))
            with patch('btc15_v2_product.journal.time.time',side_effect=lambda:at[0]):
              for poll in range(12):
                at[0]=OPEN+300+poll*.5;busy[0]=True;release.clear();entered.clear()
                with owner.lock,ThreadPoolExecutor(max_workers=24) as executor:
                    first=executor.submit(transport.capture);self.assertTrue(entered.wait(1))
                    def request(n):
                        path=('/ladders/quotes','/ladders','/information')[n%3];h=Handler(path)
                        handled=routes.serve(h)
                        if path=='/information':self.assertFalse(handled)
                        else:
                            self.assertTrue(handled);self.assertEqual(h.result[0],200)
                            if path=='/ladders/quotes':self.assertEqual(h.result[1]['status'],'AVAILABLE',h.result)
                        return 1
                    count+=sum(executor.map(request,range(144)));release.set();first.result()
                busy[0]=False
            # Real revocation and expiration cannot reuse retained transport history.
            owner.book=None;self.assertEqual(transport.capture()['status'],'UNAVAILABLE')
            book_for(owner,at[0]);self.assertEqual(transport.capture()['status'],'AVAILABLE')
            at[0]+=6;self.assertEqual(transport.capture()['status'],'UNAVAILABLE')
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'quote_concurrency.json').write_text(json.dumps(dict(status='PASS',mixed_route_requests=count,
            owner_lock_held=True,poll_ms=500,concurrent_workers=24,internal_timeouts=12,
            local_reads=calls[0],extra_upstream_polls=0,invalid_quote_fail_closed=True),indent=2))

if __name__=='__main__':unittest.main()
