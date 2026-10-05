"""Acceptance plumbing and pre-repair counterexamples; repaired gate is separate."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from btc15_v2_product.bootstrap import Pool
from btc15_v2_product.quote_view import QuoteProjection
from btc15_v2_product.quote_transport import QuoteTransport
from btc15_v2_product.journal import ProcessorEnvelope,public_view
from btc15_ladder_product_v1 import Directional
from btc15_ladder_journal_v1 import atomic_json
from test_btc15_v2_product_r1 import InertProvider,book_for,market
from test_btc15_ladder_completion_v1 import frame,OPEN

OUT=Path(__file__).parent/'qualification/v2_product_20261004'

def accepted(p,at):
    with patch('btc15_v2_product.bootstrap.time.time',return_value=at):p._accepted_clock(p.book,p.epoch)

class QuoteContinuity(unittest.TestCase):
    def setUp(self):
        self.at=OPEN+300
        self.pool=Pool(InertProvider,lambda:self.at);self.pool.select(market(),80000)
        self.p=self.pool.current;book_for(self.p,self.at);accepted(self.p,self.at)
        self.q=QuoteProjection(self.pool,lambda:self.at)
    def test_concurrent_readers_never_need_busy_provider_lock(self):
        original=self.q.capture()
        with self.p.lock,ThreadPoolExecutor(max_workers=32) as threads:
            values=list(threads.map(lambda _:self.q.capture(),range(512)))
        self.assertTrue(all(v==original for v in values))
        self.assertEqual(original['status'],'AVAILABLE')
    def test_500ms_polls_on_real_accepted_book_never_renew_source_lease(self):
        first=self.q.capture()
        with self.p.lock:
            for n in range(1,12):
                self.at=OPEN+300+n*.5
                current=self.q.capture();self.assertEqual(current['status'],'AVAILABLE')
                for field in ('epoch','sequence','exchange_ts','accepted_ts','published_ts','expires_at'):
                    self.assertEqual(current[field],first[field])
            self.at=first['expires_at'];self.assertEqual(self.q.capture()['status'],'UNAVAILABLE')
    def test_same_owner_disconnect_and_invalid_book_revoke_before_expiry(self):
        self.p.book=None
        self.assertEqual(self.q.capture()['status'],'UNAVAILABLE')
        book_for(self.p,self.at);accepted(self.p,self.at)
        self.assertEqual(self.q.capture()['status'],'AVAILABLE')
        self.p.book.levels['no'].clear();accepted(self.p,self.at)
        self.assertEqual(self.q.capture()['status'],'UNAVAILABLE')
    def test_future_source_and_new_contract_cannot_reuse_projection(self):
        self.at-=1;self.assertEqual(self.q.capture()['status'],'UNAVAILABLE')
        self.at=OPEN+900.2;self.pool.select(market(OPEN+900),80000)
        self.assertEqual(self.q.capture()['status'],'UNAVAILABLE')
    def test_duplicates_preserve_source_and_acceptance_clocks(self):
        first=self.q.capture();self.at+=1;accepted(self.p,self.at)
        current=self.q.capture()
        for field in ('sequence','exchange_ts','accepted_ts','expires_at'):self.assertEqual(current[field],first[field])
    def test_transport_single_flight_retains_valid_quote_for_32_concurrent_requests(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def read():
            calls.append(1)
            if len(calls)>1:entered.set();release.wait(2)
            return self.q.capture()
        transport=QuoteTransport(read,lambda:self.at)
        original=transport.capture()
        with ThreadPoolExecutor(max_workers=32) as threads:
            pending=threads.submit(transport.capture);self.assertTrue(entered.wait(1))
            values=list(threads.map(lambda _:transport.capture(),range(128)))
            release.set();pending.result(1)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(v==original for v in values))
    def test_transport_failure_retains_only_unexpired_provenance_and_explicit_revocation_clears(self):
        transport=QuoteTransport(self.q.capture,lambda:self.at);first=transport.capture()
        transport.read=lambda:(_ for _ in ()).throw(TimeoutError())
        for n in range(1,12):
            self.at=OPEN+300+n*.5;v=transport.capture()
            self.assertEqual(v['status'],'AVAILABLE');self.assertEqual(v['expires_at'],first['expires_at'])
        self.at=first['expires_at'];self.assertEqual(transport.capture()['status'],'UNAVAILABLE')
        self.at=OPEN+300;transport.read=self.q.capture;transport.capture();self.p.book=None
        self.assertEqual(transport.capture()['status'],'UNAVAILABLE');self.assertIsNone(transport.cached)
    def test_corrupt_loopback_response_cannot_fall_back(self):
        transport=QuoteTransport(self.q.capture,lambda:self.at);transport.capture()
        bad=self.q.capture();bad['exchange_ts']=self.at+1;transport.read=lambda:bad
        self.assertEqual(transport.capture()['status'],'UNAVAILABLE');self.assertIsNone(transport.cached)

class MainConstraintEvidence(unittest.TestCase):
    def test_native_only_lease_reproduces_pre_repair_failure_without_revalidation(self):
        results=[]
        for age in (1.,2.,3.,4.9):
            p=ProcessorEnvelope(Directional(),'main');p.restore({})
            with tempfile.TemporaryDirectory() as td:
                f=frame(offset=300,sequence=1,p=.6,ask=.6)
                f['brti']['cf_ts']=f['captured_ts']-age
                f['brti']['delivery']['observed_ts']=f['feature_cutoff']-.01
                _,_,v=p.process((f,'attempt'),f['captured_ts']+.01)
                atomic_json(Path(td)/'main.json',v)
                observed=[public_view(td,'main',f['captured_ts']+n/100)['status'] for n in range(1,500)]
                holes=sum(x=='UNAVAILABLE' for x in observed)
                self.assertGreater(holes,0)
                self.assertEqual(public_view(td,'main',v['expires_at'])['reason'],'SOURCE_EXPIRED')
                results.append(dict(brti_age_at_capture=age,expiry_after_capture=v['expires_at']-f['captured_ts'],
                    unavailable_samples=holes,total_samples=len(observed),step_seconds=.01,
                    desired_continuity='FAIL',stale_guidance_suppression='PASS'))
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'native_only_continuity_counterexample.json').write_text(json.dumps(dict(status='PRE_REPAIR_COUNTEREXAMPLE',cadence=5,
            interpretation='Original native-only lease fails without read-only confirmation; repaired path tested separately.',results=results),indent=2)+'\n')
    def test_faster_authoritative_cadence_changes_events_without_changing_thresholds(self):
        native,fast=Directional(),Directional();native.restore({});fast.restore({})
        tape=[frame(offset=425,sequence=1,p=.6,ask=.6),
              frame(offset=426,sequence=2,p=.95,ask=.35),
              frame(offset=430,sequence=3,p=.6,ask=.6)]
        baseline=[];faster=[]
        for i,f in enumerate(tape):
            at=f['captured_ts']+.001
            if i!=1:baseline.append(native.process(deepcopy(f),at))
            faster.append(fast.process(deepcopy(f),at))
        self.assertIsNone(native.origin);self.assertIsNotNone(fast.origin)
        self.assertTrue(faster[1][2]['final']['ready'])
        self.assertTrue(all(not x[2]['final']['ready'] for x in baseline))
        result=dict(status='EVENT_EQUIVALENCE_FAIL',baseline_origin=native.origin,
            faster_origin=fast.origin['origin_id'],extra_final_call=True,
            interpretation='Same byte-frozen model/gates, different input times: extra EARLY origin and FINAL call.')
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'cadence_event_counterexample.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':unittest.main()
