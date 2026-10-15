"""Offline regression of V81 recorder shutdown after queue loss.

No SSH, network, Railway or production data. Existing evidence is immutable.
"""
import hashlib
import json
import tempfile
import threading
import time
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from ops.live_recording.capture import Capture


class FakeGate:
    def __init__(self):
        self.active = True
        self.reason = None
        self.metrics = Counter()
        self.journals = {}
        self.lock = threading.Lock()
        self.disables = 0

    def disable(self):
        self.disables += 1
        self.active = False
        return True


class FinishesAfterTwoLateJoins:
    """Model a writer that outlives the original one-shot 30s recovery."""
    def __init__(self):
        self.alive = True
        self.late_joins = 0

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        if timeout == 30:
            self.late_joins += 1
            if self.late_joins >= 2:
                self.alive = False


class AlreadyFinished:
    def is_alive(self):
        return False

    def join(self, timeout=None):
        pass


def build_capture(root, worker, *, failure=None, losses=None):
    """Construct only stop's dependencies; do not start a live collector."""
    root = Path(root) / 'v81'
    root.mkdir(parents=True)
    (root / 'identity.json').write_text(json.dumps(dict(
        role='v81', run_id='fixture-recorder', identity=dict(build='fixture'))))
    segment = root / 'source.segments' / 'original.jsonl.gz'
    segment.parent.mkdir()
    segment.write_bytes(b'\x1f\x8bfixture-preserved')
    calls = []
    writer = SimpleNamespace(
        _thread=worker, _closing=False,
        submit_observation=lambda *args, **kwargs: calls.append((args, kwargs)),
        status=lambda: dict(losses=dict(losses or {}), archive_failed=False,
                            queued_bytes=1234, peak_queued_bytes=33554430,
                            queue_capacity=16384, queue_byte_budget=33554432))
    capture = Capture.__new__(Capture)
    capture.root = root
    capture.config = dict(run_id='fixture-recorder')
    capture.role = 'v81'
    capture.gate = FakeGate()
    capture.writer = writer
    capture.archive = SimpleNamespace(
        session='fixture-session', seq=9, previous='fixture-hash',
        journal=SimpleNamespace(raw_bytes=10000, stored_bytes=5000, records=9))
    capture.begin = time.monotonic()
    capture.stopped = False
    capture.failure = failure
    capture.stop_event = threading.Event()
    capture.stop_lock = threading.Lock()
    capture.control = threading.current_thread()
    capture.peaks = {'warmup': Counter(), 'steady': Counter()}
    capture.providers = []
    return capture, segment, calls


class DrainRecovery(unittest.TestCase):
    def test_late_worker_exit_still_writes_explicit_incomplete_seal(self):
        with tempfile.TemporaryDirectory() as d:
            worker = FinishesAfterTwoLateJoins()
            capture, segment, calls = build_capture(
                d, worker, failure='RECORDER_LOSS_OR_FAILURE',
                losses={'QUEUE_BYTES': 1470})
            original_hash = hashlib.sha256(segment.read_bytes()).hexdigest()
            first = capture.stop('RECORDER_LOSS_OR_FAILURE', timeout=0)
            self.assertEqual(first['status'], 'INCOMPLETE')
            self.assertTrue(first['drain_timeout_observed'])
            capture.late_sealer.join(3)
            self.assertFalse(capture.late_sealer.is_alive())
            self.assertGreaterEqual(worker.late_joins, 2)
            seal = json.loads((capture.root / 'seal.json').read_text())
            receipt = json.loads((capture.root / 'terminal-status.json').read_text())
            self.assertEqual(seal['status'], 'INCOMPLETE')
            self.assertEqual(receipt['status'], 'INCOMPLETE')
            self.assertEqual(receipt['failure'], 'RECORDER_LOSS_OR_FAILURE')
            self.assertTrue(receipt['drain_timeout_observed'])
            self.assertEqual(receipt['writer']['losses']['QUEUE_BYTES'], 1470)
            self.assertEqual(len(calls), 1)
            self.assertEqual(capture.gate.disables, 1)
            self.assertEqual(hashlib.sha256(segment.read_bytes()).hexdigest(), original_hash)
            paths = {f['path'] for f in seal['files']}
            self.assertIn('source.segments/original.jsonl.gz', paths)
            self.assertEqual(capture.stop('OPERATOR_FINISH')['status'], 'INCOMPLETE')
            self.assertEqual(len(calls), 1)

    def test_unfinished_writer_does_not_receive_forged_seal(self):
        with tempfile.TemporaryDirectory() as d:
            release = threading.Event()
            worker = threading.Thread(target=lambda: release.wait(3), daemon=True)
            worker.start()
            capture, _, _ = build_capture(d, worker, failure='RECORDER_LOSS_OR_FAILURE',
                                          losses={'QUEUE_BYTES': 1})
            try:
                result = capture.stop('RECORDER_LOSS_OR_FAILURE', timeout=0)
                self.assertEqual(result['status'], 'INCOMPLETE')
                self.assertTrue((capture.root / 'terminal-status.json').is_file())
                self.assertFalse((capture.root / 'seal.json').exists())
            finally:
                release.set()
                capture.late_sealer.join(3)
                worker.join(1)
            self.assertTrue((capture.root / 'seal.json').is_file())

    def test_clean_completed_writer_seals_without_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            capture, segment, calls = build_capture(d, AlreadyFinished())
            before = segment.read_bytes()
            result = capture.stop('DURATION_LIMIT', timeout=0)
            self.assertEqual(result['status'], 'SEALED')
            self.assertFalse(result['drain_timeout_observed'])
            self.assertEqual(json.loads((capture.root / 'seal.json').read_text())['status'], 'SEALED')
            self.assertFalse(hasattr(capture, 'late_sealer'))
            self.assertEqual(len(calls), 1)
            self.assertEqual(before, segment.read_bytes())


if __name__ == '__main__':
    unittest.main()
