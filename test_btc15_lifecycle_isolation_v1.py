"""Offline durable handoff, failure/restart/backlog and unchanged semantic tests."""
import ast
from copy import deepcopy
from datetime import timedelta
import hashlib
import inspect
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from btc15_directional_signal_authority_v1 import initialize, Authority, pack
from btc15_isolated_lifecycle_consumer_v1 import Consumer, server_for
from btc15_protected_publication_handoff_v1 import envelope,decode
import btc15_qualified_forward_observer_v1 as observer
from test_btc15_directional_signal_authority_v1 import fixture,START


class IsolatedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'publication.csv';self.db=self.root/'ledger';self.cursor=self.root/'cursor'
        self.now=START+timedelta(seconds=300);initialize(self.db,START)
        self.consumer=self.make_consumer('one')

    def tearDown(self):self.tmp.cleanup()

    def make_consumer(self,epoch):
        return Consumer(self.source,self.db,self.cursor,epoch=epoch,build={},clock=lambda:self.now)

    def publish(self,offset=300,**kwargs):
        raw=fixture(offset,**kwargs);at=START+timedelta(seconds=offset)
        record=observer.observation(raw,at);record['record_type']='OBSERVATION'
        # Exact whitespace-bearing original bytes must survive CSV quoting.
        body=json.dumps(raw,indent=1).encode()
        record['protected_publication_bytes']=envelope(body)
        observer.append(record,self.source)
        return raw,record,body

    def consume(self):
        out=self.consumer.step()
        return self.consumer.step() if out['status']=='HEADER' else out

    def state(self):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT value FROM meta WHERE key='state'").fetchone()[0]

    def test_raw_bytes_preserved_and_receipt_not_replaced(self):
        raw,record,body=self.publish()
        self.assertEqual(decode(record),(raw,body))
        self.now+=timedelta(seconds=1)
        out=self.consume();self.assertEqual(out['event'],'BUY')
        self.assertEqual(out['origin']['observer_received_utc'],record['observed_utc'])
        self.assertEqual(out['origin']['signal_timestamp_utc'],self.now.isoformat())

    def test_legacy_csv_and_information_frames_cannot_manufacture_missing_publication(self):
        raw=fixture();record=observer.observation(raw,self.now);record['record_type']='OBSERVATION'
        observer.append(record,self.source)
        out=self.consume();self.assertEqual(out['status'],'UNAVAILABLE')
        self.assertIn('FULL_PROTECTED_PUBLICATION_UNAVAILABLE',out['reason'])
        with self.assertRaises(ValueError):decode({'schema':'BTC15_INFORMATION_JOURNAL_V1','frame':raw})

    def test_duplicate_and_rapid_final_changes_remain_ordered(self):
        events=[]
        for offset,kwargs in ((300,{}),(300,{}),(300.000001,{'final_ready':True}),
                              (300.000002,{'final_side':'DOWN'})):
            self.publish(offset,**kwargs);self.now=START+timedelta(seconds=offset)
            events.append(self.consume()['event'])
        self.assertEqual(events,['BUY',None,'HOLD','PROTECT'])
        self.assertEqual(self.consumer.view()['guidance'],'PROTECT')

    def test_consumer_absent_paused_hung_cannot_block_publisher_and_guidance_expires(self):
        self.publish();self.consume();original=self.state()
        for i in range(50):self.publish(305+i*5)
        self.assertEqual(self.state(),original) # consumer did no work
        self.now+=timedelta(seconds=16)
        self.assertEqual(self.consumer.view()['status'],'UNAVAILABLE')
        self.assertGreater(self.source.stat().st_size,10000)

    def test_backlog_is_checked_at_current_time_and_does_not_create_old_buys(self):
        for i in range(10):self.publish(300+i*5)
        self.now=START+timedelta(seconds=400)
        for _ in range(10):
            out=self.consume();self.assertEqual(out['status'],'UNAVAILABLE');self.assertIsNone(out.get('event'))
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM origins').fetchone()[0],0)
        self.publish(400);self.assertEqual(self.consume()['event'],'BUY')

    def test_restart_after_commit_before_cursor_checkpoint_is_idempotent(self):
        self.publish();self.assertEqual(self.consumer.step()['status'],'HEADER')
        with patch.object(self.consumer,'_save',side_effect=RuntimeError('crash after commit')):
            with self.assertRaises(RuntimeError):self.consumer.step()
        self.consumer=self.make_consumer('two')
        out=self.consume();self.assertIsNone(out['event'])
        self.assertEqual(out['origin']['signal_runtime_epoch'],'one')
        self.assertEqual(out['signal_runtime_epoch'],'two')

    def test_consumer_sink_locked_or_failed_never_writes_source(self):
        self.publish();self.consumer.step();before=self.source.read_bytes()
        db=sqlite3.connect(self.db);db.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(sqlite3.OperationalError):self.consumer.step()
        finally:db.rollback();db.close()
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(self.consume()['event'],'BUY')
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'storage'); END")
        original=self.state();self.publish(305,final_ready=True);before=self.source.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):self.consumer.step()
        self.assertEqual(self.state(),original);self.assertEqual(self.source.read_bytes(),before)

    def test_actual_process_crash_after_commit_restarts_without_duplicate_buy(self):
        self.publish();self.consumer.step()
        code='''import os,sys
from datetime import datetime
from btc15_isolated_lifecycle_consumer_v1 import Consumer
c=Consumer(sys.argv[1],sys.argv[2],sys.argv[3],epoch='crashed-process',build={},clock=lambda:datetime.fromisoformat(sys.argv[4]))
c._save=lambda value:os._exit(17)
c.step()
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.source),str(self.db),str(self.cursor),self.now.isoformat()],
                              cwd=Path(__file__).parent,timeout=10)
        self.assertEqual(result.returncode,17)
        self.consumer=self.make_consumer('restarted-process')
        out=self.consume();self.assertIsNone(out['event'])
        self.assertEqual(out['origin']['signal_runtime_epoch'],'crashed-process')
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM origins').fetchone()[0],1)

    def test_malformed_and_partial_record_fail_closed_then_recover(self):
        self.publish();self.consume();state=self.state()
        with self.source.open('ab') as f:f.write(b'broken,row\n')
        self.assertEqual(self.consume()['status'],'UNAVAILABLE');self.assertEqual(self.state(),state)
        self.publish(305,final_ready=True);self.now+=timedelta(seconds=5)
        data=self.source.read_bytes();self.source.write_bytes(data[:-1])
        self.assertEqual(self.consume()['reason'],'PARTIAL_RECORD_WAIT')
        with self.source.open('ab') as f:f.write(b'\n')
        self.assertEqual(self.consume()['event'],'HOLD')

    def test_hash_duplicate_json_keys_and_identity_tampering_are_rejected(self):
        raw,record,body=self.publish()
        bad=deepcopy(record);bad['protected_publication_bytes']['sha256']='0'*64
        with self.assertRaises(ValueError):decode(bad)
        bad=deepcopy(record);bad['contract']='OTHER'
        with self.assertRaises(ValueError):decode(bad)
        bad=deepcopy(record);bad['protected_publication_bytes']=envelope(b'{"contract":"A","contract":"B"}')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):decode(bad)

    def test_file_replacement_or_truncation_cannot_cross_input_identity(self):
        self.publish();self.consume();original=self.state()
        self.source.rename(self.root/'old');self.publish(305)
        self.assertEqual(self.consume()['reason'],'INPUT_IDENTITY_CHANGED');self.assertEqual(self.state(),original)

    def test_quote_wait_brti_expiry_recovery_and_rollover(self):
        self.publish();self.consume();original=self.state()
        for change in ('quote','brti','final'):
            raw=fixture(305,final_ready=True)
            if change=='quote':raw['health']['paired_quotes']=False
            if change=='brti':raw['market']['brti_age_seconds']=5.000001
            if change=='final':raw['final']={}
            at=START+timedelta(seconds=305);record=observer.observation(raw,at)
            record.update(record_type='OBSERVATION',protected_publication_bytes=envelope(pack(raw).encode()))
            observer.append(record,self.source);self.now=at
            self.assertEqual(self.consume()['status'],'UNAVAILABLE');self.assertEqual(self.state(),original)
        self.publish(310,final_ready=True);self.now=START+timedelta(seconds=310)
        self.assertEqual(self.consume()['event'],'HOLD')
        self.publish(1200,close_offset=1800,side='DOWN');self.now=START+timedelta(seconds=1200)
        out=self.consume();self.assertEqual(out['event'],'BUY');self.assertEqual(out['origin']['side'],'DOWN')

    def test_later_evidence_never_changes_accepted_publication(self):
        raw,record,body=self.publish();buy=self.consume()
        self.publish(305,final_ready=True);self.now+=timedelta(seconds=5);hold=self.consume()
        self.assertEqual(hold['origin'],buy['origin'])
        self.assertEqual(hold['origin']['protected_publication']['final'],raw['final'])
        self.assertNotEqual(hold['protected_evidence']['final'],raw['final'])

    def test_separate_projection_endpoint_never_evaluates_or_writes(self):
        self.publish();self.consume();before=self.state()
        server=server_for(self.consumer);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            for _ in range(4):
                with urlopen(f'http://127.0.0.1:{server.server_port}/directional_signal.json') as r:view=json.load(r)
                self.assertEqual(view['guidance'],'BUY');self.assertIsNone(view['event'])
        finally:server.shutdown();server.server_close();worker.join(2)
        self.assertEqual(self.state(),before)

    def test_publisher_has_one_request_one_existing_append_no_consumer_dependency(self):
        raw=fixture();body=pack(raw).encode()
        class Response:
            content=body
            def raise_for_status(self):pass
            def json(self):return raw
        with patch.dict('os.environ',{'BTC15_ENABLE_DIRECTIONAL_SIGNALS':'1'}),\
             patch.object(observer.requests,'get',return_value=Response()) as get,patch.object(observer,'append') as append:
            record=observer.collect_once('http://synthetic/dashboard_state.json')
        self.assertEqual(get.call_count,1);self.assertEqual(append.call_count,1)
        self.assertEqual(decode(record)[1],body)
        source=inspect.getsource(observer)
        self.assertNotIn('Authority(',source);self.assertNotIn('.consume(',source);self.assertNotIn('sqlite3',source)

    def test_engine_manager_and_native_files_are_byte_identical(self):
        root=Path(__file__).parent
        for file in ('btc15_directional_signal_authority_v1.py','BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py',
                     'btc15_directional_signal_publication_v1.py','test_directional_position_manager_v1.py',
                     'bot_two_output_build_v4_13_profit_protection_shadow.py','btc15_information_native_offpath_candidate.py',
                     'btc15_brti_delivery_v1.py','btc15_kalshi_quote_provenance_v1.py','requirements.txt'):
            self.assertEqual((root/file).read_bytes(),subprocess.check_output(['git','show','334bbff:'+file],cwd=root),file)
        self.assertEqual((root/'btc15_information_install_v1.py').read_bytes(),
                         subprocess.check_output(['git','show','abe212b:btc15_information_install_v1.py'],cwd=root))



if __name__=='__main__':unittest.main()
