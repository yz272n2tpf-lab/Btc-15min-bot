"""Small declared fixtures; never substitute these for the sealed native run."""
from collections import Counter
import json
import queue
import sqlite3
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from btc15_quote_proof_offpath_v1 import OffPathProofWriter, Observation, Witness, GAP_REASONS
from itertools import count
from candidates.early_recording_20261012.archive import read_archive
from ops.live_recording.burst_journal_research import BufferedProofWriter, observation_charge
from ops.live_recording.capture import Gate, Capture
from ops.live_recording.candle_schema import SCHEMA, PRODUCER_SHA256
from ops.live_recording.policy import canonical, sha, file_sha
from ops.live_recording.reader import CampaignVerifier
from ops.live_recording.windowed_campaign import run
from research.main_closeout_incremental_20261015.test_recorder_burst_batch_research import archive, writer_for
from research.early_reader_qualification_20261016.test_restart_and_drain import config

ROOT=Path(__file__).resolve().parents[2]

class FixTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)

    def test_original_charge_mutation_reproduced_for_quote_and_http(self):
        a=archive(self.root/'old');a.start()
        for kind,raw in [('QUOTE_RECEIVE','x'*1500),('QUOTE_ACCEPT',b'x'*1500),
                         ('HTTP_RESPONSE',b'{"padding":"'+b'x'*1500+b'"}')]:
            fields=dict(raw=raw,received_at=120.,ticker='fixture',epoch='one',endpoint='/fixture')
            before=observation_charge(fields);a.observe(kind,fields)
            self.assertNotEqual(observation_charge(fields),before)
        a.write('STOP',dict(clean=True));a.close()

    def test_exact_charge_multibatch_string_bytes_and_dedup(self):
        a=archive(self.root/'new');w=writer_for(self.root,a);expected=0
        # Same immutable input may produce two envelopes, one envelope, or a
        # deduplicated wire reference. Count observations and charge separately.
        for i in range(400):
            raw=canonical(dict(type='fixture',seq=i,padding='x'*1800))
            for kind,value in [('QUOTE_RECEIVE',raw.decode()),('QUOTE_ACCEPT',raw),
                               ('HTTP_RESPONSE',raw)]:
                f=dict(raw=value,received_at=120.,ticker='fixture',epoch='one',endpoint='/fixture')
                expected+=observation_charge(f)
                self.assertTrue(w.submit_observation(kind,**f))
        self.assertTrue(w.close(15));s=w.status();b=s['durable_batch']
        self.assertTrue(s['terminal_accounting_complete'])
        self.assertEqual(s['admitted_observations'],1200)
        self.assertEqual(s['admitted_charge_bytes'],expected)
        self.assertEqual(b['processed_charge_bytes'],expected)
        self.assertEqual(b['durable_charge_bytes'],expected)
        self.assertEqual(s['not_yet_durable_observations'],0)
        self.assertEqual(s['not_yet_durable_charge_bytes'],0)
        rows=read_archive(self.root/'new')['records']
        self.assertEqual(sum(r['kind']=='QUOTE_BYTES' for r in rows),400)
        self.assertEqual(sum(r['kind']=='HTTP_BYTES' for r in rows),400)
        self.assertEqual(sum(r['kind']=='STOP' for r in rows),1)

    def test_no_partial_or_failed_fsync_durable_credit(self):
        a=archive(self.root/'pending');a.start()
        a.write('SOURCE_GAP',dict(reason='FIXTURE'))
        a.journal.observation_processed(987)
        self.assertEqual(a.journal.durable_charge,0)
        with patch.object(a.journal.original,'append',side_effect=OSError('injected fsync failure')):
            with self.assertRaises(OSError):a.journal.flush()
        self.assertEqual(a.journal.durable_charge,0)
        self.assertEqual(a.journal.processed_charge,987)
        self.assertTrue(a.journal.pending)
        a.journal.flush();self.assertEqual(a.journal.durable_charge,987)
        a.write('STOP',dict(clean=True));a.close()

    def test_failed_observation_has_no_processed_credit(self):
        a=archive(self.root/'broken')
        a.observe=lambda *a,**k:(_ for _ in ()).throw(ValueError('fixture'))
        w=writer_for(self.root,a)
        self.assertTrue(w.submit_observation('SOURCE_GAP',reason='fixture'))
        self.assertTrue(w.close(15));s=w.status()
        self.assertFalse(s['terminal_accounting_complete'])
        self.assertEqual(s['durable_batch']['processed_observations'],0)
        self.assertEqual(s['not_yet_durable_charge_bytes'],s['admitted_charge_bytes'])
        self.assertGreater(s['losses']['WRITER_FAILURE'],0)

    def test_drain_fsync_failure_never_claims_durable_or_clean_terminal(self):
        a=archive(self.root/'fsync-failure');ready=threading.Event();start=a.start
        def started():start();ready.set()
        a.start=started;w=writer_for(self.root,a)
        self.assertTrue(ready.wait(2))
        with patch.object(a.journal.original,'append',side_effect=OSError('injected fsync failure')):
            self.assertTrue(w.submit_observation('SOURCE_GAP',reason='fixture'))
            self.assertTrue(w.close(10))
        s=w.status();self.assertFalse(s['terminal_accounting_complete'])
        self.assertEqual(s['durable_batch']['processed_observations'],1)
        self.assertEqual(s['durable_batch']['durable_observations'],0)
        self.assertEqual(s['not_yet_durable_charge_bytes'],s['admitted_charge_bytes'])
        self.assertTrue(s['archive_failed']);self.assertGreater(s['losses']['WRITER_FAILURE'],0)

    def test_existing_proof_job_charge_is_accounted_after_last_envelope(self):
        a=archive(self.root/'proof');w=writer_for(self.root,a)
        witness=Witness('fixture','2020-01-01T00:00:00Z','epoch',1000,'market',1,2,999,900000)
        self.assertTrue(w.submit(witness,[]));self.assertTrue(w.close(10))
        s=w.status();self.assertTrue(s['terminal_accounting_complete'])
        self.assertEqual(s['admitted_observations'],1)
        self.assertEqual(s['durable_batch']['durable_charge_bytes'],w.max_bytes)

    def test_normal_quote_capture_drain_and_seal_have_exact_counters(self):
        c=Capture(config(self.root/'capture'),'main',offline=True)
        try:
            for i in range(20):
                self.assertTrue(c.emit('QUOTE_RECEIVE',raw='x'*1500,ticker='fixture',epoch='one',received_at=float(i)))
        finally:s=c.stop(timeout=10)
        self.assertEqual(s['status'],'SEALED')
        self.assertTrue(s['writer']['terminal_accounting_complete'])
        self.assertEqual(s['writer']['not_yet_durable_charge_bytes'],0)
        self.assertEqual(s['writer']['admitted_observations'],21)  # includes stop boundary
        seal=json.loads((c.root/'seal.json').read_bytes())
        self.assertEqual(seal['status'],'SEALED')
        for item in seal['files']:
            self.assertEqual(item['sha256'],file_sha(c.root/item['path']))

    def test_terminal_counter_mismatch_cannot_seal(self):
        c=Capture(config(self.root/'capture'),'main',offline=True)
        c.writer.admitted['charge_bytes']+=1  # deliberate accounting fault
        s=c.stop(timeout=10)
        self.assertEqual(s['status'],'INCOMPLETE')
        self.assertEqual(s['failure'],'DURABILITY_ACCOUNTING_INCOMPLETE')
        self.assertFalse(s['writer']['terminal_accounting_complete'])
        self.assertEqual(json.loads((c.root/'seal.json').read_bytes())['status'],'INCOMPLETE')

    def test_signed_overcredit_is_not_hidden(self):
        a=archive(self.root/'overcredit');w=writer_for(self.root,a)
        self.assertTrue(w.close(10));a.journal.durable_charge+=1
        self.assertEqual(w.status()['not_yet_durable_charge_bytes'],-1)
        self.assertFalse(w.status()['terminal_accounting_complete'])

    def bare_writer(self):
        w=BufferedProofWriter.__new__(BufferedProofWriter)
        w.queue=queue.Queue(2);w._admission=threading.Lock();w._closing=False
        w.queue_bytes=10000;w.queued_bytes=0;w.peak_queued_bytes=0;w.dropped=0
        w._loss_counters={k:count() for k in GAP_REASONS}
        w.admitted=Counter();w.admission_kinds={}
        return w

    def test_old_put_nowait_blocks_new_admission_rejects_mutex_contention(self):
        w=self.bare_writer();f=Observation('SOURCE_GAP',(('reason','fixture'),),540)
        done=threading.Event();begun=threading.Event()
        def old():
            begun.set();OffPathProofWriter._enqueue(w,f,540);done.set()
        w.queue.mutex.acquire();t=threading.Thread(target=old);t.start()
        try:
            self.assertTrue(begun.wait(1));self.assertFalse(done.wait(.02))
        finally:w.queue.mutex.release();t.join(1)
        self.assertTrue(done.is_set())
        w=self.bare_writer();w.queue.mutex.acquire()
        try:self.assertFalse(w._enqueue(f,540))
        finally:w.queue.mutex.release()
        self.assertEqual(next(w._loss_counters['ADMISSION_BUSY']),1)
        self.assertEqual(w.queue.qsize(),0);self.assertEqual(w.admitted['observations'],0)

    def test_queue_bounds_order_and_loss_counters_preserved(self):
        w=self.bare_writer()
        for i in range(2):self.assertTrue(w._enqueue(Observation('SOURCE_GAP',(),i+1),i+1))
        self.assertFalse(w._enqueue(Observation('SOURCE_GAP',(),3),3))
        self.assertEqual(next(w._loss_counters['QUEUE_OVERFLOW']),1)
        self.assertEqual([w.queue.get_nowait()[1] for _ in range(2)],[1,2])
        self.assertEqual(w.queued_bytes,3);self.assertEqual(w.admitted['observations'],2)

    def test_wall_guard_still_stops_on_off_cpu_delay(self):
        g=Gate(SimpleNamespace())
        with patch('ops.live_recording.capture.time.perf_counter_ns',return_value=6000001),patch('ops.live_recording.capture.time.thread_time_ns',return_value=2000):
            g.overhead(0,'QUOTE_ACCEPT',1000)
        self.assertFalse(g.active);self.assertEqual(g.reason,'HOOK_OVER_5MS:QUOTE_ACCEPT')
        self.assertEqual(g.metrics['QUOTE_ACCEPT:slow_max_thread_cpu_ns'],1000)
        self.assertEqual(g.metrics['QUOTE_ACCEPT:slow_max_off_cpu_ns'],5999001)

    def candle_fixture(self,root,receipt=149.,accepted=150.,start=120.):
        root.mkdir();a=archive(root/'source');a.start()
        wire=canonical([[start,99.,103.,100.,102.,1.]])
        a.observe('ORIGINAL_RESPONSE',dict(raw=wire,received_at=receipt,
            endpoint='https://api.exchange.coinbase.com/products/BTC-USD/candles'))
        row=[start+60,start+60,start,100.,103.,99.,102.,1.]
        a.observe('CANDLE_ACCEPTANCE',dict(raw=canonical([row]),accepted_at=accepted,
            basis='NATIVE_COMPLETED_CACHE_ACCEPTANCE',clock_schema=SCHEMA,producer_sha256=PRODUCER_SHA256))
        a.write('STOP',dict(clean=True));a.close()

    def test_current_bucket_preserved_without_completed_credit_and_replay_identical(self):
        src=self.root/'src';self.candle_fixture(src)
        before={str(p):file_sha(p) for p in src.rglob('*.gz')}
        r=run(src,self.root/'one',window_records=2)
        self.assertEqual(r['campaign_verification']['metrics']['cache_candles_not_completed_at_acceptance'],1)
        self.assertNotIn('RECORD_VERIFICATION',r['campaign_verification']['issue_counts'])
        with sqlite3.connect(self.root/'one/verification.sqlite3') as db:
            value,at,original=db.execute('SELECT v,at,original_http FROM candles').fetchone()
            self.assertEqual(json.loads(value)[:2],[180.,180.]);self.assertEqual(at,150.)
            self.assertEqual(original,0)  # never turn a partial receipt into final OHLCV
        run(src,self.root/'two',window_records=2)
        for name in ('windows.jsonl','issues.jsonl','associations.jsonl'):
            self.assertEqual((self.root/'one'/name).read_bytes(),(self.root/'two'/name).read_bytes())
        self.assertEqual(r,run(src,self.root/'one',resume=True,window_records=2))
        self.assertEqual(before,{str(p):file_sha(p) for p in src.rglob('*.gz')})

    def test_receipt_before_bucket_end_is_not_completed_provenance(self):
        src=self.root/'src';self.candle_fixture(src,receipt=149.,accepted=181.)
        r=run(src,self.root/'out')
        self.assertEqual(r['campaign_verification']['metrics']['completed_cache_rows_upstream_receipt_unknown'],1)
        self.assertEqual(r['campaign_verification']['metrics'].get('original_completed_candles',0),0)

    def test_final_receipt_accepted_but_future_bucket_rejected(self):
        src=self.root/'src';self.candle_fixture(src,receipt=180.,accepted=181.)
        r=run(src,self.root/'out')
        self.assertEqual(r['campaign_verification']['metrics']['original_completed_candles'],1)
        src2=self.root/'src2';self.candle_fixture(src2,start=180.)
        r=run(src2,self.root/'out2')
        self.assertEqual(r['campaign_verification']['issue_counts']['RECORD_VERIFICATION'],1)

    def test_future_candle_cannot_enter_decision_association(self):
        a=dict(opened=0.,decision=150.,captured=151.,closed=900.,completed=[[180.,180.,100.,103.,99.,102.,1.]])
        z=dict(value=dict(anchor=a,anchor_id=sha(canonical(a)),cut=152.,brti={},proof={}))
        with self.assertRaisesRegex(ValueError,'CANDLE_NOT_COMPLETED_AT_DECISION'):
            CampaignVerifier.information(SimpleNamespace(),('fixture',1,1),z)

    def test_original_information_failures_remain_failures(self):
        src=self.root/'src';src.mkdir();a=archive(src/'source');a.start()
        for _ in range(7):a.write('INFORMATION_FAILURE',dict(reason='INPUT_NOT_PUBLISHED'))
        a.write('STOP',dict(clean=True));a.close()
        before={str(p):file_sha(p) for p in src.rglob('*.gz')}
        r=run(src,self.root/'out')
        self.assertEqual(r['campaign_verification']['issue_counts']['INFORMATION_FAILURE'],7)
        self.assertEqual(r['campaign_verification']['status'],'INCOMPLETE')
        self.assertEqual(before,{str(p):file_sha(p) for p in src.rglob('*.gz')})

    def test_authentic_receipts_do_not_claim_raw_loss_recovery(self):
        p=ROOT/'research/native_diagnostic_execution_20261017/receipts'
        for role,deficit in [('main',1982092),('v81',21880904)]:
            s=json.loads((p/(role+'-native-health.json')).read_bytes())['roles'][role]['terminal-status.json']['value']['writer']
            self.assertEqual(s['admitted_charge_bytes']-s['durable_batch']['durable_charge_bytes'],deficit)
            self.assertEqual(s['admitted_observations'],s['durable_batch']['durable_observations'])
            self.assertEqual(s['losses'],{});self.assertEqual(s['unfinished_observations'],0)
        issues=[json.loads(x) for x in (p/'issues.jsonl').read_text().splitlines()]
        self.assertEqual([r['sequence'] for r in issues if r['reason']=='INFORMATION_FAILURE'],[141,158,185,189,209,215,227])

if __name__=='__main__':unittest.main()
