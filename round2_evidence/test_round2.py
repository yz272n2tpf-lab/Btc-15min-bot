"""Synthetic offline controls. No live URLs, clock claims or signal generation."""
from copy import deepcopy
from dataclasses import asdict,replace
from decimal import Decimal
import gzip,hashlib,hmac,json,sqlite3,tempfile,unittest,ast,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from btc15_directional_signal_authority_v1 import pack
from btc15_external_evidence_admission_v1 import seal_member,MAX_COMPRESSED
from test_btc15_external_evidence_admission_v1 import POLICY,KEY,stamp,bound
from test_btc15_directional_signal_authority_v1 import fixture
from round2_evidence.capture import DetachedRecorder,initialize,normalize,validate
from round2_evidence.contract import FIELDS,PRODUCERS,SCHEMA
from round2_evidence.chronology import EventAudit,final_relation,later_gain
from round2_evidence.clock_receipts import CertificateRegistry

def record(seq=1,sec=300):
    return dict(schema_version=1,record_type='OBSERVATION',run_id=POLICY.run_id,observer_epoch=POLICY.observer_epoch,
      sequence_in_process=seq,recorded_utc=stamp(sec+.25),sampling_seconds=1.0,orders=False,signal_only=True,
      sources=[dict(service='main',http_status=200,request_started_utc=stamp(sec+.05),response_received_utc=stamp(sec+.2),state=fixture(sec))])
def artifact(r=None,seq=1,offset=0,data=None,policy=POLICY):
    data=gzip.compress((pack(r or record(seq))+'\n').encode(),mtime=0) if data is None else data
    return data,seal_member(data,policy,offset=offset,sequence=seq,clock_refs={'native':'N','collector':'O'},key=KEY)
def event(lane,kind,eid,t=300,**kw):
    return dict(lane=lane,kind=kind,event_id=eid,producer_id=lane,observed_utc=stamp(t),runtime_epoch='SYNTHETIC_EPOCH',contract='CONTRACT_A',**kw)
def origin(lane='SCALP',oid='s1',t=300,**kw):
    defaults=dict(side='UP',original_ask='0.29',original_bid='0.28',quote_id='q0',origin_evidence_id='evidence0')
    if lane=='SCALP':defaults.update(lane_label='FIRST',evidence_role='SHADOW',lifecycle_sequence=0,initial_state='UNARMED')
    defaults.update(kw)
    return event(lane,lane+'_ORIGIN',oid,t,origin_id=oid,**defaults)
def transition(kind='SCALP_ARM',eid='arm1',t=301,**kw):
    defaults=dict(origin_id='s1',evidence_role='SHADOW',lifecycle_sequence=1,prior_state='UNARMED',next_state='ARMED',user_guidance=False)
    defaults.update(kw);return event('SCALP',kind,eid,t,**defaults)

class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'evidence.sqlite'
        initialize(self.path,POLICY);self.r=DetachedRecorder(self.path,POLICY,acquisition_key=KEY)
    def tearDown(self):self.tmp.cleanup()
    def rows(self):
        with sqlite3.connect(self.path) as db:return db.execute('SELECT seq,digest FROM members').fetchall()
    def test_complete_map_and_schema_producer_bindings(self):
        self.assertEqual(len(FIELDS),len({f['field'] for f in FIELDS}));self.assertTrue(all(f['producer'] in PRODUCERS for f in FIELDS))
        out=normalize(record(),'synthetic');validate(out)
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(SCHEMA);jsonschema.validate(out,SCHEMA)
        for f in FIELDS:
            if f['source_path'] is None:self.assertEqual(out['fields'][f['field']]['status'],'UNAVAILABLE')
        wrong=deepcopy(out);wrong['fields']['final.side']['producer']='SCALP_ORIGIN_EVENT_STREAM'
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(wrong,SCHEMA)
    def test_requirements_and_future_partition_freeze(self):
        root=Path(__file__).parent;p=json.loads((root/'protocol.json').read_text());rows=json.loads((root/'requirements_crosswalk.json').read_text())
        self.assertIsNone(p['capture_start_utc']);self.assertFalse(p['production_capture_authorized'])
        self.assertEqual([(x['open_day_inclusive'],x['open_day_exclusive']) for x in p['partitions']],[(0,21),(21,35),(35,56)])
        self.assertFalse(any(x['status']=='UNAVAILABLE_REQUIREMENT' for x in rows))
        side=next(x for x in rows if x['source']=='FINAL_CAPTURE_SPEC' and x['section']=='research_origin' and x['requirement']=='side')
        self.assertEqual(side['mapped_fields'],'early.original_side')
        linked=[x for x in rows if x['section']=='immutable_accepted_origin_if_one_exists']
        self.assertTrue(all(x['mapped_fields']=='early.origin_record' for x in linked))
    def test_original_bytes_persist_exactly_and_restart_continuity(self):
        a=artifact();self.assertEqual(self.r.accept(*a)['status'],'RECORDED_PARTIAL')
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT original FROM members').fetchone()[0],a[0])
        r=DetachedRecorder(self.path,POLICY,acquisition_key=KEY)
        self.assertEqual(r.accept(*a)['status'],'DUPLICATE_RECORDED')
        self.assertEqual(r.accept(*artifact(seq=2,offset=len(a[0])))['status'],'RECORDED_PARTIAL')
        self.assertEqual(len(self.rows()),2)
    def test_replay_conflict_gap_and_backlog_do_not_advance(self):
        a=artifact();self.r.accept(*a);before=self.rows()
        for kwargs in [dict(seq=3,offset=len(a[0])),dict(seq=1,r=record(sec=301)),dict(seq=10000,offset=9999999)]:
            self.assertEqual(self.r.accept(*artifact(**kwargs))['status'],'UNAVAILABLE');self.assertEqual(self.rows(),before)
        self.assertEqual(self.r.accept(*artifact(seq=2,offset=len(a[0])))['status'],'RECORDED_PARTIAL')
    def test_tamper_build_run_epoch_authentication(self):
        for p in [replace(POLICY,run_id='OTHER'),replace(POLICY,observer_epoch='B'),replace(POLICY,collector_commit='wrong'),replace(POLICY,stream_id='wrong')]:
            self.assertEqual(self.r.accept(*artifact(policy=p))['status'],'UNAVAILABLE')
        data,env=artifact();env=json.loads(env);env['mac']='0'*64
        self.assertEqual(self.r.accept(data,pack(env).encode())['status'],'UNAVAILABLE');self.assertFalse(self.rows())
    def test_malformed_oversized_truncated_and_multiple_members(self):
        good=artifact()[0]
        for data in [b'',b'x'*(MAX_COMPRESSED+1),good[:-3],good+good,b'not gzip',gzip.compress(b'{"x":NaN}\n')]:
            with self.subTest(length=len(data)):
                if 0<len(data)<=MAX_COMPRESSED:
                    try:a=artifact(data=data)
                    except ValueError:continue # frozen sealer rejects the artifact before consumer
                    result=self.r.accept(*a)
                else:result=self.r.accept(data,b'{}')
                self.assertEqual(result['status'],'UNAVAILABLE')
        self.assertFalse(self.rows())
    def test_invalid_final_is_not_startup_substitute(self):
        for val in [None,[],[1],'bad',{'source':'startup','ready':True,'side':'UP'}]:
            r=record();r['sources'][0]['state']['final']=val;r['sources'][0]['state']['_two_final_side']='UP'
            out=normalize(r,'x');self.assertEqual(out['fields']['final.final']['status'],'UNAVAILABLE')
    def test_wait_and_recovery_and_simultaneous_lane_objects(self):
        r=record();r['sources'] += [dict(service=s,http_status=200,state={'sentinel':s}) for s in ('owner','v81','serial')]
        self.assertEqual(self.r.accept(*artifact(r))['status'],'RECORDED_PARTIAL')
        r['sources'][0]['http_status']=503;r['sources'][0]['error_type']='WAIT'
        out=normalize(r,'x');self.assertEqual(out['coverage'],'SOURCE_ERROR_OR_WAIT');self.assertIsNone(out['guidance'])
        r['sources'][1]['http_status']=500
        self.assertEqual(normalize(r,'x')['fields']['shared.owner_state']['status'],'UNAVAILABLE')
        r['sources'][0]['http_status']=200;r['sources'][0].pop('error_type')
        self.assertEqual(normalize(r,'x')['fields']['early.early']['status'],'OBSERVED')
    def test_storage_locked_full_crash_and_network_absence(self):
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN EXCLUSIVE')
            self.assertEqual(self.r.accept(*artifact())['status'],'UNAVAILABLE')
        with patch.object(self.r,'_db',side_effect=sqlite3.OperationalError('disk is full')):
            self.assertEqual(self.r.accept(*artifact())['status'],'UNAVAILABLE')
        with patch.object(self.r,'_db',side_effect=OSError('consumer store disconnected')):
            self.assertEqual(self.r.accept(*artifact())['status'],'UNAVAILABLE')
        self.assertFalse(self.rows());self.assertEqual(self.r.accept(*artifact())['status'],'RECORDED_PARTIAL')
    def test_quota_is_bounded_and_missing_store_never_recreated(self):
        with sqlite3.connect(self.path) as db:db.execute("UPDATE meta SET v='32768' WHERE k='quota'")
        self.assertEqual(self.r.accept(*artifact())['status'],'UNAVAILABLE')
        self.path.unlink();self.assertEqual(self.r.accept(*artifact())['status'],'UNAVAILABLE');self.assertFalse(self.path.exists())
    def test_abrupt_consumer_exit_mid_transaction_rolls_back_without_upstream(self):
        data,env=artifact();root=Path(self.tmp.name);(root/'member').write_bytes(data);(root/'manifest').write_bytes(env)
        script='''import os,sqlite3,sys
from pathlib import Path
from round2_evidence.capture import DetachedRecorder
from test_btc15_external_evidence_admission_v1 import POLICY,KEY
class CrashConnection(sqlite3.Connection):
 def execute(self,sql,*args,**kw):
  result=super().execute(sql,*args,**kw)
  if sql.startswith('UPDATE meta'):os._exit(73)
  return result
root=Path(sys.argv[1]);r=DetachedRecorder(root/'evidence.sqlite',POLICY,acquisition_key=KEY)
r._db=lambda: sqlite3.connect(root/'evidence.sqlite',factory=CrashConnection)
r.accept((root/'member').read_bytes(),(root/'manifest').read_bytes())
'''
        r=subprocess.run([sys.executable,'-B','-c',script,str(root)],capture_output=True,timeout=10)
        self.assertEqual(r.returncode,73,r.stderr);self.assertFalse(self.rows())
        self.assertEqual(self.r.accept(data,env)['status'],'RECORDED_PARTIAL')
    def test_archive_is_immutable(self):
        self.r.accept(*artifact())
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM members')
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE members SET digest='bad'")
    def test_passive_consumer_absent_no_network_callback_or_authority(self):
        before=deepcopy(record());expected=deepcopy(before)
        # With no invocation there is no consumer process or write on producer path.
        self.assertEqual(before,expected)
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.r.accept(*artifact(before))
        self.assertEqual(before,expected)
        for name in ('capture.py','chronology.py','clock_receipts.py'):
            tree=ast.parse((Path(__file__).parent/name).read_text())
            imported={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}
            self.assertFalse(imported & {'requests','socket','urllib','subprocess'})
        self.assertFalse(any('round2_evidence' in p.read_text(errors='ignore') for p in Path('.').glob('btc15_*.py')))

class EventTests(unittest.TestCase):
    def setUp(self):self.a=EventAudit(producer_ids={s:s for s in ('EARLY','FINAL','SCALP','SHARED')})
    def test_immutable_origins_and_replays(self):
        o=origin();self.a.accept(o);self.assertEqual(self.a.accept(o),'DUPLICATE')
        x=deepcopy(o);x['side']='DOWN'
        with self.assertRaises(ValueError):self.a.accept(x)
        x['event_id']='new'
        with self.assertRaises(ValueError):self.a.accept(x)
        self.assertEqual(self.a.origins['s1'],o)
    def test_explicit_final_link_ready_vs_not_ready_and_no_exit(self):
        self.a.accept(origin('EARLY','e1'))
        for ready in (False,True):
            f=fixture(300,final_side='DOWN',final_ready=ready)['final']
            self.assertEqual(final_relation(f,self.a.origins['e1']),'OPPOSING_READY' if ready else 'OPPOSING_NOT_READY')
        self.a.accept(event('FINAL','FINAL_PUBLICATION','f1',301,origin_id='e1',explicit_link_evidence_id='real-link-required'))
        for e in [event('FINAL','FINAL_PUBLICATION','f2',302,origin_id='e1'),event('FINAL','EXIT','f3',302),event('EARLY','EXIT','e2',302)]:
            with self.assertRaises(ValueError):self.a.accept(e)
        self.assertEqual(len(self.a.origins),1)
    def test_rollover_and_cross_lane_ownership(self):
        self.a.accept(origin());self.a.accept(origin('EARLY','e1'))
        e=event('FINAL','FINAL_PUBLICATION','f',301,origin_id='s1',explicit_link_evidence_id='bad')
        with self.assertRaises(ValueError):self.a.accept(e)
        e=transition();e['contract']='CONTRACT_B'
        with self.assertRaises(ValueError):self.a.accept(e)
        e=transition();e['origin_id']='e1'
        with self.assertRaises(ValueError):self.a.accept(e)
    def test_lifecycle_gap_and_recovery_preserves_origin(self):
        self.a.accept(origin());o=deepcopy(self.a.origins)
        with self.assertRaises(ValueError):self.a.accept(transition(lifecycle_sequence=2))
        self.assertEqual(self.a.origins,o);self.assertEqual(self.a.lifecycle['s1'],(0,'UNARMED'))
        self.a.accept(transition());self.assertEqual(self.a.lifecycle['s1'],(1,'ARMED'))
    def test_retirement_is_not_exit_serial_explicit_policy(self):
        self.a.accept(origin())
        bad=transition('SCALP_RETIREMENT_UNARMED','r',301,exit_bid='0.31')
        with self.assertRaises(ValueError):self.a.accept(bad)
        self.a.accept(transition('SCALP_RETIREMENT_UNARMED','r',301,next_state='RETIRED'))
        o=origin(oid='s2',t=302,side='DOWN',lane_label='REVERSAL',prior_signal_id='s1',prior_terminal_event_id='r')
        with self.assertRaises(ValueError):self.a.accept(o)
        o['serial_policy']='ALLOW_UNARMED_RETIREMENT';self.a.accept(o)
        self.assertEqual(len(self.a.origins),2);self.assertNotIn('exit_bid',self.a.terminals['r'])
    def test_shadow_exit_cannot_be_user_guidance(self):
        self.a.accept(origin())
        e=transition('SCALP_SHADOW_EXIT','x',301,trigger_quote_id='q1',exit_bid='0.32',user_guidance=True)
        with self.assertRaises(ValueError):self.a.accept(e)
        e['user_guidance']=False;self.a.accept(e)
        n=origin(oid='s2',t=302,prior_signal_id='s1',prior_terminal_event_id='x',lane_label='CONTINUATION',evidence_role='USER_GUIDANCE')
        with self.assertRaises(ValueError):self.a.accept(n)
    def test_overlap_without_terminal_and_event_order_are_unavailable(self):
        self.a.accept(origin())
        with self.assertRaises(ValueError):self.a.accept(origin(oid='s2',t=301))
        with self.assertRaises(ValueError):self.a.accept(transition(t=299))
    def test_exact_later_bid_no_ask_no_future_max(self):
        o=origin();q=dict(contract='CONTRACT_A',observed_utc=stamp(301),up_bid='0.39',up_ask='0.90')
        self.assertEqual(later_gain(o,q,origin_bound=bound('a'),quote_bound=bound('b')),Decimal('10.00'))
        q['observed_utc']=stamp(300)
        with self.assertRaises(ValueError):later_gain(o,q,origin_bound=bound('a'),quote_bound=bound('b'))
        q['observed_utc']=stamp(300.1)
        with self.assertRaises(ValueError):later_gain(o,q,origin_bound=bound('a',error=400000),quote_bound=bound('b',error=400000))
    def test_quiet_wait_gap_reconnect_population_not_signal_only(self):
        for i,k in enumerate(('CONTRACT_ELIGIBLE','WAIT','GAP','RECOVERY','CLOSEOUT')):
            self.a.accept(event('SHARED',k,str(i),300+i))
        self.a.accept(event('SCALP','SCALP_NO_SIGNAL','quiet',306))
        self.a.accept(event('EARLY','EARLY_REJECTED','rejected',306))
        self.assertEqual(len(self.a.population['CONTRACT_A']),7);self.assertFalse(self.a.origins)

class ClockTests(unittest.TestCase):
    def setUp(self):self.r=CertificateRegistry(trusted_keys={'monitor':KEY},domains={'clock':{'signer_id':'monitor','runtime_epoch':'runtime-A'}})
    def packet(self,seq=1,**kw):
        body=dict(bound=asdict(bound('clock')),signer_id='monitor',runtime_epoch='runtime-A',synthetic=True,monitor_sequence=seq,state='HEALTHY',step_detected=False,suspension_unknown=False,
          reference_identity='SYNTHETIC_REFERENCE',offset_bound_evidence='SYNTHETIC',rate_bound_evidence='SYNTHETIC',read_bound_evidence='SYNTHETIC',epoch_continuity_evidence='SYNTHETIC')
        body.update(kw);return dict(body=body,mac=hmac.new(KEY,pack(body).encode(),hashlib.sha256).hexdigest())
    def test_expiry_unknown_and_authentication(self):
        b=self.r.ingest(self.packet(),now_utc=stamp(300));self.r.at(b.measurement_id,stamp(301))
        for mid,t in [(b.measurement_id,stamp(3601)),('unknown',stamp(301))]:
            with self.assertRaises(ValueError):self.r.at(mid,t)
        p=self.packet(2);p['mac']='bad'
        with self.assertRaises(ValueError):self.r.ingest(p,now_utc=stamp(300))
    def test_step_suspension_revocation_origin_independent(self):
        b=self.r.ingest(self.packet(),now_utc=stamp(300))
        with self.assertRaises(ValueError):self.r.ingest(self.packet(2,step_detected=True),now_utc=stamp(301))
        with self.assertRaises(ValueError):self.r.at(b.measurement_id,stamp(301))
        with self.assertRaises(ValueError):self.r.ingest(self.packet(3,suspension_unknown=True),now_utc=stamp(302))
    def test_missing_premise_replay_runtime_restart_and_live_mode_blocked(self):
        for p in [self.packet(offset_bound_evidence=''),self.packet(runtime_epoch='new'),self.packet(synthetic=False)]:
            with self.assertRaises(ValueError):self.r.ingest(p,now_utc=stamp(300))
        self.r.ingest(self.packet(),now_utc=stamp(300))
        with self.assertRaises(ValueError):self.r.ingest(self.packet(),now_utc=stamp(300))
        self.r.synthetic_only=False
        with self.assertRaisesRegex(ValueError,'LIVE_CLOCK_PRODUCER_NOT_QUALIFIED'):self.r.ingest(self.packet(2,synthetic=False),now_utc=stamp(300))

if __name__=='__main__':unittest.main()
