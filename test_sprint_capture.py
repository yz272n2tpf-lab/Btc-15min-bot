"""Sprint capture engineering controls; synthetic inputs are never live samples."""
import ast
from copy import deepcopy
from dataclasses import replace
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from sprint_evidence.passive_capture import (
    Producer, Receiver, Identity, pack, digest, observed_copy, add_event_store,
    instrument_native, instrument_protected, instrument_common, detached_authority_class, MAX_TEXT, MAX_NODES,
)
from round2_evidence.capture import DetachedRecorder, initialize
from round2_evidence.test_round2 import record, artifact
from test_btc15_external_evidence_admission_v1 import POLICY, KEY

ROOT = Path(__file__).parent
IDENTITY = Identity('synthetic-native', 'synthetic-build', 'a'*64, 'synthetic-run', 'synthetic-clock','synthetic-boot')

class MemorySocket:
    def __init__(self): self.packets = []
    def sendto(self, data, *args): self.packets.append(data); return len(data)
    def close(self): pass


def crash_store(path):
    db=sqlite3.connect(path)
    db.execute('BEGIN IMMEDIATE')
    db.execute("INSERT INTO producer_events VALUES ('dead','dead',1,'hash',X'00','incomplete','')")
    os._exit(73)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'unified.sqlite'
        initialize(self.path,POLICY);add_event_store(self.path)
        self.sock=MemorySocket();self.p=Producer(self.root/'socket',IDENTITY,KEY,sock=self.sock)
        self.r=Receiver(self.path,[IDENTITY],{(IDENTITY.producer_id,IDENTITY.run_id):KEY},common_recorder=DetachedRecorder(self.path,POLICY,acquisition_key=KEY))
    def tearDown(self): self.p.close();self.temp.cleanup()
    def packet(self,body=None):
        self.assertTrue(self.p.offer('NATIVE_CYCLE', body or {'cutoff':123}))
        return self.sock.packets[-1]
    def rows(self):
        with sqlite3.connect(self.path) as db:return db.execute('SELECT seq,raw,status FROM producer_events ORDER BY seq').fetchall()

    def test_immutable_detachment_no_upstream_mutation(self):
        body={'origin':{'id':'immutable','ask':.31},'gates':[True,False]};before=deepcopy(body)
        raw=self.packet(body);self.assertEqual(body,before);body['origin']['ask']=.9
        self.assertEqual(json.loads(raw)['event']['body']['origin']['ask'],.31)
        self.assertEqual(self.r.accept(raw)['status'],'RECORDED_UNQUALIFIED_CLOCK')
        with sqlite3.connect(self.path) as db:
            for sql in ('DELETE FROM producer_events',"UPDATE producer_events SET digest='other'"):
                with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)

    def test_same_unified_original_member_bytes_and_projection(self):
        member=artifact()[0]
        self.assertTrue(self.p.common_member(member,0))
        out=self.r.accept(self.sock.packets[-1]);self.assertEqual(out['status'],'RECORDED_UNQUALIFIED_CLOCK',out)
        with sqlite3.connect(self.path) as db:
            original,projection=db.execute('SELECT original,projection FROM members').fetchone()
        self.assertEqual(original,member)
        self.assertEqual(json.loads(projection)['fields']['early.early']['status'],'OBSERVED')
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.r.accept(self.sock.packets[-1])['status'],'DUPLICATE_RECORDED')

    def test_common_bridge_restart_after_event_commit(self):
        member=artifact()[0];self.p.common_member(member,0);raw=self.sock.packets[-1]
        with patch.object(self.r,'_common',return_value={'status':'UNAVAILABLE','reason':'consumer crash boundary'}):
            self.assertEqual(self.r.accept(raw)['status'],'UNAVAILABLE')
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.r.accept(raw)['status'],'DUPLICATE_RECORDED')
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM members').fetchone()[0],1)

    def test_duplicate_replay_conflict_and_gap_sticky(self):
        a=self.packet();self.r.accept(a);self.assertEqual(self.r.accept(a)['status'],'DUPLICATE_RECORDED')
        self.p.sequence=0;b=self.packet({'cutoff':999})
        self.assertEqual(self.r.accept(b)['reason'],'REPLAY_CONFLICT')
        self.p.sequence=2;c=self.packet();self.assertEqual(self.r.accept(c)['status'],'RECORDED_UNAVAILABLE_GAP')
        self.assertEqual(self.r.accept(self.packet())['status'],'RECORDED_UNAVAILABLE_GAP')

    def test_rollover_preserves_objects_without_relinking(self):
        for ticker in ('A','B'):
            self.p.native({'now_ts':123,'ticker':ticker,'_ec_row':{'origin_id':ticker},'_brti_contract':None})
            self.r.accept(self.sock.packets[-1])
        bodies=[json.loads(x[1])['event']['body'] for x in self.rows()]
        self.assertEqual([b['ticker'] for b in bodies],['A','B'])
        self.assertTrue(all(b['witness_limits']['actual_accepted_early_origin'] is None for b in bodies))

    def test_malformed_unregistered_tampered_clock_not_certified(self):
        raw=self.packet();ev=json.loads(raw)
        for payload in (b'',b'{"x":NaN}',b'{"x":1,"x":2}',b'{}',raw[:-1]):
            self.assertEqual(self.r.accept(payload)['status'],'UNAVAILABLE')
        ev['mac']='0'*64;self.assertEqual(self.r.accept(pack(ev))['reason'],'PRODUCER_AUTHENTICATION')
        bad=Producer('unused',replace(IDENTITY,run_id='restart'),KEY,sock=MemorySocket())
        bad.offer('NATIVE_CYCLE',{})
        self.assertEqual(self.r.accept(bad.sock.packets[-1])['reason'],'UNREGISTERED_PRODUCER_BUILD_RUN')
        self.assertFalse(self.rows())
        self.assertEqual(json.loads(raw)['event']['hook_read']['clock_qualified'],False)

    def test_signed_malformed_nested_objects_fail_closed(self):
        import hmac,hashlib
        raw=self.packet();event=json.loads(raw)['event']
        for key,values in [('hook_read',[None,[],123,'bad']),('body',[None,[],True]),('identity',[None,[]])]:
            for value in values:
                e=deepcopy(event);e[key]=value;data=pack(e)
                malformed=pack(dict(event=e,sha256=digest(data),mac=hmac.new(KEY,data,hashlib.sha256).hexdigest()))
                self.assertEqual(self.r.accept(malformed)['status'],'UNAVAILABLE')
        for value in (None,[],True):
            self.assertEqual(self.r.accept(pack(dict(event=value,sha256='x',mac='x')))['status'],'UNAVAILABLE')
        self.assertFalse(self.rows())

    def test_disk_full_lock_and_quota_do_not_advance(self):
        raw=self.packet()
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN EXCLUSIVE')
            self.assertEqual(self.r.accept(raw)['status'],'UNAVAILABLE')
        with patch.object(self.r,'_db',side_effect=sqlite3.OperationalError('disk full')):
            self.assertEqual(self.r.accept(raw)['status'],'UNAVAILABLE')
        self.assertFalse(self.rows())
        with sqlite3.connect(self.path) as db:db.execute("UPDATE meta SET v='32768' WHERE k='sprint_quota'")
        self.assertEqual(self.r.accept(raw)['reason'],'STORE_QUOTA');self.assertFalse(self.rows())

    def test_missing_store_not_recreated_and_crash_transaction_rolls_back(self):
        p=multiprocessing.Process(target=crash_store,args=(self.path,));p.start();p.join(5)
        self.assertEqual(p.exitcode,73);self.assertFalse(self.rows())
        self.assertEqual(self.r.accept(self.packet())['status'],'RECORDED_UNQUALIFIED_CLOCK')
        self.path.unlink();self.assertEqual(self.r.accept(self.packet())['status'],'UNAVAILABLE');self.assertFalse(self.path.exists())

    def test_producer_absence_consumer_absence_and_backlog_never_block(self):
        path=self.root/'socket'
        try:p=Producer(path,IDENTITY,KEY)
        except PermissionError:
            if os.getenv('BTC15_REQUIRE_SOCKET_SMOKE')=='1':raise
            self.skipTest('Local AF_UNIX sockets denied by environment; hosted required gate retained')
        try:
            self.assertFalse(p.offer('NATIVE_CYCLE',{}));self.assertEqual(p.dropped,1)
            server=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);server.bind(str(path))
            try:
                start=time.perf_counter()
                for i in range(50):p.offer('NATIVE_CYCLE',{'i':i})
                elapsed=time.perf_counter()-start
                self.assertGreater(p.dropped,1)
                self.assertLess(elapsed,2.0) # timeout guard, not hosted overhead budget
                self.assertGreater(p.sent,0)
            finally:server.close()
            self.assertFalse(p.offer('NATIVE_CYCLE',{}))
        finally:p.close()

    def test_size_node_depth_and_arbitrary_object_bounds(self):
        class Dangerous:
            def __repr__(self):raise AssertionError('must not repr')
            def __str__(self):raise AssertionError('must not str')
        x=observed_copy({'unknown':Dangerous(),'nan':float('nan')})
        self.assertIsNone(x['unknown']['value']);self.assertIsNone(x['nan']['value'])
        for obj in ({'a':'x'*MAX_TEXT,'b':'y'},[1]*(MAX_NODES+1),{'i':1<<10000}):
            self.assertFalse(self.p.offer('NATIVE_CYCLE',obj))
        deep={}
        for i in range(20):deep={'next':deep}
        self.assertFalse(self.p.offer('NATIVE_CYCLE',deep))
        self.assertEqual(self.p.dropped,4)

    def test_capture_disabled_has_no_socket_clock_copy_or_sequence(self):
        p=Producer('unused',IDENTITY,KEY,enabled=False)
        with patch('socket.socket',side_effect=AssertionError('no socket')),patch('time.time_ns',side_effect=AssertionError('no clock')):
            self.assertFalse(p.offer('NATIVE_CYCLE',object()))
        self.assertEqual(p.sequence,0);self.assertEqual(p.dropped,0)

    def test_current_protected_final_ready_false_true_and_simultaneous_lanes(self):
        from test_btc15_directional_signal_authority_v1 import fixture
        for ready in (False,True):
            state=fixture(300,final_ready=ready,final_side='DOWN')
            state['scalp']={'source':'FROZEN_STRONG_SCALP','ready':True}
            before=deepcopy(state);self.p.protected(state,{'tier1_ready':True,'final_ready':ready,'scalp_ready':True})
            self.assertEqual(state,before);self.r.accept(self.sock.packets[-1])
        vals=[json.loads(r[1])['event']['body'] for r in self.rows()]
        self.assertEqual([v['state']['final']['ready'] for v in vals],[False,True])
        self.assertTrue(all(v['accepted_origin_id'] is None and v['completed_delivery_utc'] is None for v in vals))

    def test_actual_lifecycle_committed_origin_link_and_duplicate_equivalence(self):
        from btc15_directional_signal_authority_v1 import Authority,initialize as authority_initialize
        from btc15_qualified_forward_observer_v1 import observation
        from test_btc15_directional_signal_authority_v1 import fixture,START
        from datetime import timedelta
        import shutil
        a=self.root/'off.sqlite';b=self.root/'on.sqlite';authority_initialize(a,START)
        with sqlite3.connect(a) as left,sqlite3.connect(b) as right:left.backup(right)
        source=ROOT/'btc15_directional_signal_authority_v1.py'
        cls=detached_authority_class(source,digest(source.read_bytes()),self.p)
        off=Authority(a,runtime_epoch='synthetic',build={});on=cls(b,runtime_epoch='synthetic',build={})
        for t in (300,305,305,310):
            state=fixture(t,final_ready=t>=305,final_side='UP')
            now=START+timedelta(seconds=t);qualified=observation(state,now)
            expected=off.consume(state,qualified,now_utc=now,receipt_utc=now)
            actual=on.consume(state,qualified,now_utc=now,receipt_utc=now)
            self.assertEqual(actual,expected)
            captured=json.loads(self.sock.packets[-1])['event']['body']['emission']
            self.assertEqual(captured,actual)
            with sqlite3.connect(b) as db:self.assertEqual(json.loads(db.execute('SELECT payload FROM records ORDER BY seq DESC LIMIT 1').fetchone()[0]),actual)
        self.assertEqual(self.p.sequence,4)
        self.assertTrue(actual['origin_id'])
        self.assertEqual(actual['origin']['origin_id'],actual['origin_id'])

    def test_actual_common_append_hook_exact_member_no_get(self):
        source=(ROOT/'round2_evidence/references/observed_common_observer.py.txt').read_bytes()
        tree=instrument_common(source,digest(source));scope={'__name__':'common_test','_sprint_producer':self.p}
        exec(compile(tree,'frozen-common','exec'),scope)
        path=self.root/'common.gz';scope['append_record'](path,record())
        raw=path.read_bytes();self.assertEqual(json.loads(gzip.decompress(raw)),record())
        with patch.object(scope['requests'],'get',side_effect=AssertionError('no GET')):
            self.assertEqual(self.r.accept(self.sock.packets[-1])['status'],'RECORDED_UNQUALIFIED_CLOCK')
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT original FROM members').fetchone()[0],raw)


class ExactHooks(unittest.TestCase):
    def test_native_ast_off_exact_on_only_passive_insertions(self):
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        original=ast.parse(raw);off=instrument_native(raw,digest(raw),enabled=False)
        self.assertEqual(ast.dump(original),ast.dump(off))
        on=instrument_native(raw,digest(raw))
        calls=[n for n in ast.walk(on) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='_sprint_producer']
        self.assertEqual(len(calls),5) # fair input, success, 2 waits, one error
        class Strip(ast.NodeTransformer):
            def visit_Expr(self,n):
                if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='_sprint_producer':return None
                return self.generic_visit(n)
        self.assertEqual(ast.dump(Strip().visit(on)),ast.dump(original))
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):instrument_native(raw,'f'*64)

    def test_exact_packaged_protected_build_off_on_with_missing_inputs(self):
        from test_btc15_canary_data_path_static import load_sources
        source=load_sources()[0]['BTC15_DASHBOARD_STATE_V2.py'].encode()
        sock=MemorySocket();p=Producer('none',IDENTITY,KEY,sock=sock)
        a={'__name__':'off','__file__':str(ROOT/'BTC15_DASHBOARD_STATE_V2.py')}
        b={'__name__':'on','__file__':str(ROOT/'BTC15_DASHBOARD_STATE_V2.py'),'_sprint_producer':p}
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'BTC15_DATA_DIR':d}):
            exec(compile(instrument_protected(source,digest(source),enabled=False),'off','exec'),a)
            exec(compile(instrument_protected(source,digest(source)),'on','exec'),b)
            # Empty input paths truthfully cause no eligible gates. Freeze the
            # source's current clock to compare identical protected generations.
            from datetime import datetime,timezone
            class FixedDate(datetime):
                @classmethod
                def now(cls,*args,**kwargs):return cls(2026,9,29,tzinfo=timezone.utc)
            a['datetime']=b['datetime']=FixedDate
            expected=a['build_state']();actual=b['build_state']()
        self.assertEqual(actual,expected);self.assertEqual(len(sock.packets),1)
        observed=json.loads(sock.packets[0])['event']['body']
        self.assertEqual(observed['state'],actual)
        self.assertEqual(observed['state']['final']['source'],'FROZEN_V4_6_FINAL')
        self.assertEqual(observed['gate_values']['final_ready'],actual['final']['ready'])

    def test_frozen_native_complete_behavior_identical_with_capture_on_wait_rollover(self):
        from completion_audit.isolated_decision_v2 import FrozenRuntime,stable
        from test_btc15_isolated_decision_v2 import completed,fixture,TICKER
        initial=FrozenRuntime(completed());off,on=initial.fork(),initial.fork()
        p=Producer('absent',IDENTITY,KEY,sock=MemorySocket())
        # Execute the actual transformed native while-loop, not a manual hook
        # after the oracle. Callable test holder is excluded as an adapter from
        # the oracle's strategy-state inventory, like its original clocks.
        proxy=lambda:None
        proxy.native=p.native
        proxy.fair_input=p.fair_input
        on.ns['_sprint_producer']=proxy
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        tree=instrument_native(raw,digest(raw))
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        on.loop=compile(ast.Module(body=[loop],type_ignores=[]),'instrumented-native','exec')
        fair=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_live_fair_shadow')
        exec(compile(ast.Module(body=[fair],type_ignores=[]),'instrumented-native-fair','exec'),on.ns)
        for i,at in enumerate((300,304.75,305,310,315,895,901,906)):
            inp=fixture(at,ask=(.31,.79,.42)[i%3],btc=100000+(-1)**i*85,
                quote_wait=i==3,brti_delay=(4.999999,5.000001,2.4)[i%3],ticker=TICKER if at<900 else 'KXBTC15M-19DEC311930-15')
            expected=off.step(inp);actual=on.step(inp)
            self.assertEqual(stable(actual),stable(expected))
            self.assertEqual(stable(on.snapshot()),stable(off.snapshot()))
        self.assertEqual(p.sequence,12)
        fairs=[json.loads(x)['event'] for x in p.sock.packets if json.loads(x)['event']['kind']=='NATIVE_FAIR_INPUT']
        self.assertEqual(len(fairs),4)
        self.assertTrue(all(x['body']['features'] for x in fairs))

    def test_strict_ask_then_later_bid_remains_existing_gate(self):
        from round2_evidence.chronology import later_gain
        from round2_evidence.test_round2 import origin,stamp
        from test_btc15_external_evidence_admission_v1 import bound
        o=origin(t=300);q={'contract':o['contract'],'observed_utc':stamp(300),'up_bid':'0.40'}
        for at in (299,300):
            q['observed_utc']=stamp(at)
            with self.assertRaisesRegex(ValueError,'QUOTE_ORDER_UNAVAILABLE'):
                later_gain(o,q,origin_bound=bound('o'),quote_bound=bound('q'))
        q['observed_utc']=stamp(300.000001)
        self.assertEqual(str(later_gain(o,q,origin_bound=bound('o'),quote_bound=bound('q'))),'11.00')
        with self.assertRaisesRegex(ValueError,'QUOTE_ORDER_UNAVAILABLE'):
            later_gain(o,q,origin_bound=bound('o',error=400000),quote_bound=bound('q',error=400000))

    def test_exact_scheduler_475_boundary_remains_negative(self):
        from types import SimpleNamespace
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        tree=ast.parse(raw)
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        nodes=[n for n in loop.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('elapsed','sleep_for') for t in n.targets)]
        code=compile(ast.Module(body=nodes,type_ignores=[]),'exact-scheduler','exec')
        def next_at(work):
            ns={'time':SimpleNamespace(time=lambda:work),'cycle_start':0,'POLL_SECONDS':5}
            exec(code,ns);return work+ns['sleep_for']
        # Positive hook work remains a true failure of universal wall-clock
        # equivalence. Test does not introduce an epsilon or widen freshness.
        self.assertEqual(next_at(4.75),5)
        self.assertGreater(next_at(4.75+.000001),5)
        self.assertEqual(next_at(4.5+.000001),5)
        age=4.9999995;added=.000001
        self.assertTrue(age<=5);self.assertFalse(age+added<=5)

    def test_generation_publication_explicit_same_object_immutable_link(self):
        sock=MemorySocket();p=Producer('none',IDENTITY,KEY,sock=sock)
        state={'contract':'A','final':{'ready':False}}
        self.assertTrue(p.protected(state,{}));self.assertTrue(p.published(state))
        generation=json.loads(sock.packets[0])['event']['body'];published=json.loads(sock.packets[1])['event']['body']
        self.assertEqual(generation['generation_id'],published['generation_id'])
        self.assertEqual(published['linkage_status'],'OBSERVED_SAME_OBJECT_UNCHANGED')
        self.assertIsNone(published['browser_delivery_utc'])
        p.published(deepcopy(state));self.assertIsNone(json.loads(sock.packets[-1])['event']['body']['generation_id'])
        state['final']['ready']=True;p.published(state)
        self.assertIsNone(json.loads(sock.packets[-1])['event']['body']['generation_id'])

if __name__=='__main__':unittest.main()
