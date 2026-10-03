"""Synthetic detached artifacts only. No live HTTP, credentials or journal."""
from dataclasses import replace
from datetime import timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from btc15_directional_signal_authority_v1 import initialize,pack
from test_btc15_directional_signal_authority_v1 import fixture,START
from btc15_external_clock_guard_v1 import Bound,elapsed,range_truth
import btc15_external_evidence_admission_v1 as mod

KEY=b'SYNTHETIC_ACQUISITION_KEY_ONLY_000000'
TOKEN=b'SYNTHETIC_READER_CREDENTIAL_00000000'
POLICY=mod.Policy('https://scalp-finalprod-clean-v1-production.up.railway.app/research/common-export',
    'b369287c-d8a1-4427-84de-25e39fe9fdf7','SYNTHETIC_RUN','SYNTHETIC_OBSERVER_EPOCH',
    'e98576f23e247349b90717aea3a3ad832d409354','a'*64,(('collector.py','b'*64),),
    'SYNTHETIC_APPROVED_ACQUIRER','SYNTHETIC_STREAM')


def stamp(seconds):return (START+timedelta(seconds=seconds)).isoformat()


def bound(clock,epoch='clock-epoch',error=0,rate=0):
    return Bound(clock,epoch,'SYNTHETIC_MEASUREMENT:'+clock,stamp(0),stamp(0),stamp(3600),error,rate)


class Clock:
    def __init__(self):
        self.seconds=300.3;self.boot=300_300_000_000;self.epoch='consumer-A'
        self.bound=bound('consumer',self.epoch);self.healthy=True
    def at(self,seconds):self.seconds=seconds;self.boot=round(seconds*1e9)
    def __call__(self):return mod.Sample(stamp(self.seconds),self.boot,self.epoch,self.bound,self.healthy)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.ledger=self.root/'ledger';self.checkpoint=self.root/'checkpoint'
        initialize(self.ledger,START);mod.initialize_checkpoint(self.checkpoint,POLICY)
        self.clock=Clock();self.registry={'N':bound('native'),'O':bound('collector')}
        self.a=self.new();self.offset=0;self.seq=1

    def tearDown(self):self.tmp.cleanup()

    def new(self):
        return mod.Admission(self.ledger,self.checkpoint,POLICY,acquisition_key=KEY,
            reader_credential=TOKEN,clock_provider=self.clock,clock_registry=self.registry,
            activation_bound=bound('consumer','activation'),runtime_epoch=self.clock.epoch,artifact_root=self.root)

    def state(self):
        with sqlite3.connect(self.ledger) as db:
            return (db.execute("SELECT value FROM meta WHERE key='state'").fetchone()[0],
                    db.execute('SELECT payload FROM origins ORDER BY contract').fetchall())

    def record(self,sec=300,**kw):
        raw=fixture(sec,**kw);raw['generated_utc']=stamp(sec+.1)
        source=dict(service='main',request_started_utc=stamp(sec+.05),response_received_utc=stamp(sec+.2),
                    http_status=200,state=raw)
        return dict(schema_version=1,record_type='OBSERVATION',run_id=POLICY.run_id,
                    observer_epoch=POLICY.observer_epoch,sequence_in_process=self.seq,
                    recorded_utc=stamp(sec+.25),sources=[source],sampling_seconds=1.0,
                    actual_browser_delivery_verified=False,signal_only=True,orders=False)

    def artifact(self,record=None,data=None):
        data=gzip.compress((pack(record or self.record())+'\n').encode(),mtime=0) if data is None else data
        path=self.root/f'member-{self.seq}-{self.offset}'
        path.write_bytes(data)
        env=mod.seal_member(data,POLICY,offset=self.offset,sequence=self.seq,
                            clock_refs={'native':'N','parity':'N','collector':'O'},key=KEY)
        self.offset+=len(data);self.seq+=1
        return path,env

    def consume(self,sec=300,**kw):
        self.clock.at(sec+.3)
        return self.a.consume(*self.artifact(self.record(sec,**kw)),credential=TOKEN)

    def assertBlocked(self,result,before):
        self.assertEqual(result['status'],'UNAVAILABLE',result)
        self.assertIsNone(result['guidance']);self.assertEqual(self.state(),before)

    def test_interior_buy_hold_protect_latched_and_immutable(self):
        buy=self.consume(final_ready=True);self.assertEqual(buy['accepted_event'],'BUY',buy)
        original=self.state()[1]
        self.assertEqual(self.consume(301,final_ready=True)['guidance'],'HOLD')
        self.assertEqual(self.consume(302,final_ready=True,final_side='DOWN')['guidance'],'PROTECT')
        self.assertEqual(self.consume(303,final_ready=True)['guidance'],'PROTECT')
        self.assertEqual(self.state()[1],original)
        self.assertFalse(self.a.view(credential=TOKEN)['orders_enabled'])

    def test_wrong_reader_credential_does_not_touch_any_storage(self):
        before=self.state();p,e=self.artifact()
        with patch.object(self.a,'_db',side_effect=AssertionError('must not open')):
            self.assertBlocked(self.a.consume(p,e,credential=b'wrong'),before)
        self.assertIsNone(self.a.view(credential=b'wrong')['origin_id'])

    def test_wrong_acquisition_signature(self):
        before=self.state();p,e=self.artifact();v=json.loads(e);v['mac']='0'*64
        self.assertBlocked(self.a.consume(p,pack(v).encode(),credential=TOKEN),before)

    def test_signed_wrong_host_run_build_manifest_epoch_and_service(self):
        for field,value in [('endpoint','https://evil.invalid/redirect'),('service_id','wrong'),
            ('run_id','wrong'),('collector_commit','0'*40),('run_manifest_sha256','0'*64),
            ('observer_epoch','different'),('fingerprints',{})]:
            with self.subTest(field=field):
                # Use a fresh fixture per attempted first-member substitution.
                self.offset=0;self.seq=1;p,e=self.artifact();v=json.loads(e)
                v['manifest'][field]=value;v['mac']=mod.signature(v['manifest'],KEY)
                before=self.state();self.assertBlocked(self.a.consume(p,pack(v).encode(),credential=TOKEN),before)

    def test_modified_bytes_even_with_new_unkeyed_digest(self):
        p,e=self.artifact();v=json.loads(e);data=p.read_bytes()+b'X';p.write_bytes(data)
        v['manifest']['sha256']=hashlib.sha256(data).hexdigest()
        self.assertBlocked(self.a.consume(p,pack(v).encode(),credential=TOKEN),self.state())

    def test_duplicate_member_and_repeated_native_publication(self):
        p,e=self.artifact();first=self.a.consume(p,e,credential=TOKEN)
        self.assertEqual(first['accepted_event'],'BUY')
        before=self.state();self.assertBlocked(self.a.consume(p,e,credential=TOKEN),before)
        second=self.record();second['sources'][0]['state']['generated_utc']=stamp(300.15)
        out=self.a.consume(*self.artifact(second),credential=TOKEN)
        self.assertIsNone(out['accepted_event']);self.assertEqual(self.state()[1],before[1])
        with sqlite3.connect(self.ledger) as db:
            events=[json.loads(x[0])['event'] for x in db.execute('SELECT payload FROM records')]
        self.assertEqual(events.count('BUY'),1)

    def test_replay_gap_and_run_switch_fail_closed(self):
        self.consume();before=self.state();p,e=self.artifact(self.record(301));v=json.loads(e)
        v['manifest']['sequence']+=1;v['mac']=mod.signature(v['manifest'],KEY)
        self.assertBlocked(self.a.consume(p,pack(v).encode(),credential=TOKEN),before)

    def test_missing_or_duplicate_main_and_forged_label(self):
        for mode in ('missing','duplicate','forged'):
            with self.subTest(mode=mode):
                r=self.record();main=r['sources'][0]
                if mode=='missing':r['sources']=[]
                if mode=='duplicate':r['sources']=[main,main]
                if mode=='forged':main['service']='fake_main'
                self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),self.state())

    def test_unknown_clock_bound_and_wrong_role(self):
        for ref in ('UNKNOWN','O'):
            r=self.record();p,e=self.artifact(r);v=json.loads(e)
            v['manifest']['clock_refs']['native']=ref;v['mac']=mod.signature(v['manifest'],KEY)
            self.assertBlocked(self.a.consume(p,pack(v).encode(),credential=TOKEN),self.state())

    def test_400ms_false_hold_rejected(self):
        self.consume();before=self.state();self.clock.bound=replace(self.clock.bound,error_us=400000)
        self.clock.at(309.8)
        out=self.a.consume(*self.artifact(self.record(305,final_ready=True)),credential=TOKEN)
        self.assertBlocked(out,before);self.assertIn('UNCERTAIN',out['reason'])

    def test_uncertain_confirmation_latch_cannot_create_buy(self):
        before=self.state();self.clock.bound=replace(self.clock.bound,error_us=400000)
        self.clock.at(304.8)
        self.assertBlocked(self.a.consume(*self.artifact(self.record(final_ready=True)),credential=TOKEN),before)

    def test_expired_bound_and_unhealthy_monitor(self):
        for mode in ('expired','unhealthy'):
            self.a=self.new();self.clock.healthy=True;self.clock.bound=bound('consumer',self.clock.epoch)
            if mode=='expired':self.clock.bound=replace(self.clock.bound,valid_until_utc=stamp(299))
            else:self.clock.healthy=False
            self.assertBlocked(self.a.consume(*self.artifact(),credential=TOKEN),self.state())

    def test_clock_step_latches_unavailable(self):
        self.consume();before=self.state();self.clock.seconds+=.01 # BOOTTIME did not advance
        self.assertBlocked(self.a.view(credential=TOKEN),before)
        self.clock.at(301.3)
        self.assertBlocked(self.a.consume(*self.artifact(self.record(301)),credential=TOKEN),before)

    def test_restart_requires_new_clock_epoch_and_new_admission(self):
        self.consume();before=self.state();self.clock.epoch='consumer-B'
        self.a=self.new() # supplied old bound cannot masquerade as new epoch
        self.assertBlocked(self.a.view(credential=TOKEN),before)
        self.clock.at(301.3)
        self.assertBlocked(self.a.consume(*self.artifact(self.record(301)),credential=TOKEN),before)

    def test_valid_restart_with_linked_history(self):
        self.consume();original=self.state()[1]
        self.clock.epoch='consumer-B';self.clock.bound=bound('consumer','consumer-B')
        self.a=self.new()
        self.assertEqual(self.consume(301,final_ready=True)['guidance'],'HOLD')
        self.assertEqual(original,self.state()[1])

    def test_suspension_elapsed_included_and_stale_backlog(self):
        self.consume();before=self.state();self.clock.at(600)
        self.assertBlocked(self.a.consume(*self.artifact(self.record(301)),credential=TOKEN),before)
        self.assertBlocked(self.a.view(credential=TOKEN),before)

    def test_drift_grows_uncertainty(self):
        b=bound('x',error=10,rate=100)
        early=b.witness(stamp(1));late=b.witness(stamp(100))
        self.assertGreater(late.hi-late.lo,early.hi-early.lo)
        self.assertGreater(elapsed(late,early)[0],0)

    def test_asymmetric_delays_do_not_use_rtt_midpoint(self):
        r=self.record();r['sources'][0]['request_started_utc']=stamp(299)
        r['sources'][0]['response_received_utc']=stamp(302)
        self.clock.at(302.3)
        out=self.a.consume(*self.artifact(r),credential=TOKEN)
        self.assertEqual(out['accepted_event'],'BUY')
        self.assertEqual(out['origin']['observer_received_utc'],stamp(302))

    def test_wait_and_missing_final_preserve_origin_then_recovery(self):
        self.consume();before=self.state();r=self.record(301);r['sources'][0].pop('state')
        r['sources'][0]['error_type']='Timeout'
        self.clock.at(301.3);self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)
        r=self.record(302);r['sources'][0]['state']['final']={};self.clock.at(302.3)
        self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)
        self.assertEqual(self.consume(303,final_ready=True)['guidance'],'HOLD')

    def test_final_cannot_buy_and_missing_final_does_not_add_entry_gate(self):
        self.assertEqual(self.consume(300,early_ready=False,final_ready=True)['status'],'PASS')
        r=self.record(301);r['sources'][0]['state']['final']={};self.clock.at(301.3)
        self.assertEqual(self.a.consume(*self.artifact(r),credential=TOKEN)['accepted_event'],'BUY')

    def test_every_partial_member_prefix(self):
        full=gzip.compress((pack(self.record())+'\n').encode(),mtime=0)
        for n in range(1,len(full)):
            with self.subTest(prefix=n):
                with self.assertRaises((ValueError,mod.zlib.error)):mod.parsed_member(full[:n])

    def test_crc_trailing_and_multiple_members(self):
        full=gzip.compress((pack(self.record())+'\n').encode(),mtime=0)
        corrupt=bytearray(full);corrupt[-8]^=1
        for data in (bytes(corrupt),full+b'junk',full+full):
            with self.assertRaises((ValueError,mod.zlib.error)):mod.parsed_member(data)

    def test_malformed_duplicate_key_nonfinite_and_deep_json(self):
        for raw in (b'{bad}\n',b'{"a":1,"a":2}\n',b'{"a":NaN}\n',b'{"a":1e999}\n',b'['*34+b'0'+b']'*34+b'\n'):
            with self.assertRaises((ValueError,RecursionError)):
                mod.parsed_member(gzip.compress(raw,mtime=0))

    def test_decompression_and_compressed_bounds(self):
        with self.assertRaises(ValueError):mod.parsed_member(gzip.compress(b' '* (mod.MAX_DECOMPRESSED+1)))
        p=self.root/'huge';p.write_bytes(b'x'*(mod.MAX_COMPRESSED+1))
        with self.assertRaises(ValueError):mod.read_member(p)

    def test_truncation_replacement_and_symlink(self):
        p,e=self.artifact();self.a.consume(p,e,credential=TOKEN);before=self.state()
        data=p.read_bytes();p.unlink();p.write_bytes(data)
        self.assertBlocked(self.a.consume(p,e,credential=TOKEN),before)
        p.write_bytes(data[:-1]);self.assertBlocked(self.a.consume(p,e,credential=TOKEN),before)
        p.unlink();p.symlink_to(self.ledger);self.assertBlocked(self.a.consume(p,e,credential=TOKEN),before)

    def test_storage_locked_full_and_missing(self):
        self.consume();before=self.state()
        with sqlite3.connect(self.checkpoint) as db:
            db.execute('BEGIN EXCLUSIVE')
            self.assertBlocked(self.a.consume(*self.artifact(self.record(301)),credential=TOKEN),before)
        with patch.object(self.a,'_save',side_effect=sqlite3.OperationalError('database or disk is full')):
            self.assertBlocked(self.a.consume(*self.artifact(self.record(302)),credential=TOKEN),before)
        self.assertBlocked(self.a.view(credential=TOKEN),before)

    def test_crash_after_authority_commit_before_checkpoint(self):
        p,e=self.artifact();original=self.a._save
        def crash(db,**kw):
            if kw.get('status')=='AVAILABLE':raise OSError('SYNTHETIC_CRASH_AFTER_COMMIT')
            return original(db,**kw)
        with patch.object(self.a,'_save',side_effect=crash):
            self.assertEqual(self.a.consume(p,e,credential=TOKEN)['status'],'UNAVAILABLE')
        origin=self.state()[1];self.assertEqual(len(origin),1)
        self.a=self.new();out=self.a.consume(p,e,credential=TOKEN)
        self.assertIn('accepted_event',out,out)
        self.assertIsNone(out['accepted_event'],out);self.assertEqual(self.state()[1],origin)

    def test_slow_projection_cannot_publish_expired_hold(self):
        self.consume();self.consume(301,final_ready=True);before=self.state()
        original=mod.signal_view
        def slow(*args):
            result=original(*args);self.clock.at(307);return result
        with patch.object(mod,'signal_view',side_effect=slow):
            self.assertBlocked(self.a.view(credential=TOKEN),before)

    def test_rollover_does_not_rewrite_old_origin(self):
        self.consume();old=self.state()[1]
        out=self.consume(1200,close_offset=1800,final_ready=True)
        self.assertIn('accepted_event',out,out)
        self.assertEqual(out['accepted_event'],'BUY',out)
        self.assertEqual(len(self.state()[1]),2);self.assertIn(old[0],self.state()[1])
        before=self.state();self.clock.at(1201)
        self.assertBlocked(self.a.consume(*self.artifact(self.record(303)),credential=TOKEN),before)

    def test_scalp_and_later_other_source_never_attached(self):
        r=self.record();r['sources'][0]['state']['scalp']={'ready':True,'side':'DOWN','event':'EXIT'}
        r['sources'].append({'service':'owner','state':{'brti':'future'},'response_received_utc':stamp(400)})
        out=self.a.consume(*self.artifact(r),credential=TOKEN)
        self.assertEqual(out['accepted_event'],'BUY');self.assertEqual(out['origin']['side'],'UP')
        self.assertNotIn('scalp',out['origin']['protected_publication'])

    def test_no_native_network_or_order_path_and_frozen_files(self):
        source=Path(mod.__file__).read_text()
        import ast
        tree=ast.parse(source)
        imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)]
        self.assertFalse(set(imports)&{'requests','urllib','socket','subprocess'})
        root=Path(mod.__file__).parent
        for name in ('btc15_directional_signal_authority_v1.py','BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py',
                     'btc15_qualified_forward_observer_v1.py','btc15_information_install_v1.py'):
            self.assertEqual((root/name).read_bytes(),subprocess.check_output(['git','show',
                 'dcc44cc858eb745953c48860bbe1e2e847860326:'+name],cwd=root))

    def test_boundary_truth_does_not_relax_five_seconds(self):
        self.assertTrue(range_truth((5_000_000,5_000_000),0,5_000_000))
        with self.assertRaises(ValueError):range_truth((4_999_999,5_000_001),0,5_000_000)
        self.assertFalse(range_truth((5_000_001,5_000_002),0,5_000_000))

    def test_nonzero_bounds_and_rapid_causal_transitions(self):
        self.registry={'N':bound('native',error=1000,rate=10),'O':bound('collector',error=1000,rate=10)}
        self.clock.bound=replace(self.clock.bound,error_us=1000,rate_ppm=10)
        self.a=self.new()
        self.assertEqual(self.consume(final_ready=True)['accepted_event'],'BUY')
        self.assertEqual(self.consume(300.000001,final_ready=True)['accepted_event'],'HOLD')
        self.assertEqual(self.consume(300.000002,final_ready=True,final_side='DOWN')['accepted_event'],'PROTECT')

    def test_unhealthy_source_qualification_and_brti_expiry_preserve_origin(self):
        self.consume();before=self.state()
        for field in ('source_fresh','paired_quotes','brti_fresh'):
            r=self.record(301+self.seq);r['sources'][0]['state']['health'][field]=False
            self.clock.at(301+self.seq+.3)
            self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)
        r=self.record(310);self.clock.at(315)
        self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)

    def test_hung_absent_and_missing_private_storage_suspend_projection(self):
        self.consume();before=self.state()
        self.a.lock.acquire()
        try:self.assertBlocked(self.a.view(credential=TOKEN),before)
        finally:self.a.lock.release()
        self.clock.at(400);self.assertBlocked(self.a.view(credential=TOKEN),before)
        self.checkpoint.unlink()
        self.assertBlocked(self.a.view(credential=TOKEN),before)
        self.assertFalse(self.checkpoint.exists())

    def test_input_no_ack_and_exact_bytes_clocks_retained(self):
        r=self.record();p,e=self.artifact(r);data=p.read_bytes();original_stat=p.stat()
        self.a.consume(p,e,credential=TOKEN)
        self.assertEqual(p.read_bytes(),data);self.assertEqual(p.stat().st_mtime_ns,original_stat.st_mtime_ns)
        with sqlite3.connect(self.checkpoint) as db:
            saved=db.execute('SELECT bytes,manifest FROM members').fetchone()
        self.assertEqual(saved[0],data)
        parsed=mod.parsed_member(saved[0]);self.assertEqual(parsed,r)
        self.assertFalse(json.loads(saved[1])['original_http_bytes_available'])

    def test_epoch_conflict_and_raw_source_order_ambiguity(self):
        self.consume();before=self.state();r=self.record(301);r['observer_epoch']='unapproved'
        self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)
        r=self.record(302);r['sources'][0]['state']['generated_utc']=stamp(302.1)
        self.registry['O']=bound('collector',error=200000);self.a.registry=dict(self.registry)
        self.clock.at(302.3)
        self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)

    def test_authority_storage_failure_and_slow_commit_suspend_current_guidance(self):
        self.consume();before=self.state()
        with patch.object(self.a.authority,'consume',side_effect=sqlite3.OperationalError('disk full')):
            self.assertBlocked(self.consume(301),before)
        # A valid signal accepted at consumption may be historical by publication.
        # The slow downstream work must not expose a fresh HOLD.
        self.a=self.new();self.offset=0;self.seq=1
        # This existing member is already completed; a new run cannot bypass it.
        self.assertBlocked(self.a.consume(*self.artifact(),credential=TOKEN),before)

    def test_slow_authority_commit_leaves_only_historical_acceptance(self):
        original=self.a.authority.consume
        def slow(*args,**kw):
            result=original(*args,**kw);self.clock.at(316);return result
        with patch.object(self.a.authority,'consume',side_effect=slow):
            result=self.consume()
        self.assertEqual(result['status'],'UNAVAILABLE');self.assertIsNone(result['guidance'])
        self.assertEqual(len(self.state()[1]),1) # valid earlier acceptance, no fresh guidance

    def test_bound_replacement_cannot_reinterpret_old_origin(self):
        self.consume();before=self.state()
        self.a.registry['N']=replace(self.registry['N'],error_us=1)
        self.assertBlocked(self.a.view(credential=TOKEN),before)

    def test_no_implicit_clock_provider_or_source_fallback(self):
        self.clock.bound=None
        self.assertBlocked(self.a.consume(*self.artifact(),credential=TOKEN),self.state())
        result=self.a.consume('/tmp/unapproved',b'',credential=TOKEN)
        self.assertEqual(result['status'],'UNAVAILABLE');self.assertIn('DETACHED_ROOT',result['reason'])

    def test_same_clock_offset_cancellation_retains_independent_read_error(self):
        b=replace(bound('native',error=200000),read_error_us=100)
        iv=elapsed(b.witness(stamp(301)),b.witness(stamp(300)))
        self.assertEqual(iv,(999800,1000200))
        with self.assertRaisesRegex(ValueError,'UNCERTAIN'):
            range_truth(iv,0,1000000)

    def test_wrong_structural_types_fail_closed_before_authority(self):
        before=self.state()
        for key in ('final','scalp'):
            r=self.record();r['sources'][0]['state'][key]=['malformed']
            with self.subTest(key=key):
                self.assertBlocked(self.a.consume(*self.artifact(r),credential=TOKEN),before)
        p,e=self.artifact();e=json.loads(e);e['manifest']=[]
        e['mac']=mod.signature(e['manifest'],KEY)
        self.assertBlocked(self.a.consume(p,pack(e).encode(),credential=TOKEN),before)

    def test_adapter_preserves_native_outputs_at_fixed_cutoffs(self):
        from completion_audit.isolated_decision_v2 import FrozenRuntime,stable
        from test_btc15_isolated_decision_v2 import completed,fixture as native_fixture,TICKER
        base=FrozenRuntime(completed());off,on=base.fork(),base.fork()
        for i,t in enumerate((300,305.000001,310,315,895,901)):
            native=native_fixture(t,ask=(.31,.79)[i%2],btc=100000+(-1)**i*85,
                quote_wait=i==2,brti_delay=(4.999999,5.000001)[i%2],
                ticker=TICKER if t<900 else 'KXBTC15M-19DEC311930-15')
            self.assertEqual(stable(off.step(native)),stable(on.step(native)))
            before=stable(on.snapshot())
            with patch('requests.get',side_effect=AssertionError('No added source GET')):
                self.consume(300+i,final_ready=True,final_side='DOWN' if i>2 else 'UP')
            self.assertEqual(stable(on.snapshot()),before)
            self.assertEqual(stable(off.snapshot()),stable(on.snapshot()))
            self.assertEqual(stable(off.diag),stable(on.diag))

if __name__=='__main__':unittest.main(verbosity=2)
