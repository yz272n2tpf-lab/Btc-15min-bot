"""Research-only integration test against the ACTUAL V2 RevisionWorker.

Run from the repository root on an isolated research checkout:
  python -m unittest -v research.main_closeout_incremental_20261015.test_v8_actual_worker_contract

No Railway, no live journal, no network or orders. The test intentionally
documents the CURRENT missing idempotency guarantee; it is not a production GO.
"""
import json
import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

import btc15_ladder_journal_v1 as frozen
from btc15_v2_product.journal import RevisionJournal, RevisionWorker, install


class Processor:
    def restore(self, saved):
        self.state = saved or {}

    def process(self, value, now):
        kind = value['kind']
        record = dict(kind=kind, contract=value['contract'],
                      published_ts=now, signal_only=True, orders=False)
        if kind == 'BRTI_CLOSEOUT':
            record['brti_closeout'] = value['settlement']
        state = dict(self.state)
        view = dict(status='UNAVAILABLE', reason='RESEARCH_FIXTURE',
                    signal_only=True, orders=False)
        return record, state, view


class ActualWorkerContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.orig_journal = frozen.Journal
        self.orig_worker = frozen.Worker
        install()
        self.worker = RevisionWorker(self.root, 'main', Processor())

    def tearDown(self):
        self.worker.queue.put(None)
        self.worker.thread.join(timeout=5)
        frozen.Journal = self.orig_journal
        frozen.Worker = self.orig_worker
        self.tmp.cleanup()

    def closeout(self):
        return dict(kind='BRTI_CLOSEOUT', contract='RESEARCH-ONLY',
                    settlement=dict(final60_count=60, final60_complete=True,
                                    final60_side='UP'))

    def test_actual_worker_commits_and_currently_allows_duplicate_closeout(self):
        self.assertTrue(self.worker.offer(self.closeout()))
        self.assertTrue(self.worker.offer(self.closeout()))
        self.assertIsNone(self.worker.failed)
        with sqlite3.connect(self.root / 'main.sqlite3') as db:
            records = [json.loads(zlib.decompress(blob))
                       for (blob,) in db.execute(
                           "SELECT body FROM events WHERE kind='BRTI_CLOSEOUT' ORDER BY seq")]
            self.assertEqual(len(records), 2)  # Baseline deficiency, not desired behavior.
            self.assertTrue(all(r['product']['lane'] == 'main' for r in records))
            self.assertTrue(all(r['orders'] is False for r in records))
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'closeout_receipts%'"
            ).fetchone()[0], 0)


    def test_direct_v2_journal_commit_diagnostic(self):
        # Separate file so this test exposes the actual SQLite exception.
        from btc15_v2_product.journal import ProcessorEnvelope
        from time import time
        path = self.root / 'diagnostic.sqlite3'
        journal = RevisionJournal(path, 'main')
        try:
            processor = Processor()
            processor.restore({})
            record, state, view = ProcessorEnvelope(processor, 'main').process((self.closeout(), None), time())
            seq = journal.commit(record, state)
            self.assertGreater(seq, 0)
        finally:
            journal.close()

if __name__ == '__main__':
    unittest.main()