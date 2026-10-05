"""Counterexample for the deployed V8.1 journal queue latch (offline only).

The commit delay is injected, not attributed to a production disk operation.
This reproduces the permanent failure after queue saturation; it is not a fix.
"""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import btc15_ladder_journal_v1 as frozen
from btc15_scalp_journal_v1 import Scalp
from btc15_v2_product.journal import RevisionJournal, RevisionWorker, public_view
from test_btc15_scalp_journal_v1 import ENTRY, state


def drained(worker):
    deadline = time.monotonic() + 5
    with worker.queue.all_tasks_done:
        while worker.queue.unfinished_tasks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError('worker did not drain within diagnostic bound')
            worker.queue.all_tasks_done.wait(remaining)


class PublicationStallTests(unittest.TestCase):
    def test_full_queue_permanently_rejects_and_discards_already_accepted_frames(self):
        entered, release = threading.Event(), threading.Event()
        processed = []
        clock = [ENTRY + .001]

        class TracedScalp(Scalp):
            def process(self, frame, now):
                processed.append(frame['captured_ts'])
                return super().process(frame, now)

        class DelayedCommit(RevisionJournal):
            def commit(self, record, saved):
                if len(processed) == 2:
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError('diagnostic commit barrier timed out')
                return super().commit(record, saved)

        with tempfile.TemporaryDirectory() as td, patch.object(frozen, 'Journal', DelayedCommit):
            worker = RevisionWorker(td, 'v81', TracedScalp(), lambda: clock[0])
            try:
                self.assertTrue(worker.offer(state(ENTRY, eligible=False)))
                drained(worker)
                self.assertEqual(public_view(td, 'v81', clock[0])['guidance'], 'PASS')

                clock[0] = ENTRY + 1.001
                stale = state(ENTRY + 1, seq=2, eligible=False)
                stale['row']['input_provenance']['quote']['source_ts_ms'] = int((ENTRY - 6) * 1000)
                self.assertTrue(worker.offer(stale))
                self.assertTrue(entered.wait(5))
                for number in range(16):
                    self.assertTrue(worker.offer(state(ENTRY + 2 + number, seq=3 + number)))
                self.assertEqual(worker.queue.qsize(), 16)
                self.assertFalse(worker.offer(state(ENTRY + 18, seq=19)))
                self.assertEqual(worker.failed, 'JOURNAL_QUEUE_FULL')
                release.set()
                drained(worker)

                snapshot = (Path(td) / 'v81.json').read_bytes()
                value = json.loads(snapshot)
                self.assertEqual(value['reason'], 'QUOTE_SOURCE_UNQUALIFIED')
                self.assertEqual(value['journal']['sequence'], 2)
                self.assertEqual(value['journal']['queue_depth'], 16)
                self.assertEqual(value['journal']['drops'], 1)
                self.assertEqual(worker.queue.qsize(), 0)
                self.assertEqual((worker.accepted, worker.written, worker.dropped), (18, 2, 1))
                self.assertEqual(processed, [ENTRY, ENTRY + 1])
                for number in range(100):
                    self.assertFalse(worker.offer(state(ENTRY + 19 + number, seq=20 + number)))
                self.assertEqual((Path(td) / 'v81.json').read_bytes(), snapshot)
                self.assertTrue(worker.thread.is_alive())
                self.assertEqual(public_view(td, 'v81', ENTRY + 200)['reason'], 'QUOTE_SOURCE_UNQUALIFIED')
                with sqlite3.connect(Path(td) / 'v81.sqlite3') as db:
                    self.assertEqual(db.execute('SELECT seq FROM events ORDER BY seq').fetchall(), [(1,), (2,)])
                result = dict(
                    status='COUNTEREXAMPLE_REPRODUCED_NOT_REPAIRED',
                    injected_trigger='commit barrier; production pressure trigger not established',
                    accepted=worker.accepted, committed=worker.written,
                    accepted_but_discarded=16, drops=worker.dropped,
                    later_valid_offers_rejected=100,
                    snapshot_queue_depth=value['journal']['queue_depth'], actual_queue_depth=0,
                    frozen_reason=value['reason'], worker_alive=True,
                    publication_sequences=[1, 2], native_upstream_calls=0,
                    source_gate_weakened=False, signal_only=True, orders=False)
                output = Path(__file__).parent / 'qualification/two_blockers_20261005'
                output.mkdir(parents=True, exist_ok=True)
                (output / 'v81-stall-counterexample.json').write_text(json.dumps(result, indent=2) + '\n')
            finally:
                release.set()
                # offer(None) is itself rejected by the latch; stop the test thread directly.
                worker.queue.put(None, timeout=5)
                worker.thread.join(5)
                self.assertFalse(worker.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
