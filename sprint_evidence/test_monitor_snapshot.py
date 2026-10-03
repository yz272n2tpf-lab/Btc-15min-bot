"""New reader-contention integration controls; prior 257 tests are not rerun."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from sprint_evidence.monitor_snapshot import SnapshotReceiver, read, inspect, MAX_SNAPSHOT
from sprint_evidence.diagnose_sqlite_readers import diagnose
from test_sprint_capture import IDENTITY, MemorySocket
from test_btc15_external_evidence_admission_v1 import POLICY, KEY
from round2_evidence.capture import initialize, DetachedRecorder
from round2_evidence.test_round2 import artifact
from sprint_evidence.passive_capture import Producer, add_event_store


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.db=self.root/'archive.sqlite'; self.view=self.root/'monitor.json'
        initialize(self.db,POLICY);add_event_store(self.db)
        self.sock=MemorySocket();self.p=Producer('unused',IDENTITY,KEY,sock=self.sock)
        self.r=SnapshotReceiver(self.db,[IDENTITY],{(IDENTITY.producer_id,IDENTITY.run_id):KEY},
            common_recorder=DetachedRecorder(self.db,POLICY,acquisition_key=KEY),snapshot_path=self.view)
    def tearDown(self):
        self.p.close();self.tmp.cleanup()
    def emit(self):
        assert self.p.offer('NATIVE_CYCLE',{'synthetic':True})
        return self.r.accept(self.sock.packets[-1])
    def test_real_reader_lock_negative_control_preserved(self):
        self.assertTrue(diagnose()['assertions_pass'])
    def test_monitor_concurrent_reads_cannot_lock_live_archive(self):
        self.assertEqual(self.emit()['status'],'RECORDED_UNQUALIFIED_CLOCK')
        stop=threading.Event(); errors=[]; reads=[]
        def monitor():
            while not stop.is_set():
                try: reads.append(len(read(self.view)['events']))
                except Exception as exc: errors.append(str(exc))
        thread=threading.Thread(target=monitor);thread.start()
        try:
            for _ in range(80):self.assertEqual(self.emit()['status'],'RECORDED_UNQUALIFIED_CLOCK')
        finally:stop.set();thread.join(5)
        self.assertFalse(errors);self.assertTrue(reads);self.assertFalse(thread.is_alive())
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0],81)
        self.assertLessEqual(self.view.stat().st_size,MAX_SNAPSHOT)
        self.assertEqual(inspect(self.view)['state'],'UNAVAILABLE')
    def test_original_common_member_and_receipt_preserved(self):
        member=artifact()[0];self.assertTrue(self.p.common_member(member,0))
        self.assertEqual(self.r.accept(self.sock.packets[-1])['status'],'RECORDED_UNQUALIFIED_CLOCK')
        self.assertEqual(read(self.view)['receipt']['status'],'RECORDED_UNQUALIFIED_CLOCK')
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT original FROM members').fetchone()[0],member)
    def test_failed_snapshot_does_not_undo_or_repeat_acquisition(self):
        with patch('sprint_evidence.monitor_snapshot.os.replace',side_effect=OSError('disk full')):
            result=self.emit()
        self.assertEqual(result['status'],'UNAVAILABLE')
        self.assertFalse(self.view.exists())
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0],1)
        self.assertFalse(list(self.root.glob('.monitor-*')))
    def test_tamper_missing_oversize_and_wrong_destination_fail_closed(self):
        self.assertEqual(inspect(self.view)['state'],'UNAVAILABLE')
        self.emit();data=json.loads(self.view.read_bytes());data['payload']['events']=[]
        self.view.write_text(json.dumps(data));self.assertEqual(inspect(self.view)['reason'],'MONITOR_SNAPSHOT_UNAVAILABLE')
        self.view.write_bytes(b'x'*(MAX_SNAPSHOT+1));self.assertEqual(inspect(self.view)['state'],'UNAVAILABLE')
        self.r.snapshot_path=self.db
        self.assertEqual(self.emit()['status'],'UNAVAILABLE')
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0],2)

if __name__=='__main__':unittest.main()
