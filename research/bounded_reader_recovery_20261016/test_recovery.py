"""Declared offline fixtures; no authentic missing decisions are invented."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ops.live_recording.policy import file_sha
from ops.live_recording.windowed_campaign import run, WindowedCampaignVerifier
from research.early_reader_qualification_20261016.test_main_reader import fixture, sources
from research.main_closeout_incremental_20261015 import test_v81_exact_native_window_causality as v81


def main_fixture(root, mutate=None):
    original=sources.native;sequence=[100]
    def contiguous(a,n,unused,**kw):
        sequence[0]+=1
        return original(a,n,sequence[0],**kw)
    with patch.object(sources,'native',contiguous):fixture(root,mutate)


def v81_fixture(root):
    a=v81.make_archive(root);v81.original_market(a);q=v81.quote_book(a)
    btc=v81.btc_http(a);b,h,at=v81.brti_read(a)
    p=v81.v81_row(a,q,b,btc,(b,h,at));v81.scalp_native(a,p)
    a.write('STOP',dict(clean=True));a.close()


def hashes(root):
    return {str(p.relative_to(root)):file_sha(p) for p in root.rglob('*.jsonl.gz')}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.tmp=Path(t.name);self.root=self.tmp/'source';self.root.mkdir()

    def assert_outputs_equal(self,a,b):
        for name in ('windows.jsonl','associations.jsonl','issues.jsonl',
                     'v81_native_original_associations.jsonl','window_inventory_manifest.json'):
            self.assertEqual((a/name).read_bytes(),(b/name).read_bytes(),name)

    def kill(self,out,phase,generation=3):
        script='''
import os,signal,sys
from ops.live_recording.windowed_campaign import run
def fault(phase,v):
 if phase==sys.argv[3] and v.generation==int(sys.argv[4]):os.kill(os.getpid(),signal.SIGKILL)
run(sys.argv[1],sys.argv[2],window_records=3,fault=fault)
'''
        proc=subprocess.run([sys.executable,'-B','-c',script,str(self.root),str(out),phase,str(generation)],capture_output=True)
        self.assertEqual(proc.returncode,-signal.SIGKILL,proc.stderr.decode())
        self.assertFalse((out/'window_inventory_manifest.json').exists())

    def test_main_windowed_checks_match_existing_association_methods(self):
        main_fixture(self.root);r=run(self.root,self.tmp/'out',window_records=3)
        v=r['campaign_verification'];m=v['metrics']
        self.assertEqual(m['native_associations'],6);self.assertEqual(m['terminal_associations'],2)
        self.assertEqual(m['outcome_associations'],1);self.assertEqual(v['pending_outcomes'],{})
        self.assertFalse(v['actual_production_complete']);self.assertEqual(v['long_test'],'NO_GO')

    def test_sigkill_before_commit_resumes_exactly(self):
        main_fixture(self.root);before=hashes(self.root)
        run(self.root,self.tmp/'baseline',window_records=3)
        self.kill(self.tmp/'resume','before_commit')
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')
        self.assertEqual(before,hashes(self.root))

    def test_sigkill_after_commit_no_duplicate_ledgers(self):
        main_fixture(self.root);run(self.root,self.tmp/'baseline',window_records=3)
        self.kill(self.tmp/'resume','after_commit')
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')
        with sqlite3.connect(self.tmp/'resume'/'verification.sqlite3') as db:
            self.assertEqual(db.execute("SELECT count(*) FROM ledger WHERE name='associations'").fetchone()[0],7)

    def test_sigkill_inside_window_preserves_quote_vector_source_state(self):
        main_fixture(self.root);run(self.root,self.tmp/'baseline',window_records=3)
        self.kill(self.tmp/'resume','after_record',6)
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')

    def test_settlement_acceptance_to_publication_restart(self):
        main_fixture(self.root);run(self.root,self.tmp/'baseline',window_records=3)
        from ops.recording_workflow.evidence import lines
        records=sorted((r for p in self.root.rglob('*.jsonl.gz') for _,r,_ in lines(p)),key=lambda r:r['sequence'])
        seq=next(r['sequence'] for r in records if r['kind']=='OUTCOME_ACCEPTANCE')
        script='''
import os,signal,sys
from ops.live_recording.windowed_campaign import run
def fault(phase,v):
 if phase=='after_commit' and v.counts['OUTCOME_ACCEPTANCE'] and not v.metrics['outcome_associations']:
  os.kill(os.getpid(),signal.SIGKILL)
run(sys.argv[1],sys.argv[2],window_records=1,fault=fault)
'''
        proc=subprocess.run([sys.executable,'-B','-c',script,str(self.root),str(self.tmp/'resume')],capture_output=True)
        self.assertEqual(proc.returncode,-signal.SIGKILL,proc.stderr.decode())
        run(self.root,self.tmp/'one',window_records=1)
        run(self.root,self.tmp/'resume',resume=True,window_records=1)
        self.assert_outputs_equal(self.tmp/'one',self.tmp/'resume')

    def test_v81_receipts_and_exact_causal_ledger_survive_restart(self):
        v81_fixture(self.root);r=run(self.root,self.tmp/'baseline',window_records=3)
        self.assertEqual(r['campaign_verification']['v81_causal_matches'],1)
        self.kill(self.tmp/'resume','after_commit',6)
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')

    def test_completed_resume_is_idempotent(self):
        main_fixture(self.root);a=run(self.root,self.tmp/'out',window_records=3)
        h=file_sha(self.tmp/'out'/'verification.sqlite3')
        b=run(self.root,self.tmp/'out',resume=True,window_records=3)
        self.assertEqual(a,b);self.assertEqual(h,file_sha(self.tmp/'out'/'verification.sqlite3'))

    def test_logically_valid_sql_tamper_is_rejected(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with sqlite3.connect(self.tmp/'out'/'verification.sqlite3') as db:
            db.execute('UPDATE sources SET value=value+1')
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_LOGICAL_INTEGRITY:sources'):
            run(self.root,self.tmp/'out',resume=True,window_records=3)

    def test_ledger_tamper_is_rejected(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with sqlite3.connect(self.tmp/'out'/'verification.sqlite3') as db:
            db.execute("DELETE FROM ledger WHERE name='associations' AND n=1")
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_LOGICAL_INTEGRITY:ledger'):
            run(self.root,self.tmp/'out',resume=True,window_records=3)

    def test_state_checksum_tamper_is_rejected(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with sqlite3.connect(self.tmp/'out'/'verification.sqlite3') as db:
            db.execute("UPDATE recovery_checkpoint SET body='{}'")
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_STATE_HASH'):
            run(self.root,self.tmp/'out',resume=True,window_records=3)

    def test_options_drift_rejected(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SOURCE_CODE_OR_OPTIONS_DRIFT'):
            run(self.root,self.tmp/'out',resume=True,window_records=4)

    def test_config_drift_rejected(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_CONFIG_DRIFT'):
            run(self.root,self.tmp/'out',resume=True,window_records=3,work_db_bytes=8*1024**2)

    def test_concurrent_writer_is_refused(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        a=WindowedCampaignVerifier(self.root,self.tmp/'out',resume=True)
        try:
            with self.assertRaisesRegex(ValueError,'RECOVERY_CONCURRENT_WRITER'):
                WindowedCampaignVerifier(self.root,self.tmp/'out',resume=True)
        finally:a.close()

    def test_wrong_main_exit_bid_still_rejected(self):
        def change(i,n):
            if i==5:
                n['terminal']['executable_exit_bid']=.99
                n['management']['terminal']=dict(n['terminal'])
        main_fixture(self.root,change)
        with self.assertRaisesRegex(ValueError,'MAIN_TERMINAL_EXECUTABLE_BID'):
            run(self.root,self.tmp/'out',window_records=3)
        self.assertFalse((self.tmp/'out'/'window_inventory_manifest.json').exists())

    def test_ledger_budget_stops_without_complete_manifest(self):
        main_fixture(self.root)
        with self.assertRaisesRegex(Exhausted,'LEDGER_BYTES'):
            run(self.root,self.tmp/'out',window_records=3,ledger_bytes=1024)
        self.assertFalse((self.tmp/'out'/'window_inventory_manifest.json').exists())

    def test_first_checkpoint_can_recover_before_any_record(self):
        main_fixture(self.root);run(self.root,self.tmp/'baseline',window_records=3)
        self.kill(self.tmp/'resume','after_commit',1)
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')

    def test_original_file_change_refuses_resume(self):
        main_fixture(self.root);self.kill(self.tmp/'resume','after_commit',3)
        import gzip
        path=next(self.root.rglob('*.jsonl.gz'))
        raw=gzip.decompress(path.read_bytes())
        path.write_bytes(gzip.compress(raw,mtime=123))
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SOURCE_CODE_OR_OPTIONS_DRIFT'):
            run(self.root,self.tmp/'resume',resume=True,window_records=3)

    def test_duplicate_native_identity_refused_across_windows(self):
        from btc15_ladder_journal_v1 import digest
        def change(i,n):
            if i==6:
                n['evidence']['native_sequence']=5
                n['final']['publication_id']=digest(['MAIN','FINAL',['NATIVE-EPOCH',5]])
        main_fixture(self.root,change)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_NATIVE_DECISION_IDENTITY'):
            run(self.root,self.tmp/'out',window_records=3)

    def test_final_commit_can_recover_before_export(self):
        main_fixture(self.root);run(self.root,self.tmp/'baseline',window_records=3)
        script='''
import os,signal,sys
from ops.live_recording.windowed_campaign import run
def fault(phase,v):
 if phase=='after_commit' and v.errors['DECLARED_CAMPAIGN_SCOPE_MISSING']:
  os.kill(os.getpid(),signal.SIGKILL)
run(sys.argv[1],sys.argv[2],window_records=3,fault=fault)
'''
        proc=subprocess.run([sys.executable,'-B','-c',script,str(self.root),str(self.tmp/'resume')],capture_output=True)
        self.assertEqual(proc.returncode,-signal.SIGKILL,proc.stderr.decode())
        run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')

    def test_original_loss_remains_quarantined_after_resume(self):
        from research.main_closeout_incremental_20261015 import test_quote_window_handoff_research as quotes
        a=quotes.setup(self.root);a.write('EVIDENCE_GAP',dict(reason='DECLARED_FIXTURE_LOSS'))
        for i in range(9):a.write('RECORDING_HEALTH',dict(observed_at=quotes.T0+i))
        a.write('STOP',dict(clean=True));a.close()
        result=run(self.root,self.tmp/'baseline',window_records=3)
        self.kill(self.tmp/'resume','after_commit',3)
        again=run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assertFalse(again['loss_free']);self.assertEqual(again['campaign_verification']['status'],'INCOMPLETE')
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')

    def test_v81_stale_publication_still_fails(self):
        a=v81.make_archive(self.root);v81.original_market(a);q=v81.quote_book(a)
        btc=v81.btc_http(a);b,h,at=v81.brti_read(a)
        p=v81.v81_row(a,q,b,btc,(b,h,at));v81.scalp_native(a,p,published=v81.NOW+20)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'V81_LINKS_NATIVE_PUBLICATION_STALE'):
            run(self.root,self.tmp/'out',window_records=3)

    def test_sql_schema_change_refuses_resume(self):
        main_fixture(self.root);run(self.root,self.tmp/'out',window_records=3)
        with sqlite3.connect(self.tmp/'out'/'verification.sqlite3') as db:
            db.execute('DROP INDEX native_origin')
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SQL_SCHEMA_DRIFT'):
            run(self.root,self.tmp/'out',resume=True,window_records=3)

    def test_nonmarket_http_response_keeps_original_handoff_semantics(self):
        from ops.live_recording.policy import canonical
        a=v81.make_archive(self.root)
        a.observe('HTTP_RESPONSE',dict(raw=canonical(dict(series=dict(ticker='KXBTC15M'))),
                  endpoint='/trade-api/v2/series/KXBTC15M',received_at=v81.NOW-6))
        v81.original_market(a);q=v81.quote_book(a);btc=v81.btc_http(a);b,h,at=v81.brti_read(a)
        p=v81.v81_row(a,q,b,btc,(b,h,at));v81.scalp_native(a,p)
        a.write('STOP',dict(clean=True));a.close()
        result=run(self.root,self.tmp/'out',window_records=3)
        self.assertEqual(result['campaign_verification']['v81_causal_matches'],1)

    def test_invalid_candle_is_durable_quarantine_not_qualification(self):
        from ops.live_recording.policy import canonical,sha
        a=v81.make_archive(self.root)
        raw=canonical([[100,100,1,1,1,1,1]])
        a.write('CANDLE_ACCEPTANCE',dict(raw=raw.decode(),sha256=sha(raw),accepted_at=v81.NOW))
        for i in range(8):a.write('RECORDING_HEALTH',dict(observed_at=v81.NOW+i))
        a.write('STOP',dict(clean=True));a.close()
        result=run(self.root,self.tmp/'baseline',window_records=3)
        self.assertEqual(result['campaign_verification']['issue_counts']['RECORD_VERIFICATION'],1)
        self.assertIn('COMPLETED_CANDLE_END_CLOCK',(self.tmp/'baseline'/'issues.jsonl').read_text())
        self.kill(self.tmp/'resume','after_commit',3)
        again=run(self.root,self.tmp/'resume',resume=True,window_records=3)
        self.assertFalse(again['campaign_verification']['complete_supplied_scope'])
        self.assert_outputs_equal(self.tmp/'baseline',self.tmp/'resume')


from ops.recording_workflow.whole_run import Exhausted
if __name__=='__main__':unittest.main()
