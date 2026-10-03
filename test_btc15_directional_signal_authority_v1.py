"""Synthetic integration/adversarial tests; no market cohort or endpoints."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from directional_shadow_examples_v1 import fixture as legacy_fixture, START
from btc15_directional_signal_authority_v1 import (
    Authority, initialize, decode_state, pack, snapshot_identity, PROTECTED_SHA256,
)
from btc15_directional_signal_publication_v1 import signal_view
import btc15_qualified_forward_observer_v1 as observer


def fixture(offset=300, **kwargs):
    raw = legacy_fixture(offset, **kwargs)
    raw['generated_utc'] = raw['source_timestamp_utc']
    raw['timer']['close_basis'] = 'source_timestamp_plus_logged_remaining'
    raw['market'].update(target=100000., brti_ready=True, brti_age_seconds=0.1, brti_value=100080.)
    raw['parity'] = dict(status='PASS', contract=raw['contract'], api_contract=raw['contract'],
                         timestamp_utc=raw['source_timestamp_utc'])
    return raw


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'signals.sqlite3'
        initialize(self.path, START)
        self.authority = Authority(self.path, runtime_epoch='SYNTHETIC_EPOCH_A', build={'scope':'SYNTHETIC'})

    def tearDown(self):
        self.temp.cleanup()

    def consume(self, raw=None, offset=None):
        raw = fixture() if raw is None else raw
        now = START + timedelta(seconds=offset) if offset is not None else observer.datetime.fromisoformat(raw['source_timestamp_utc'])
        return self.authority.consume(raw, observer.observation(raw, now), now_utc=now, receipt_utc=now)

    def rows(self, table='records'):
        with sqlite3.connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM '+table)]

    def state(self):
        with sqlite3.connect(self.path) as db:
            return decode_state(db.execute("SELECT value FROM meta WHERE key='state'").fetchone()[0])

    def test_early_sole_owner_and_original_exact_ask(self):
        for final in ({}, dict(source='FROZEN_V4_6_FINAL', ready=True, side='DOWN', confidence=.95)):
            with self.subTest(final=final):
                raw=fixture();raw['final']=final
                with tempfile.TemporaryDirectory() as d:
                    path=Path(d)/'db';initialize(path,START)
                    a=Authority(path,runtime_epoch='test',build={})
                    now=START+timedelta(seconds=300)
                    out=a.consume(raw,observer.observation(raw,now),now_utc=now,receipt_utc=now)
                    self.assertEqual(out['event'],'BUY')
                    self.assertEqual(out['origin']['original_ask'],raw['market']['up_ask'])
                    self.assertEqual(out['origin']['protected_early'],raw['early'])
                    self.assertFalse(out['final_confirmation'])

    def test_final_never_creates_buy(self):
        out=self.consume(fixture(early_ready=False,final_ready=True))
        self.assertEqual(out['status'],'PASS');self.assertIsNone(out['event'])
        self.assertEqual(self.rows('origins'),[])

    def test_repeated_requests_do_not_create_transitions(self):
        first=self.consume()
        for n in range(50):
            raw=fixture();raw['generated_utc']=(START+timedelta(seconds=300+.01*n)).isoformat()
            out=self.consume(raw,offset=300+.01*n)
            self.assertIsNone(out['event']);self.assertEqual(out['guidance'],'BUY')
        self.assertEqual(sum(x['event']=='BUY' for x in self.rows()),1)
        self.assertEqual(self.rows('origins'),[first['origin']])

    def test_unchanged_source_changed_final_is_conflict_not_transition(self):
        self.consume()
        before=self.state()
        out=self.consume(fixture(final_ready=True,final_side='DOWN'))
        self.assertEqual(out['reason'],'SAME_SOURCE_PAYLOAD_CONFLICT')
        self.assertEqual(self.state(),before);self.assertIsNone(out['event'])

    def test_rapid_causal_management_and_no_origin_rewrite(self):
        first=self.consume();origin=deepcopy(first['origin'])
        hold=self.consume(fixture(300.000001,final_ready=True))
        protect=self.consume(fixture(300.000002,final_ready=True,final_side='DOWN'))
        after=self.consume(fixture(300.000003,final_ready=True))
        self.assertEqual([x['event'] for x in (first,hold,protect,after)],['BUY','HOLD','PROTECT',None])
        self.assertEqual(after['guidance'],'PROTECT')
        self.assertTrue(all(x['origin']==origin for x in (hold,protect,after)))
        self.assertTrue(all(x['origin_id']==origin['origin_id'] for x in self.rows()))

    def test_final_disagreement_and_confirmation_loss_never_exit(self):
        self.consume();self.consume(fixture(305,final_ready=True))
        out=self.consume(fixture(310,final_side='DOWN'))
        self.assertEqual(out['event'],'PROTECT')
        self.assertIn('NO_QUALIFIED',out['exit_rule'])
        self.assertNotIn('EXIT',[r['event'] for r in self.rows()])

    def test_confirmation_loss_with_complete_evidence_protects(self):
        self.consume();self.consume(fixture(305,final_ready=True))
        self.assertEqual(self.consume(fixture(310))['event'],'PROTECT')

    def test_missing_and_stale_final_are_unavailable_not_hold_or_protect(self):
        self.consume();self.consume(fixture(305,final_ready=True));before=self.state()
        for change in ('missing','brti','confidence','source'):
            raw=fixture(310,final_ready=True)
            if change=='missing':raw['final']={}
            if change=='brti':raw['market']['brti_age_seconds']=5.000001
            if change=='confidence':raw['final']['confidence']=None
            if change=='source':raw['final']['source']='startup_two_final'
            out=self.consume(raw)
            self.assertEqual(out['status'],'UNAVAILABLE',change)
            self.assertIsNone(out['guidance']);self.assertIsNone(out['event'])
            self.assertEqual(self.state(),before)

    def test_wait_and_recovery_do_not_advance_manager_on_wait(self):
        for existing in (False,True):
            if existing:self.consume()
            before=self.state()
            for failure in ('parity','paired','source','quote'):
                raw=fixture(305)
                if failure=='parity':raw['parity']['status']='WAIT'
                if failure=='paired':raw['health']['paired_quotes']=False
                if failure=='source':raw['health']['source_fresh']=False
                if failure=='quote':raw['market']['up_ask']=None
                out=self.consume(raw)
                self.assertEqual(out['status'],'UNAVAILABLE',failure)
                self.assertEqual(self.state(),before)
        self.assertEqual(self.consume(fixture(305,final_ready=True))['event'],'HOLD')

    def test_rollover_has_distinct_origin_and_old_contract_cannot_return(self):
        old=self.consume()
        new=self.consume(fixture(1200,close_offset=1800,side='DOWN'))
        self.assertEqual(new['event'],'BUY')
        self.assertNotEqual(new['origin_id'],old['origin_id'])
        state=self.state();out=self.consume(fixture(310))
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertEqual(self.state(),state)
        self.assertEqual(self.rows('origins')[0],old['origin'])

    def test_restart_epoch_never_recreates_or_mutates_origin(self):
        first=self.consume()
        self.authority=Authority(self.path,runtime_epoch='SYNTHETIC_EPOCH_B',build={'other':'build'})
        repeat=self.consume();hold=self.consume(fixture(305,final_ready=True))
        self.assertIsNone(repeat['event']);self.assertEqual(hold['event'],'HOLD')
        self.assertEqual(hold['origin'],first['origin'])
        self.assertEqual(hold['signal_runtime_epoch'],'SYNTHETIC_EPOCH_B')
        self.assertEqual(hold['origin']['signal_runtime_epoch'],'SYNTHETIC_EPOCH_A')

    def test_missing_ledger_does_not_autoinitialize(self):
        path=Path(self.temp.name)/'absent'
        a=Authority(path,runtime_epoch='X',build={})
        with self.assertRaises(sqlite3.OperationalError):a.consume(None,{},now_utc=START,receipt_utc=START)
        self.assertFalse(path.exists())
        with self.assertRaises(FileExistsError):initialize(self.path,START)

    def test_delayed_publication_and_future_clocks_never_renew_source(self):
        raw=fixture();raw['generated_utc']=(START+timedelta(seconds=316)).isoformat()
        self.assertEqual(self.consume(raw,offset=316)['status'],'UNAVAILABLE')
        self.assertEqual(self.rows('origins'),[])
        raw=fixture();raw['generated_utc']=(START+timedelta(seconds=301)).isoformat()
        self.assertEqual(self.consume(raw)['reason'],'PUBLICATION_CLOCK_ORDER_OR_ACTIVATION')

    def test_no_truncation_of_submicrosecond_source(self):
        raw=fixture();raw['source_timestamp_utc']='2026-01-01T12:05:00.0000001+00:00'
        out=self.consume(raw,offset=300)
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertEqual(self.rows('origins'),[])

    def test_target_conflict_and_wrong_contract_window_are_rejected(self):
        self.consume();before=self.state()
        raw=fixture(305);raw['market']['target']=99999.
        self.assertEqual(self.consume(raw)['reason'],'CONTRACT_TARGET_CHANGED')
        raw=fixture(305);raw['timer']['close_utc']=(START+timedelta(seconds=1800)).isoformat()
        self.assertEqual(self.consume(raw)['status'],'UNAVAILABLE')
        self.assertEqual(self.state(),before)

    def test_scalp_overlapping_serial_events_never_enter_directional_input(self):
        class Explodes(dict):
            def items(self):raise AssertionError('SCALP read')
            def get(self,*args):raise AssertionError('SCALP read')
        raw=fixture();raw['scalp']=Explodes()
        now=START+timedelta(seconds=300)
        q=observer.observation(fixture(),now)
        out=self.authority.consume(raw,q,now_utc=now,receipt_utc=now)
        self.assertEqual(out['event'],'BUY');self.assertNotIn('scalp',out['origin']['protected_publication'])
        for offset in (305,310,315):
            raw=fixture(offset);raw['scalp']={'origins':['A','B','C'],'event':'EXIT','pending':295}
            self.consume(raw)
        self.assertEqual(len(self.rows('origins')),1)

    def test_sink_failure_rolls_back_all_signal_changes(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.consume()
        self.assertIsNone(self.state().position);self.assertEqual(self.rows('origins'),[])
        with sqlite3.connect(self.path) as db:db.execute('DROP TRIGGER fail')
        self.assertEqual(self.consume()['event'],'BUY')

    def test_locked_sink_cannot_accept_or_publish_uncommitted_buy(self):
        db=sqlite3.connect(self.path);db.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(sqlite3.OperationalError):self.consume()
            self.assertIsNone(self.state().position)
        finally:db.rollback();db.close()

    def test_concurrent_consumers_can_commit_only_one_buy(self):
        def attempt(_):
            try:return self.consume()['event']
            except sqlite3.OperationalError:return 'LOCKED'
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(30)))
        self.assertEqual(results.count('BUY'),1);self.assertEqual(len(self.rows('origins')),1)

    def test_immutable_origin_storage_and_state_conflict_guards(self):
        self.consume()
        with sqlite3.connect(self.path) as db:
            for sql in ("UPDATE origins SET payload='{}'",'DELETE FROM origins'):
                with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
            value=json.loads(db.execute("SELECT value FROM meta WHERE key='state'").fetchone()[0])
            value['position']['entry_ask']=.01
            db.execute("UPDATE meta SET value=? WHERE key='state'",(pack(value),))
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_ORIGIN_CONFLICT'):self.consume(fixture(305))

    def test_source_outage_does_not_create_strategy_pass_or_loss(self):
        self.consume();before=self.state();now=START+timedelta(seconds=305)
        out=self.authority.consume(None,{},now_utc=now,receipt_utc=now)
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertIsNone(out['guidance'])
        self.assertEqual(self.state(),before)

    def test_expiry_is_not_an_invented_exit(self):
        first=self.consume();out=self.consume(fixture(900,early_ready=False))
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertIsNone(out['event'])
        self.assertEqual(self.rows('origins'),[first['origin']])

    def test_unavailable_provenance_is_explicit(self):
        origin=self.consume()['origin']
        for key in ('native_epoch','native_decision_id','owner_source_witness','native_receipt_utc',
                    'native_consumption_utc','native_publication_utc','manual_fill'):
            self.assertIsNone(origin[key],key)
        self.assertFalse(origin['v2_admitted'])
        self.assertEqual(origin['contract']['close_basis'],'source_timestamp_plus_logged_remaining')

    def test_publication_reads_are_passive_and_cannot_repeat_buy(self):
        self.consume();before=self.state();count=len(self.rows())
        for _ in range(30):
            view=signal_view(fixture(),self.path,START+timedelta(seconds=300))
            self.assertIsNone(view['event']);self.assertEqual(view['guidance'],'BUY')
        self.assertEqual(self.state(),before);self.assertEqual(len(self.rows()),count)
        self.assertEqual(signal_view(fixture(305),self.path,START+timedelta(seconds=305))['status'],'UNAVAILABLE')
        self.assertEqual(signal_view(fixture(),self.path,START+timedelta(seconds=316))['status'],'UNAVAILABLE')
        wait=fixture();wait['health']['source_fresh']=False
        self.assertEqual(signal_view(wait,self.path,START+timedelta(seconds=300))['status'],'UNAVAILABLE')

    def test_input_is_not_mutated_by_acceptance_or_management(self):
        for raw in (fixture(),fixture(305,final_ready=True),fixture(310,final_side='DOWN')):
            original=deepcopy(raw);self.consume(raw);self.assertEqual(raw,original)

    def test_observer_consumes_one_existing_get_and_only_appends(self):
        events=[];raw=fixture()
        class Response:
            def raise_for_status(self):pass
            def json(self):return raw
        with patch.object(observer.requests,'get',return_value=Response()) as get, patch.object(observer,'append',side_effect=lambda r:events.append('append')):
            observer.collect_once('http://synthetic/dashboard_state.json')
            self.assertEqual(get.call_count,1);self.assertEqual(events,['append'])
        events.clear()
        with patch.object(observer.requests,'get',return_value=Response()),patch.object(observer,'append',side_effect=OSError('sink')):
            with self.assertRaises(OSError):observer.collect_once('http://synthetic')
        self.assertEqual(events,[])

    def test_slow_evidence_sink_does_not_backdate_acceptance(self):
        raw=fixture()
        class Clock:
            calls=0
            @classmethod
            def now(cls,*_):
                cls.calls+=1;return START+timedelta(seconds=300 if cls.calls==1 else 316)
        class Response:
            def raise_for_status(self):pass
            def json(self):return raw
        with patch.object(observer.requests,'get',return_value=Response()),patch.object(observer,'append'),patch.object(observer,'datetime',Clock):
            # observation.age requires datetime.fromisoformat, delegated explicitly.
            from datetime import datetime
            Clock.fromisoformat=datetime.fromisoformat
            record=observer.collect_once('http://synthetic')
            out=self.authority.consume(raw,record,now_utc=Clock.now(),receipt_utc=Clock.fromisoformat(record['observed_utc']))
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertEqual(self.rows('origins'),[])

    def test_signal_creation_is_not_backdated_to_source_quote(self):
        raw=fixture();raw['generated_utc']=(START+timedelta(seconds=301)).isoformat()
        out=self.consume(raw,offset=302)
        self.assertEqual(out['event'],'BUY')
        self.assertEqual(out['origin']['signal_timestamp_utc'],(START+timedelta(seconds=302)).isoformat())
        self.assertEqual(out['origin']['protected_source_timestamp_utc'],raw['source_timestamp_utc'])


class WiringTests(unittest.TestCase):
    def test_assembled_http_producer_no_longer_hosts_lifecycle_or_projection(self):
        import importlib.util,sys,threading
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        from datetime import datetime
        from btc15_information_install_v1 import assemble
        from btc15_isolated_lifecycle_consumer_v1 import Consumer
        import btc15_directional_signal_publication_v1 as publication_module
        current=[fixture()];builds=[]
        def build():
            builds.append(1);return deepcopy(current[0])
        class Clock:
            fromisoformat=datetime.fromisoformat
            @staticmethod
            def now(*args):return datetime.fromisoformat(current[0]['source_timestamp_utc'])
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'BTC15_ENABLE_DIRECTIONAL_SIGNALS':'1'}):
            root=Path(d);installed=assemble(root/'installed')
            path=root/'btc15_directional_signals_v1.sqlite3';initialize(path,START)
            consumer=Consumer(root/'forward.csv',path,root/'cursor.sqlite3',
                              epoch='HTTP_SYNTHETIC',build={},clock=Clock.now)
            with patch.dict(sys.modules,{'BTC15_DASHBOARD_STATE_V2':SimpleNamespace(build_state=build)}):
                spec=importlib.util.spec_from_file_location('assembled_signal_server',installed/'BTC15_DASHBOARD_LIVE_SERVER_V1.py')
                server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)
            # A real script launch puts its assembled directory first on sys.path.
            spec=importlib.util.spec_from_file_location('btc15_information_proxy_v1',installed/'btc15_information_proxy_v1.py')
            proxy_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(proxy_module)
            server=ThreadingHTTPServer(('127.0.0.1',0),server_module.Handler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            append_original=observer.append
            try:
                with patch.dict(sys.modules,{'btc15_information_proxy_v1':proxy_module}),\
                     patch.object(observer,'datetime',Clock),patch.object(publication_module,'datetime',Clock),\
                     patch.object(publication_module,'_btc15_data_root',return_value=root),\
                     patch.object(observer,'append',side_effect=lambda r:append_original(r,root/'forward.csv')):
                    url=f'http://127.0.0.1:{server.server_port}/dashboard_state.json'
                    events=[]
                    for offset,kw in ((300,{}),(300,{}),(305,{'final_ready':True}),(310,{'final_side':'DOWN'})):
                        current[0]=fixture(offset,**kw)
                        observer.collect_once(url)
                        result=consumer.step()
                        if result['status']=='HEADER':result=consumer.step()
                        events.append(result['event'])
                    response=observer.requests.get(url,timeout=2).json()
                    self.assertNotIn('directional_signal',response)
                    view=consumer.view()
                    self.assertEqual(view['guidance'],'PROTECT');self.assertIsNone(view['event'])
                    self.assertEqual(events,['BUY',None,'HOLD','PROTECT'])
                    self.assertEqual(len(builds),5) # exactly the 4 pre-existing polls + explicit read
                    with sqlite3.connect(path) as db:
                        self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],4)
                        origin=json.loads(db.execute('SELECT payload FROM origins').fetchone()[0])
                    self.assertNotIn('directional_signal',origin['protected_publication'])
            finally:
                server.shutdown();server.server_close();worker.join(2)

    def test_actual_protected_builder_controls_qualification_without_shadow_or_startup_promotion(self):
        import base64,gzip
        import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
        ns={'__file__':str(Path(__file__).parent/'BTC15_DASHBOARD_STATE_V2.py')}
        exec(compile(gzip.decompress(base64.b64decode(installer.PAYLOADS['BTC15_DASHBOARD_STATE_V2.py'])),
                     'unaltered_protected_builder','exec'),ns)
        now=START+timedelta(seconds=300);ticker=fixture()['contract']
        snap=dict(_timestamp=now,_contract=ticker,_paired_quotes=True,
                  preferred_fair_side='UP',current_target_side='UP',preferred_fair=.75,preferred_edge=.08,
                  side_ask=.45,side_bid=.43,minutes_left=10.,seconds_left=600.,btc_gap=25.,
                  dist_over_range5=1.2,brti_ready=True,brti_age_seconds=.1,brti_gap=25.,brti_side='UP',
                  target=100000.,btc_price=100025.,brti_value=100025.,
                  up_bid=.43,up_ask=.45,down_bid=.55,down_ask=.57,
                  provisional_candidate=False,candidate_persistence_30s=0)
        parity=dict(contract=ticker,unified_contract=ticker,api_contract=ticker,
                    audit_timestamp_utc=now.isoformat(),overall_status='PASS')
        ns['now_utc']=lambda:now
        ns['latest_unified_snapshot']=lambda rows:dict(snap)
        ns['read_csv_tail']=lambda path,*args:[parity] if 'parity' in path.name else []
        raw=ns['build_state']()
        self.assertTrue(raw['early']['ready']);self.assertFalse(raw['final']['ready'])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db';initialize(path,START)
            out=Authority(path,runtime_epoch='synthetic',build={}).consume(raw,observer.observation(raw,now),now_utc=now,receipt_utc=now)
            self.assertEqual(out['event'],'BUY');self.assertEqual(out['origin']['protected_early'],raw['early'])
        for field,value in (('side_ask',.450001),('preferred_fair',.749999),('preferred_edge',.079999),
                            ('minutes_left',10.000001),('minutes_left',1.999999),('btc_gap',24.999999)):
            original=snap[field];snap[field]=value
            self.assertFalse(ns['build_state']()['early']['ready'],field)
            snap[field]=original
        snap.update(preferred_fair=.95,minutes_left=5.,seconds_left=300.,btc_gap=80.,brti_gap=80.)
        self.assertTrue(ns['build_state']()['final']['ready'])

    def test_optional_packaged_integration_preserves_protected_source_and_no_new_polling(self):
        import hashlib
        from btc15_information_install_v1 import assemble
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'BTC15_ENABLE_DIRECTIONAL_SIGNALS':'1'}):
            out=assemble(Path(d))
            self.assertEqual(hashlib.sha256((out/'BTC15_DASHBOARD_STATE_V2.py').read_bytes()).hexdigest(),PROTECTED_SHA256)
            server=(out/'BTC15_DASHBOARD_LIVE_SERVER_V1.py').read_text()
            self.assertNotIn('attach(state)',server)
            html=(out/'BTC_Kalshi_App_Live_v13.html').read_text()
            self.assertEqual(html.count('function renderDirectionalSignal'),0)
            self.assertEqual(html.count('id="directionalSignalPanel"'),0)
            compile(server,str(out),'exec')
            from btc15_directional_signal_publication_v1 import RENDER
            self.assertNotIn('fetch(',RENDER);self.assertNotIn('setInterval',RENDER)

    def test_new_authority_has_no_network_order_calls_or_danger_injection(self):
        import inspect
        import btc15_directional_signal_authority_v1 as module
        source=inspect.getsource(module)
        tree=ast.parse(source)
        imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        imports|={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertFalse(imports & {'requests','socket','urllib','subprocess'})
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                self.assertNotIn(n.func.attr,('post','put','delete','create_order','submit_order'))
                if n.func.attr=='update' and isinstance(n.func.value,ast.Name) and n.func.value.id=='manager':
                    self.assertEqual({k.arg for k in n.keywords},{'now_utc'})


if __name__=='__main__':unittest.main()
