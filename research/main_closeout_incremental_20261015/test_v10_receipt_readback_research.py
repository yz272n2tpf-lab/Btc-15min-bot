"""Offline V10 tests against actual V2 worker and isolated V9 journal."""
import sqlite3
import unittest
from .test_v9_actual_worker_receipts import Tests as WorkerTests
from .btc15_v10_receipt_readback_research import verify_receipt,ReceiptUnavailable,ReceiptConflict

class ReceiptReadbackTests(WorkerTests):
    def expected(self,side='UP'):
        return dict(final60_side=side,final60_count=60,final60_complete=True)
    def verify(self,contract='A',side='UP'):
        return verify_receipt(self.root/'main.sqlite3',contract,self.expected(side))
    def test_readback_committed_sequence(self):
        self.assertTrue(self.offer('A'))
        result=self.verify('A')
        self.assertTrue(result['durable'])
        self.assertEqual(result['sequence'],1)
        self.assertFalse(result['orders'])
    def test_replay_same_receipt(self):
        self.assertTrue(self.offer('A'))
        a=self.verify('A')
        self.assertTrue(self.offer('A'))
        self.assertEqual(self.verify('A'),a)
    def test_readback_after_restart(self):
        self.assertTrue(self.offer('A'))
        a=self.verify('A')
        self.worker.queue.put(None);self.worker.thread.join(timeout=5)
        from btc15_v2_product.journal import RevisionWorker
        from .test_v9_actual_worker_receipts import Processor
        self.worker=RevisionWorker(self.root,'main',Processor())
        self.assertEqual(self.verify('A'),a)
    def test_missing_closeout_never_acknowledged(self):
        self.assertTrue(self.offer('A'))
        with self.assertRaises(ReceiptUnavailable):self.verify('B')
    def test_conflicting_payload_never_acknowledged(self):
        self.assertTrue(self.offer('A'))
        with self.assertRaises(ReceiptConflict):self.verify('A','DOWN')
    def test_corrupt_event_digest_never_acknowledged(self):
        self.assertTrue(self.offer('A'))
        self.worker.queue.join()
        with sqlite3.connect(self.root/'main.sqlite3') as db:
            db.execute("UPDATE events SET sha256='tampered' WHERE seq=1")
        with self.assertRaises(ReceiptConflict):self.verify('A')
    def test_missing_event_never_acknowledged(self):
        self.assertTrue(self.offer('A'))
        self.worker.queue.join()
        with sqlite3.connect(self.root/'main.sqlite3') as db:
            db.execute("DELETE FROM events WHERE seq=1")
        with self.assertRaises(ReceiptUnavailable):self.verify('A')

if __name__=='__main__':unittest.main()
