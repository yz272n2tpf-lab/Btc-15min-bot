"""V11 isolated V3-outbox to actual V2 worker integration tests."""
import hashlib,json,sqlite3,time
from .test_v9_actual_worker_receipts import Tests as WorkerTests
from .btc15_v11_outbox_actual_worker_bridge_research import dispatch_pending
from .btc15_closeout_outbox_research_v3 import OUTBOX_SCHEMA, EvidenceChanged

class Tests(WorkerTests):
    def setUp(self):
        super().setUp()
        self.outbox=self.root/'outbox.sqlite3'
        with sqlite3.connect(self.outbox) as db:
            db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
            db.execute('CREATE TABLE items(contract TEXT PRIMARY KEY,payload TEXT NOT NULL,sha256 TEXT NOT NULL,source_offset INTEGER NOT NULL,journal_seq INTEGER,created REAL NOT NULL)')
            db.executemany('INSERT INTO meta VALUES (?,?)',[('schema',OUTBOX_SCHEMA),('historical_cutover','EXPLICIT_NO_BACKFILL')])
        self.insert('A')
        # Explicit bounded readiness handshake: schema must be created by the
        # actual worker's journal thread, not by the outbox or a second writer.
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if self.worker.failed:
                self.fail('WORKER_FAILED_BEFORE_RECEIPT_READY:'+str(self.worker.failed))
            try:
                with sqlite3.connect(self.root/'main.sqlite3') as db:
                    ready=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='closeout_receipts_v9'").fetchone()
                if ready:break
            except sqlite3.OperationalError:
                pass
            time.sleep(.01)
        else:
            self.fail('RECEIPT_SCHEMA_NOT_INITIALIZED_BY_OWNER')
    def insert(self,contract,side='UP'):
        row=dict(contract=contract,brti=dict(final60_side=side,final60_count=60,final60_complete=True))
        body=json.dumps(row,sort_keys=True,separators=(',',':'))
        with sqlite3.connect(self.outbox) as db:
            db.execute('INSERT INTO items VALUES (?,?,?,?,NULL,0)',(contract,body,hashlib.sha256(body.encode()).hexdigest(),100))
    def pending(self):
        with sqlite3.connect(self.outbox) as db:
            return db.execute('SELECT contract,journal_seq FROM items ORDER BY contract').fetchall()
    def dispatch(self,hook=None):
        return dispatch_pending(self.outbox,self.root/'main.sqlite3',self.worker.offer,hook=hook)
    def test_real_worker_receipt_and_outbox_ack(self):
        self.assertEqual(self.dispatch(),['A'])
        self.assertEqual(self.pending(),[('A',1)])
        self.assertEqual(len(self.rows()),1)
    def test_ack_crash_recovers_without_second_event(self):
        def crash(stage,contract):
            if stage=='AFTER_JOURNAL':raise RuntimeError('SIMULATED_CRASH')
        with self.assertRaises(RuntimeError):self.dispatch(crash)
        self.assertEqual(self.pending(),[('A',None)])
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.dispatch(),['A'])
        self.assertEqual(self.pending(),[('A',1)])
        self.assertEqual(len(self.rows()),1)
    def test_replay_idempotent(self):
        self.dispatch()
        self.assertEqual(self.dispatch(),[])
        self.assertEqual(len(self.rows()),1)
    def test_worker_refusal_leaves_pending(self):
        self.worker.failed='TEST_WORKER_STOPPED'
        with self.assertRaises(EvidenceChanged):self.dispatch()
        self.assertEqual(self.pending(),[('A',None)])
    def test_multiple_contracts(self):
        self.insert('B')
        self.assertEqual(self.dispatch(),['A','B'])
        self.assertEqual(self.pending(),[('A',1),('B',2)])
    def test_outbox_digest_conflict_fails_closed(self):
        with sqlite3.connect(self.outbox) as db:db.execute("UPDATE items SET sha256='invalid' WHERE contract='A'")
        with self.assertRaises(EvidenceChanged):self.dispatch()
        self.assertEqual(self.pending(),[('A',None)])
if __name__=='__main__':
 import unittest;unittest.main()