"""Offline capture/reader tests. Scripted observations are not EARLY trades."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import pandas as pd
from completion_audit.fair_input_candidate import completed_candles
from ops.live_recording.adapters import Adapters
from ops.live_recording.candle_schema import SCHEMA, PRODUCER_SHA256, acceptance_rows, decode
from ops.live_recording.capture import Gate
from ops.live_recording.policy import canonical, file_sha, PROFILES, validate
from ops.live_recording.windowed_campaign import run, WindowedCampaignVerifier
from research.bounded_reader_recovery_20261016.test_recovery import main_fixture
from research.main_closeout_incremental_20261015.test_recorder_burst_batch_research import archive,writer_for

ROOT=Path(__file__).resolve().parents[2]


def raw_candles():
    return pd.DataFrame([[100.,103.,99.,102.,1.],[102.,105.,101.,104.,2.]],
       columns=['Open','High','Low','Close','Volume'],
       index=pd.date_range('2026-09-01T00:00:00Z',periods=2,freq='min'))


class PreflightTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def captured(self):
        native=raw_candles();completed=completed_candles(native);events=[]
        gate=types.SimpleNamespace(active=True,gap=lambda why:self.fail(why))
        capture=types.SimpleNamespace(gate=gate,emit=lambda kind,**kw:events.append((kind,kw)))
        Adapters(capture).completed(completed,native)
        return native,completed,events

    def test_pinned_original_clock_and_frames_unchanged(self):
        self.assertEqual(file_sha(ROOT/'completion_audit/fair_input_candidate.py'),PRODUCER_SHA256)
        raw=raw_candles();native=completed_candles(raw);before=raw.copy(deep=True);accepted=native.copy(deep=True)
        rows=list(acceptance_rows(native,raw))
        self.assertTrue(all(r[0]==r[1]==r[2]+60 for r in rows))
        pd.testing.assert_frame_equal(before,raw);pd.testing.assert_frame_equal(accepted,native)
        self.assertEqual(decode(rows[0])[0],[native.index[0].timestamp(),native.iloc[0].source_utc.timestamp(),100.,103.,99.,102.,1.])

    def test_v2_native_row_matches_original_http_without_clock_relabel(self):
        raw,native,events=self.captured();source=self.root/'source';source.mkdir()
        a=archive(source/'source');a.start()
        # This is an explicit synthetic HTTP receipt for testing exact joins.
        payload=[[idx.timestamp(),r.Low,r.High,r.Open,r.Close,r.Volume] for idx,r in raw.iterrows()]
        fields=events[0][1];at=fields['accepted_at']
        a.observe('ORIGINAL_RESPONSE',dict(raw=canonical(payload),received_at=at-.1,
                    endpoint='https://api.exchange.coinbase.com/products/BTC-USD/candles'))
        a.observe(*events[0]);a.write('STOP',dict(clean=True));a.close()
        result=run(source,self.root/'out',window_records=2)
        self.assertEqual(result['campaign_verification']['metrics']['original_completed_candles'],2)
        with sqlite3.connect(self.root/'out/verification.sqlite3') as db:
            row=json.loads(db.execute('SELECT v FROM candles ORDER BY q LIMIT 1').fetchone()[0])
        self.assertEqual(row[0],row[1]);self.assertEqual(row[0],native.index[0].timestamp())
        self.assertEqual(result,run(source,self.root/'out',resume=True,window_records=2))

    def test_v2_wrong_clock_and_changed_value_are_rejected(self):
        raw=raw_candles();native=completed_candles(raw);native.iloc[0,native.columns.get_loc('Close')]=101.
        with self.assertRaisesRegex(ValueError,'COMPLETED_ORIGINAL_OHLCV'):list(acceptance_rows(native,raw))
        row=list(acceptance_rows(completed_candles(raw),raw))[0];row[1]-=60
        with self.assertRaisesRegex(ValueError,'COMPLETED_V2_ORIGINAL_END_CLOCK'):decode(row)

    def test_v2_missing_original_http_is_not_credited(self):
        raw,native,events=self.captured();source=self.root/'source';source.mkdir()
        a=archive(source/'source');a.start();a.observe(*events[0]);a.write('STOP',dict(clean=True));a.close()
        result=run(source,self.root/'out')
        self.assertEqual(result['campaign_verification']['metrics']['completed_cache_rows_upstream_receipt_unknown'],2)
        self.assertEqual(result['campaign_verification']['metrics'].get('original_completed_candles',0),0)

    def test_unknown_v2_schema_remains_quarantined(self):
        raw,native,events=self.captured();events[0][1]['clock_schema']='UNREVIEWED'
        source=self.root/'source';source.mkdir();a=archive(source/'source');a.start()
        a.observe(*events[0]);a.write('STOP',dict(clean=True));a.close()
        result=run(source,self.root/'out')
        self.assertEqual(result['campaign_verification']['issue_counts']['RECORD_VERIFICATION'],1)

    def test_candle_seam_only_observes_original_native_assignment(self):
        original=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_text()
        tree=ast.parse(original)
        adapter=Adapters(types.SimpleNamespace())
        changed=adapter.instrument(lambda t,l:t,tree,'main')
        calls=[n for n in ast.walk(changed) if isinstance(n,ast.Call) and ast.unparse(n.func)=='_recording_adapter.completed']
        self.assertEqual(len(calls),1)
        self.assertEqual([ast.unparse(n) for n in calls[0].args],['_fair_btc','_fair_raw_btc'])

    def test_global_lease_refuses_different_output_before_sqlite_open(self):
        source=self.root/'source';source.mkdir();main_fixture(source)
        owner=WindowedCampaignVerifier(source,self.root/'one')
        try:
            with self.assertRaisesRegex(ValueError,'SERIAL_READER_REQUIRED'):
                run(source,self.root/'two')
            self.assertFalse((self.root/'two').exists())
        finally:owner.close()
        run(source,self.root/'two')

    def test_global_lease_survives_distinct_processes_and_releases_on_kill(self):
        source=self.root/'source';source.mkdir();main_fixture(source)
        script='''
import sys
from ops.live_recording.windowed_campaign import WindowedCampaignVerifier
v=WindowedCampaignVerifier(sys.argv[1],sys.argv[2])
print('LOCKED',flush=True)
sys.stdin.read()
v.close()
'''
        child=subprocess.Popen([sys.executable,'-B','-c',script,str(source),str(self.root/'one')],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'LOCKED')
            with self.assertRaisesRegex(ValueError,'SERIAL_READER_REQUIRED'):run(source,self.root/'two')
        finally:
            child.kill();child.communicate(timeout=10)
        self.assertEqual(child.returncode,-signal.SIGKILL)
        run(source,self.root/'two')

    def test_initialization_error_does_not_leak_serial_lease(self):
        source=self.root/'source';source.mkdir();main_fixture(source)
        with self.assertRaisesRegex(ValueError,'RECOVERY_DB_BUDGET'):run(source,self.root/'bad',work_db_bytes=1)
        run(source,self.root/'good')

    def test_first_loss_closes_capture_admission_and_preserves_reason(self):
        writer=types.SimpleNamespace(gap=lambda r:None,submit_observation=lambda *a,**k:False)
        gate=Gate(writer)
        self.assertFalse(gate.submit_observation('ORIGINAL_RESPONSE',raw=b'x'))
        self.assertFalse(gate.active);self.assertEqual(gate.reason,'RECORDER_ADMISSION_REJECTED:ORIGINAL_RESPONSE')
        writer.submit_observation=lambda *a,**k:self.fail('admission after loss')
        self.assertFalse(gate.submit_observation('QUOTE_ACCEPT',raw=b'x'))

    def test_native_sequence_gap_immediately_closes_capture(self):
        losses=[]
        writer=types.SimpleNamespace(gap=losses.append,submit_observation=lambda *a,**k:True)
        gate=Gate(writer);fields=dict(original_journal='fixture',record_basis='POST_ORIGINAL_COMMIT')
        self.assertTrue(gate.submit_observation('NATIVE_RECORD',sequence=1,**fields))
        self.assertFalse(gate.submit_observation('NATIVE_RECORD',sequence=3,**fields))
        self.assertFalse(gate.active);self.assertEqual(losses,['CAPTURE_ERROR'])

    def test_completed_admissions_are_durable_after_drain(self):
        a=archive(self.root/'source');writer=writer_for(self.root,a)
        for i in range(400):
            self.assertTrue(writer.submit_observation('SOURCE_GAP',reason='DECLARED_TELEMETRY_FIXTURE',observed_at=i))
        self.assertTrue(writer.close(timeout=15));s=writer.status();b=s['durable_batch']
        self.assertEqual(s['losses'],{});self.assertEqual(s['admitted_observations'],400)
        self.assertEqual(b['durable_observations'],400)
        self.assertEqual(b['durable_charge_bytes'],s['admitted_charge_bytes'])
        self.assertEqual(s['not_yet_durable_charge_bytes'],0)
        self.assertEqual(s['unfinished_observations'],0);self.assertGreater(b['fsync_calls'],0)

    def test_pending_batch_is_not_reported_durable(self):
        a=archive(self.root/'source');a.start()
        a.write('SOURCE_GAP',dict(reason='DECLARED_PENDING_FIXTURE'))
        a.journal.observation_processed(1234)
        s=a.journal.evidence_batch_status()
        self.assertEqual(s['durable_charge_bytes'],0);self.assertEqual(s['processed_charge_bytes'],1234)
        a.write('STOP',dict(clean=True));a.close()
        self.assertEqual(a.journal.evidence_batch_status()['durable_charge_bytes'],1234)

    def test_oversize_diagnostic_exposes_shape_not_content(self):
        a=archive(self.root/'source');writer=writer_for(self.root,a)
        raw=b'private-body-'*(400000)
        self.assertFalse(writer.submit_observation('ORIGINAL_RESPONSE',raw=raw,received_at=1))
        self.assertTrue(writer.close(timeout=15));s=writer.status()
        self.assertEqual(s['oversize_by_kind']['ORIGINAL_RESPONSE']['max_raw_length'],len(raw))
        self.assertNotIn('private-body',json.dumps(s));self.assertGreater(s['losses']['OVERSIZE'],0)

    def test_prepared_profiles_are_finite_and_keep_original_profiles(self):
        self.assertEqual(PROFILES['preflight']['compressed']['v81'],64*1024**2)
        self.assertEqual(PROFILES['early_diagnostic']['seconds'],60)
        self.assertEqual(PROFILES['early_preflight']['seconds'],1200)
        self.assertEqual(PROFILES['early_preflight']['producer_reserve'],2*1024**3)
        self.assertGreater(PROFILES['early_preflight']['records_by_role']['v81'],3150000)

    def test_preflight_bridge_uses_bounded_reader_without_old_index(self):
        work=self.root/'work';work.mkdir();source=work/'run';source.mkdir();main_fixture(source)
        proc=subprocess.run([sys.executable,'-B','-m','ops.live_recording.finish',
             '--read-only',str(work),'--profile','early_preflight'],capture_output=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stderr.decode())
        self.assertFalse((work/'index').exists())
        result=json.loads((work/'verification/summary.json').read_bytes())
        self.assertTrue(result['checkpoint_resume_implemented'])
        self.assertEqual(result['metrics']['native_associations'],6)

    def test_preflight_records_flow_telemetry_and_retains_strict_duration(self):
        from research.early_reader_qualification_20261016.test_restart_and_drain import config
        from ops.live_recording.capture import Capture
        from candidates.early_recording_20261012.archive import read_archive
        cfg=config(self.root/'campaign');cfg.update(profile='early_diagnostic',duration_seconds=60)
        c=Capture(cfg,'main',offline=True)
        try:
            deadline=time.monotonic()+3
            while not c.writer.admission_kinds.get('RECORDING_HEALTH') and time.monotonic()<deadline:time.sleep(.02)
        finally:status=c.stop(timeout=10)
        self.assertEqual(status['status'],'SEALED')
        records=read_archive(c.root/'source')['records']
        health=[r['payload'] for r in records if r['kind']=='RECORDING_HEALTH']
        self.assertEqual(health[0]['schema'],'BTC15_CAPTURE_FLOW_V1')
        self.assertIn('durable_charge_bytes',health[0]['writer']['durable_batch'])
        cfg['duration_seconds']=61
        with self.assertRaisesRegex(ValueError,'DURATION'):validate(cfg,'main',offline=True)


if __name__=='__main__':unittest.main()
