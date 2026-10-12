"""Bounded negative and integration mechanics. Fixtures, no upstream access."""
from pathlib import Path
from contextlib import redirect_stderr
import base64,gzip,io,json,os,sqlite3,tempfile,threading,time,unittest
from unittest.mock import patch
from .policy import config,local_policy,proposed_policy,validate_policy,local_root
from .integration import Capture,install_hooks
from .evidence import index_run,records_for,file_sha,independent_history
from .transfer import transfer,restore,package,private_store
from .report import generate
from .staging import make_target,install,rollback
from .rehearsal import fixture_provider
from candidates.early_recording_20261012.archive import Archive,canonical,sha,read_archive
from btc15_quote_proof_offpath_v1 import Witness

class Workflow(unittest.TestCase):
    def test_capture_default_off_no_threads_or_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'absent'
            with patch('threading.Thread.start',side_effect=AssertionError('THREAD')),patch('pathlib.Path.mkdir',side_effect=AssertionError('DISK')):
                c=Capture(config(root));self.assertEqual(c.status()['status'],'DISABLED')
            self.assertFalse(root.exists())

    def test_live_mode_flags_protected_paths_and_policy_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for key,value in [('mode','LIVE'),('orders',True),('production_enabled',True),('actionable',True)]:
                c=config(d);c[key]=value
                with self.assertRaises(ValueError):Capture(c)
            with self.assertRaises(ValueError):local_root('/data/anything')
            Path(d,'link').symlink_to('/data')
            with self.assertRaises(ValueError):local_root(Path(d,'link/x'))
            p=local_policy();p['reclaim']=True
            with self.assertRaises(ValueError):validate_policy(p)
            p=local_policy();p['total_bytes']=1
            with self.assertRaises(ValueError):validate_policy(p)

    def test_mirror_blocked_disk_does_not_block_proof_queue_or_consumer(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);c=Capture(config(d/'run',enabled=True));entered=threading.Event();release=threading.Event()
            original=c.archive.observe
            def stall(*a,**k):entered.set();release.wait(2);return original(*a,**k)
            c.archive.observe=stall
            c.observer.source('BTC',100000,100,100.1,'b');self.assertTrue(entered.wait(1))
            p=fixture_provider(d/'proof','M',1800);c.bind_provider(p)
            # Validator is independently tested; here isolate existing cache flow.
            p.proof_writer.validator=lambda proof,w:w.identity
            w=Witness('M','native','e',1002000,'id',7,2,1000000,1800000)
            self.assertTrue(p.proof_writer.submit(w,[{'type':'synthetic-proof'}]))
            p.proof_writer.queue.join()
            self.assertEqual(p.proof_writer.queue.unfinished_tasks,0)
            self.assertTrue((d/'proof/latest.json').is_file())
            self.assertGreater(c.writer.queue.unfinished_tasks,0)
            release.set();p.proof_writer.close();c.close()

    def test_failed_mirror_still_publishes_existing_proof_cache(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);c=Capture(config(d/'run',enabled=True));p=fixture_provider(d/'proof','M',1800);c.bind_provider(p)
            p.proof_writer.validator=lambda proof,w:w.identity
            c.writer.archive_failed=True
            w=Witness('M','native','e',1002000,'id',7,2,1000000,1800000)
            self.assertTrue(p.proof_writer.submit(w,[{'type':'synthetic'}]));p.proof_writer.queue.join()
            self.assertTrue((d/'proof/latest.json').is_file());self.assertTrue(c.status()['losses'])
            p.proof_writer.close();c.close()

    def test_queue_overflow_reports_independent_health_and_incomplete_session(self):
        with tempfile.TemporaryDirectory() as d,redirect_stderr(io.StringIO()) as log:
            cfg=config(d,enabled=True);cfg['ingress']=dict(queue_size=64,queue_bytes=8*1024**2)
            c=Capture(cfg);gate=threading.Event();entered=threading.Event()
            original=c.archive.observe
            def stall(*a,**k):entered.set();gate.wait(2);return original(*a,**k)
            c.archive.observe=stall
            c.observer.source('BTC',100000,100,100.1,'b');entered.wait(1)
            for t in range(100):c.observer.source('BTC',100000+t,101+t,101.1+t,'b')
            self.assertEqual(c.status()['status'],'INCOMPLETE');time.sleep(.3)
            self.assertIn('INCOMPLETE',log.getvalue());gate.set();c.close()
            self.assertTrue(read_archive(Path(d)/'source')['gaps'])

    def test_disk_failure_report_survives_archive_failure(self):
        with tempfile.TemporaryDirectory() as d,redirect_stderr(io.StringIO()) as log:
            c=Capture(config(d,enabled=True));c.writer.queue.join()
            c.archive.journal.append=lambda *a:(_ for _ in ()).throw(OSError('disk full fixture'))
            c.observer.source('BTC',100000,100,100.1,'b');c.writer.queue.join()
            self.assertEqual(c.status()['status'],'INCOMPLETE');c.close()
            self.assertIn('INCOMPLETE',log.getvalue())
            self.assertTrue(any(g['reason']=='UNCLOSED_OR_INCOMPLETE_SESSION' for g in read_archive(Path(d)/'source')['gaps']))

    def test_quota_exhaustion_no_pruning_and_restart_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=config(d,enabled=True);cfg['storage']['per_archive_bytes']=1200
            c=Capture(cfg)
            for t in range(10):c.observer.source('BTC',100000+t,t,t+.1,'b');c.writer.queue.join()
            c.close();before={p.name:p.read_bytes() for p in Path(d,'source.segments').glob('*.gz')}
            self.assertEqual(c.status()['status'],'INCOMPLETE')
            c2=Capture(cfg);c2.close()
            for name,b in before.items():self.assertEqual(Path(d,'source.segments',name).read_bytes(),b)
            self.assertTrue(read_archive(Path(d)/'source')['gaps'])

    def test_partial_transfer_resume_duplicate_retry_and_corruption_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);src=d/'src';src.write_bytes(bytes(range(256))*4096);digest=file_sha(src)
            with self.assertRaises(InterruptedError):transfer(src,d/'store',expected_sha256=digest,quota=2*1024**2,interrupt_after=1)
            r=transfer(src,d/'store',expected_sha256=digest,quota=2*1024**2);self.assertTrue(r['resumed'])
            self.assertTrue(transfer(src,d/'store',expected_sha256=digest,quota=2*1024**2)['duplicate'])
            (d/'store'/digest).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'CORRUPTION'):transfer(src,d/'store',expected_sha256=digest,quota=2*1024**2)

    def test_outage_partial_prefix_and_export_quota_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);src=d/'src';src.write_bytes(b'x'*1000);digest=file_sha(src);store=private_store(d/'store')
            with patch('os.fsync',side_effect=OSError('outage')):
                with self.assertRaises(OSError):transfer(src,store,expected_sha256=digest,quota=10000)
            self.assertTrue(transfer(src,store,expected_sha256=digest,quota=10000)['resumed'])
            with self.assertRaises(OSError):transfer(src,d/'quota',expected_sha256=digest,quota=10)
            bad=private_store(d/'bad');(bad/(digest+'.part')).write_bytes(b'no')
            with self.assertRaisesRegex(ValueError,'PARTIAL_CORRUPTION'):transfer(src,bad,expected_sha256=digest,quota=10000)

    def test_empty_partial_and_corrupt_archives_cannot_be_complete(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);root=d/'run';root.mkdir();(root/'identity.json').write_text('{}')
            seg=root/'source.segments';seg.mkdir();(seg/'torn.jsonl.gz').write_bytes(b'\x1f\x8bunfinished')
            idx=index_run(root,d/'index');r=generate(root,d/'index',d/'report')
            self.assertTrue(idx['gaps']);self.assertFalse(r['complete_evidence']);self.assertFalse(r['cost_verified'])

    def test_bounded_contract_range_source_context_and_index_corruption(self):
        from candidates.early_recording_20261012.test_recording import event_pair
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);c=Capture(config(d/'run',enabled=True))
            for i,ticker in enumerate(('A','B')):
                c.observer.source('BTC',100000,1000+i,1001+i,'b')
                for e in event_pair(ticker):
                    raw=canonical(e);c.observer.quote_receive(raw,ticker,'e'+ticker,1001+i,1)
                    c.observer.quote_accept(raw,ticker,'e'+ticker,1001+i,1001.1+i)
                c.writer.queue.join()
            c.close();index_run(d/'run',d/'index')
            rs,scope=records_for(d/'run',d/'index',contract='B',start=1002,end=1002.2)
            self.assertTrue(any(r['kind']=='SOURCE' for r in rs))
            self.assertFalse(any(r['payload'].get('ticker')=='A' for r in rs))
            with self.assertRaisesRegex(ValueError,'BUDGET'):records_for(d/'run',d/'index',max_bytes=1)
            (d/'index/index.sqlite3').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'INDEX_HASH'):records_for(d/'run',d/'index')

    def test_native_journal_postcommit_capture_preserves_exact_record(self):
        from btc15_ladder_journal_v1 import Journal
        import zlib
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);c=Capture(config(d/'run',enabled=True));j=Journal(d/'native/main.sqlite3','main');c.bind_journal(j)
            record=dict(kind='OBSERVATION',published_ts=100.,contract='M',opened=0.,closed=900.,target=100000.,
                unavailable_reason='SYNTHETIC_UNAVAILABLE',origin_id='fixture-origin',final=dict(ready=False),signal_only=True,orders=False)
            seq=j.commit(record,{});c.writer.queue.join();c.close()
            from .snapshots import snapshot
            receipt=snapshot(d/'native/main.sqlite3',d/'detached/main.sqlite3',kind='MAIN',identity=dict(evidence_class='FIXTURE'))
            self.assertEqual(receipt['event_count'],1)
            stored=j.db.execute('SELECT body,sha256 FROM events WHERE seq=?',(seq,)).fetchone();j.db.close()
            r=next(r for r in read_archive(d/'run/source')['records'] if r['kind']=='NATIVE_RECORD')
            self.assertEqual(r['payload']['raw'].encode(),zlib.decompress(stored[0]));self.assertEqual(r['payload']['sha256'],stored[1])

    def test_later_brti_not_backdated_and_incompatible_model_rejected(self):
        from candidates.early_rebuild_20261012.continuation import ContinuationEstimator
        from .staging import ROOT
        a=json.loads((ROOT/'audit/early_continuation_20261012/evaluation/CONTINUATION_ARTIFACT.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'ARTIFACT_HISTORY_PROVENANCE_UNSUPPORTED'):ContinuationEstimator(a,expected_sha256=a['artifact_sha256'])
        with tempfile.TemporaryDirectory() as d:
            c=Capture(config(d,enabled=True));c.observer.source('BTC',100000,100,100.1,'b');c.observer.source('BRTI',100001,100,102,'z')
            c.writer.queue.join();c.close();h,joined=independent_history(read_archive(Path(d)/'source')['records'],101)
            self.assertEqual(joined,[])

    def test_staging_install_rollback_and_drift_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'target';make_target(target);result=install(target);self.assertFalse(result['capture_default'])
            import subprocess,sys
            cfg=Path(d)/'config.json';cfg.write_bytes(canonical(config(Path(d)/'installed-run')))
            check=subprocess.run([sys.executable,'-B','-m','ops.recording_workflow.operator','preflight','--config',str(cfg)],cwd=target,capture_output=True,text=True)
            self.assertEqual(check.returncode,0,check.stderr);self.assertFalse(json.loads(check.stdout)['live_allowed'])
            script="from ops.recording_workflow.integration import Capture; from ops.recording_workflow.policy import config; import sys; c=Capture(config(sys.argv[1],enabled=True)); c.observer.source('BTC',100000,100,100.1,'b'); c.writer.queue.join(); assert c.close(); assert c.status()['status']=='CLOSED'"
            check=subprocess.run([sys.executable,'-B','-c',script,str(Path(d)/'installed-run')],cwd=target,capture_output=True,text=True)
            self.assertEqual(check.returncode,0,check.stderr)

            p=target/'btc15_quote_proof_offpath_v1.py';old=p.read_bytes();p.write_bytes(old+b'\n# fixture drift\n')
            with self.assertRaisesRegex(ValueError,'DRIFT'):rollback(target)
            p.write_bytes(old);self.assertEqual(rollback(target)['status'],'VERIFIED')

    def test_storage_projection_accounts_all_copies_without_reclamation(self):
        p=proposed_policy(1000000)
        self.assertGreaterEqual(p['per_archive_bytes'],1000000*(86400+120+420)*1.5)
        self.assertGreater(p['total_bytes'],p['per_archive_bytes']*6)
        self.assertFalse(p['reclaim']);self.assertFalse(p['qualified_24h'])

    def test_admin_original_worker_mirror_and_detached_backup(self):
        from .integration import bind_admin_class
        from .snapshots import snapshot
        from btc15_v2_product.admin import Admin
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);c=Capture(config(d/'run',enabled=True));bind_admin_class(c,Admin)
            admin=Admin(d/'native','main');admin.offer(dict(kind='SYNTHETIC_REJECTION',reason='UNAVAILABLE',signal_only=True,orders=False))
            admin.queue.join();c.writer.queue.join()
            # Backup WHILE the original owner remains open; never copy WAL files.
            receipt=snapshot(d/'native/main.admin.sqlite3',d/'detached/admin.sqlite3',kind='ADMIN',identity=dict(evidence_class='FIXTURE'))
            self.assertEqual(receipt['event_count'],1)
            admin.queue.put(None);admin.queue.join();admin.thread.join(1);c.close()
            rs=read_archive(d/'run/source')['records'];r=next(r for r in rs if r['kind']=='NATIVE_RECORD')
            self.assertEqual(json.loads(r['payload']['raw'])['kind'],'SYNTHETIC_REJECTION')
            with self.assertRaises(ValueError):snapshot(d/'native/main.admin.sqlite3',d/'remote/admin',kind='ADMIN',identity=dict(evidence_class='NATIVE_CAPTURE'))

    def test_information_role_shares_run_identity_without_source_thread(self):
        from .integration import InformationCapture
        from btc15_information_service_v1 import DurablePublisher
        with tempfile.TemporaryDirectory() as d:
            cfg=config(d,enabled=True);main=Capture(cfg);info=InformationCapture(cfg)
            self.assertFalse(hasattr(info,'writer'))
            # No inference needed to check cross-process archive identity/shutdown.
            archive=info.publisher_kwargs()['evidence_archive'];archive.start();archive.write('STOP',dict(clean=True));archive.close()
            self.assertEqual(archive.source_binding,cfg['run_id']+':information')
            wrong=dict(cfg,run_id='different')
            with self.assertRaises(ValueError):InformationCapture(wrong)
            main.close()

    def test_installed_preflight_uses_bundled_lock_without_production_access(self):
        from .operator import preflight
        with tempfile.TemporaryDirectory() as d:
            p=preflight(config(d));self.assertEqual(p['status'],'BLOCKED')
            self.assertFalse(p['live_allowed']);self.assertTrue(any(x['name']=='scikit-learn' and x['status']=='BLOCKED' for x in p['dependencies']))

    def test_automatic_completion_report_package_idempotence_and_failure_channel(self):
        from .completion import Completion
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);cfg=config(d/'run',enabled=True);c=Capture(cfg)
            c.observer.source('BTC',100000,100,100.1,'b');c.writer.queue.join()
            done=Completion(cfg,d/'final',d/'store');r=done.finish(c,'FIXTURE_END')
            self.assertEqual(r['status'],'COMPLETED_OFFLINE');self.assertFalse(r['complete_evidence'])
            self.assertEqual(done.finish(c,'DUPLICATE'),r)
            self.assertTrue((d/'final/report/REPORT.txt').is_file())
        with tempfile.TemporaryDirectory() as d,redirect_stderr(io.StringIO()) as log:
            d=Path(d);cfg=config(d/'run',enabled=True);c=Capture(cfg)
            with patch('ops.recording_workflow.completion.finalize',side_effect=OSError('failed report disk')):
                r=Completion(cfg,d/'fail',d/'store').finish(c,'DISK_FAILURE')
            self.assertEqual(r['status'],'FAILED');self.assertIn('AUTOMATIC_COMPLETION',log.getvalue())

    def test_real_child_exit_and_deterministic_restart_preserve_old_bytes(self):
        import subprocess,sys
        from .staging import ROOT
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run'
            script="from ops.recording_workflow.integration import Capture; from ops.recording_workflow.policy import config; import os,sys; c=Capture(config(sys.argv[1],enabled=True)); c.observer.source('BTC',100000,100,100.1,'b'); c.writer.queue.join(); os._exit(23)"
            child=subprocess.run([sys.executable,'-B','-c',script,str(root)],cwd=ROOT,capture_output=True)
            self.assertEqual(child.returncode,23)
            before={p:p.read_bytes() for p in Path(str(root/'source')+'.segments').glob('*.gz')}
            c=Capture(config(root,enabled=True));c.observer.source('BTC',100001,101,101.1,'b');c.writer.queue.join();c.close()
            for p,raw in before.items():self.assertEqual(p.read_bytes(),raw)
            out=read_archive(root/'source');self.assertEqual(out['sessions'],2)
            self.assertFalse(out['continuous_across_sessions']);self.assertTrue(any(x['reason']=='UNCLOSED_OR_INCOMPLETE_SESSION' for x in out['gaps']))

if __name__=='__main__':unittest.main()
