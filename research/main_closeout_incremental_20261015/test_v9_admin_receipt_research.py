"""Research-only V9 journal receipt regression assertions.
Run with existing isolated actual-worker suite; no production imports modified.
"""
import unittest
from .test_v9_actual_worker_receipts import Tests as BaseTests
from btc15_v2_product.journal import ADMINS

class ExtendedWorkerTests(BaseTests):
    def test_admin_pipeline_single_receipt(self):
        class Admin:
            def __init__(self):self.calls=[]
            def pipeline(self,record,seq,now):self.calls.append((record['contract'],seq))
            def offer(self,receipt):pass
        old=ADMINS.get('main')
        admin=Admin()
        try:
            ADMINS['main']=admin
            self.assertTrue(self.offer('ADMIN'))
            self.assertTrue(self.offer('ADMIN'))
            self.assertEqual(admin.calls,[('ADMIN',1)])
            self.assertEqual(len(self.rows()),1)
        finally:
            if old is None:ADMINS.pop('main',None)
            else:ADMINS['main']=old
    def test_restart_keeps_same_event_envelope(self):
        import sqlite3
        self.assertTrue(self.offer('RESTART'))
        before=self.rows()[0]
        self.worker.queue.put(None)
        self.worker.thread.join(timeout=5)
        from btc15_v2_product.journal import RevisionWorker
        from .test_v9_actual_worker_receipts import Processor
        self.worker=RevisionWorker(self.root,'main',Processor())
        self.assertTrue(self.offer('RESTART'))
        self.assertEqual(self.rows(),[before])
        with sqlite3.connect(self.root/'main.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM closeout_receipts_v9').fetchone()[0],1)

if __name__=='__main__':unittest.main()
