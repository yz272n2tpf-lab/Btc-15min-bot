"""V9 actual RevisionWorker integration tests, isolated SQLite and OFFLINE identity."""
import json,os,sqlite3,tempfile,unittest,zlib
from pathlib import Path
import btc15_ladder_journal_v1 as frozen
from btc15_v2_product.journal import RevisionWorker,install
from .btc15_v9_actual_worker_receipt_research import ReceiptJournal

class Processor:
    def restore(self,saved):self.state=saved or {}
    def process(self,value,now):
        record=dict(kind=value['kind'],contract=value['contract'],published_ts=now,
                    signal_only=True,orders=False)
        if value['kind']=='BRTI_CLOSEOUT':record['brti_closeout']=value['settlement']
        return record,dict(self.state),dict(status='UNAVAILABLE',signal_only=True,orders=False,published_ts=now,expires_at=now+5)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.orig=(frozen.Journal,frozen.Worker)
        self.old_deployment=os.environ.get('RAILWAY_DEPLOYMENT_ID')
        os.environ['RAILWAY_DEPLOYMENT_ID']='OFFLINE'
        install()
        frozen.Journal=ReceiptJournal
        self.worker=RevisionWorker(self.root,'main',Processor())
    def tearDown(self):
        if self.worker.thread.is_alive():
            self.worker.queue.put(None);self.worker.thread.join(timeout=5)
        frozen.Journal,frozen.Worker=self.orig
        if self.old_deployment is None:os.environ.pop('RAILWAY_DEPLOYMENT_ID',None)
        else:os.environ['RAILWAY_DEPLOYMENT_ID']=self.old_deployment
        self.tmp.cleanup()
    def offer(self,contract='A',side='UP'):
        return self.worker.offer(dict(kind='BRTI_CLOSEOUT',contract=contract,
            settlement=dict(final60_side=side,final60_count=60,final60_complete=True)))
    def rows(self):
        with sqlite3.connect(self.root/'main.sqlite3') as db:
            return [json.loads(zlib.decompress(x[0])) for x in db.execute("SELECT body FROM events ORDER BY seq")]
    def test_duplicate_exact_once(self):
        self.assertTrue(self.offer());self.assertTrue(self.offer())
        self.assertIsNone(self.worker.failed)
        rows=self.rows();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['product']['lane'],'main')
        self.assertIs(rows[0]['orders'],False)
    def test_multiple_contracts_and_sequences(self):
        self.assertTrue(self.offer('A'));self.assertTrue(self.offer('B'))
        self.assertEqual([r['contract'] for r in self.rows()],['A','B'])
    def test_restart_receipt_recovery(self):
        self.assertTrue(self.offer('A'))
        self.worker.queue.put(None);self.worker.thread.join(timeout=5)
        self.worker=RevisionWorker(self.root,'main',Processor())
        self.assertTrue(self.offer('A'))
        self.assertEqual(len(self.rows()),1)
    def test_conflict_fails_closed(self):
        self.assertTrue(self.offer('A','UP'))
        with self.assertRaises(RuntimeError):self.offer('A','DOWN')
        self.assertTrue(self.worker.failed)
        self.assertEqual(len(self.rows()),1)
    def test_native_queue_interleaved_with_closeouts(self):
        self.assertTrue(self.offer('A'))
        self.assertTrue(self.worker.offer(dict(kind='NATIVE_DECISION',contract='NATIVE-1')))
        self.worker.queue.join()
        self.assertTrue(self.offer('B'))
        self.assertEqual([r['kind'] for r in self.rows()],
                         ['BRTI_CLOSEOUT','NATIVE_DECISION','BRTI_CLOSEOUT'])
        self.assertIsNone(self.worker.failed)
    def test_atomic_receipt_failure_rolls_back_event(self):
        self.assertTrue(self.offer('A'))
        with sqlite3.connect(self.root/'main.sqlite3') as db:
            db.execute("""CREATE TRIGGER fail_receipt_v9 BEFORE INSERT ON closeout_receipts_v9
                WHEN NEW.contract='B' BEGIN SELECT RAISE(ABORT,'FORCED_RECEIPT_FAILURE'); END""")
        with self.assertRaises(RuntimeError):
            self.offer('B')
        self.assertTrue(self.worker.failed)
        self.assertEqual([r['contract'] for r in self.rows()],['A'])
if __name__=='__main__':unittest.main()