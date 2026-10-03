"""Actual owner/Delivery/native consumption passive source controls."""
import ast
import base64
from collections import deque
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone
import json
from pathlib import Path
import requests
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sprint_evidence.passive_capture import Producer,Identity
from sprint_evidence.source_witness_capture import *
from test_sprint_capture import MemorySocket
from test_btc15_external_evidence_admission_v1 import KEY

ROOT=Path(__file__).parent
AT=1780000000.


def source_namespace(kind,enabled=True):
    names={'owner':'brti_shared_feed_v1.py','delivery':'btc15_brti_delivery_v1.py','native':'bot_two_output_build_v4_13_profit_protection_shadow.py'}
    shas={'owner':OWNER_SHA,'delivery':DELIVERY_SHA,'native':NATIVE_SHA}
    ident=Identity('synthetic-'+kind,'synthetic-build',shas[kind],'synthetic-run','uncertified-clock','synthetic-boot')
    sock=MemorySocket();p=Producer('none',ident,KEY,sock=sock);tap=SourceWitnessCapture(p)
    ns={'__name__':__name__,'_sprint_sources':tap}
    transforms={'owner':instrument_owner,'delivery':instrument_delivery,'native':instrument_native}
    tree=transforms[kind]((ROOT/names[kind]).read_bytes(),enabled=enabled)
    if kind=='native':tree=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_latest_brti'],type_ignores=[])
    exec(compile(tree,'actual-'+kind,'exec'),ns)
    return ns,p,sock


def emissions(sock):return [json.loads(x)['event']['body']['emission'] for x in sock.packets]


def compare_delivery(d):return dict(states=list(d.states),statuses=list(d.statuses),seen=d.seen,epoch=d.epoch)


class SourceWitnessTests(unittest.TestCase):
    def test_actual_owner_validation_error_recovery_unchanged(self):
        off,_,_=source_namespace('owner',False);on,p,sock=source_namespace('owner')
        batch=[dict(index_id='BRTI',source_ts_ms=int((AT-1)*1000),value=100000.)]
        current=[batch];calls=[0,0]
        def fetch(which):
            def call():
                calls[which]+=1
                if isinstance(current[0],Exception):raise current[0]
                return deepcopy(current[0])
            return call
        with patch('time.time',return_value=AT),patch('time.monotonic',return_value=100.),patch('time.time_ns',return_value=int((AT+.003)*1e9)):
            a=off['SharedBrtiPoller'](fetch(0),poll_interval_s=2,max_qualification_age_s=5,jitter_s=0)
            b=on['SharedBrtiPoller'](fetch(1),poll_interval_s=2,max_qualification_age_s=5,jitter_s=0)
            a.owner_epoch=b.owner_epoch='same-owner'
            cases=[batch,batch,[],[dict(index_id='BRTI',source_ts_ms=int((AT+1)*1000),value=100000)],
                   [dict(index_id='BRTI',source_ts_ms=int((AT-1)*1000),value=99999)],RuntimeError('source wait'),batch]
            for case in cases:
                current[0]=case;self.assertEqual(a.poll_once(force=True),b.poll_once(force=True))
                self.assertEqual(a.snapshot(),b.snapshot());self.assertEqual(a.history(),b.history())
            self.assertFalse(b.poll_once());self.assertEqual(calls,[7,7])
        self.assertEqual(len(emissions(sock)),7)
        successes=[e for e in emissions(sock) if e['payload_validation_succeeded']]
        self.assertTrue(all(e['batch_received_wall']==AT for e in successes))
        self.assertTrue(all(e['response_reference'] is None for e in successes)) # injected fetch has no actual HTTP witness
        self.assertGreater(successes[0]['completed_boundary_observed_wall_ns'],int(AT*1e9))
        self.assertEqual(successes[0]['latest_source_ts_ms'],int((AT-1)*1000))

    def test_existing_http_bytes_exact_link_no_added_get(self):
        ns,p,sock=source_namespace('owner')
        raw=b'{"data":{"id":"BRTI","payload":[{"time":1779999999000,"value":"100000"}]}}'
        response=requests.Response();response.status_code=200;response._content=raw
        calls=[]
        fetcher=object.__new__(ns['KalshiBrtiFetcher']);fetcher.http=SimpleNamespace(get=lambda *a,**k:(calls.append(1) or response));fetcher.timeout_s=1;fetcher._hdr=lambda:{}
        with patch('time.time',return_value=AT),patch('time.monotonic',return_value=100.),patch('time.time_ns',return_value=int((AT+.001)*1e9)):
            owner=ns['SharedBrtiPoller'](fetcher.fetch_once,poll_interval_s=2,max_qualification_age_s=5,jitter_s=0)
            self.assertTrue(owner.poll_once(force=True))
        es=emissions(sock);self.assertEqual(len(es),2);self.assertEqual(calls,[1])
        self.assertEqual(base64.b64decode(es[0]['body_base64']),raw)
        self.assertEqual(es[1]['response_reference']['response_sha256'],digest(raw))
        self.assertEqual(es[1]['response_reference']['response_event_sequence'],1)
        self.assertEqual(es[1]['status'],'PRIMARY_OK')
        self.assertIsNone(es[0]['source_utc']) # raw HTTP return is not exchange source time

    def test_delivery_accept_reject_restart_dedupe_off_on(self):
        off,_,_=source_namespace('delivery',False);on,p,sock=source_namespace('delivery')
        a=off['Delivery']();b=on['Delivery']()
        cases=[(100000,AT-1,AT,'epoch'),(100000,AT-1,AT+.1,'epoch'),(100001,AT-1,AT+.2,'epoch'),
               (100002,AT,AT+.3,'restart'),(100002,AT,AT+5.001,'restart')]
        for args in cases:
            errors=[]
            for d in (a,b):
                try:d.accept(*args);errors.append(None)
                except Exception as exc:errors.append((type(exc),str(exc)))
            self.assertEqual(errors[0],errors[1]);self.assertEqual(compare_delivery(a),compare_delivery(b))
        self.assertEqual([e['witness_kind'] for e in emissions(sock)],['LOCAL_BRTI_RECEIPT_ACCEPTED','LOCAL_BRTI_RECEIPT_ACCEPTED','LOCAL_BRTI_RECEIPT_REJECTED','LOCAL_BRTI_RECEIPT_ACCEPTED','LOCAL_BRTI_RECEIPT_REJECTED'])
        self.assertEqual(emissions(sock)[0]['received'],AT)

    def test_native_actual_select_return_clock_not_cutoff_rewrite(self):
        from btc15_brti_delivery_v1 import Delivery
        off,_,_=source_namespace('native',False);on,p,sock=source_namespace('native')
        deliveries=[Delivery(),Delivery()]
        for ns,d in zip((off,on),deliveries):
            ns.update(time=SimpleNamespace(time=lambda:AT+.2),_brti_delivery=d,_brti_lock=threading.Lock(),_brti_conflicting_seconds=set(),_brti_samples=deque())
            d.accept(100000,AT-4.9,AT-.1,'owner')
        cut=datetime.fromtimestamp(AT,timezone.utc)
        with patch('time.time_ns',return_value=int((AT+.3)*1e9)):
            self.assertEqual(off['_latest_brti'](cut),on['_latest_brti'](cut))
        e=emissions(sock)[0]
        self.assertEqual(e['original_cutoff'],AT);self.assertEqual(e['original_checked_time'],AT+.2)
        self.assertGreater(e['completed_boundary_observed_wall_ns'],int(e['original_cutoff']*1e9))
        self.assertFalse(e['selected']['ready']) # now-source > 5; unchanged real-time freshness
        self.assertIsNone(e['completed_native_decision_or_publication'])
        for d in deliveries:d.fail(AT+.2)
        self.assertEqual(off['_latest_brti'](cut),on['_latest_brti'](cut))
        for ns in (off,on):ns['_brti_conflicting_seconds'].add(int(AT-4.9))
        self.assertEqual(off['_latest_brti'](cut),on['_latest_brti'](cut))

    def test_empty_delivery_wait_no_fabricated_selection(self):
        from btc15_brti_delivery_v1 import Delivery
        ns,p,sock=source_namespace('native');ns.update(time=SimpleNamespace(time=lambda:AT),_brti_delivery=Delivery(),_brti_lock=threading.Lock(),_brti_conflicting_seconds=set(),_brti_samples=deque())
        self.assertIsNone(ns['_latest_brti'](datetime.fromtimestamp(AT,timezone.utc)))
        self.assertIsNone(emissions(sock)[0]['selected'])

    def test_capture_backlog_does_not_change_owner_or_delivery(self):
        class Lost:
            def sendto(self,*a):raise BlockingIOError
            def close(self):pass
        ns,p,_=source_namespace('delivery');p.sock=Lost();d=ns['Delivery']()
        d.accept(100000,AT-1,AT,'owner');self.assertEqual(d.select(AT,AT)['value'],100000);self.assertEqual(p.dropped,1)
        ns,p,_=source_namespace('owner');p.sock=Lost()
        with patch('time.time',return_value=AT),patch('time.monotonic',return_value=100.):
            owner=ns['SharedBrtiPoller'](lambda:[dict(index_id='BRTI',source_ts_ms=int(AT*1000),value=100000)],jitter_s=0)
            self.assertTrue(owner.poll_once(force=True));self.assertTrue(owner.snapshot()['clean_for_qualification']);self.assertEqual(p.dropped,1)

    def test_hooks_have_no_network_accept_select_or_revalidation_calls(self):
        tree=ast.parse((ROOT/'sprint_evidence/source_witness_capture.py').read_bytes())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SourceWitnessCapture')
        names=[n.func.attr for n in ast.walk(cls) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(names)&{'accept','select','fetch_once','poll_once','raise_for_status','json','read_shared_brti'})
        for kind,func,path in [('owner',instrument_owner,'brti_shared_feed_v1.py'),('delivery',instrument_delivery,'btc15_brti_delivery_v1.py'),('native',instrument_native,'bot_two_output_build_v4_13_profit_protection_shadow.py')]:
            raw=(ROOT/path).read_bytes();self.assertEqual(ast.dump(func(raw,enabled=False)),ast.dump(ast.parse(raw)))
            with self.assertRaises(ValueError):func(raw+b'changed')

if __name__=='__main__':unittest.main()
