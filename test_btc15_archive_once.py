"""Small file-safety fixtures only; no live feeds or shadow deployment."""
from contextlib import redirect_stdout
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import btc15_information_archive_once as maintenance
from btc15_information_journal_v1 import information_lines
from btc15_cohort_evidence_v1 import read_information, REQUIRED_INFORMATION


def line(frame_id):
    frame = dict.fromkeys(REQUIRED_INFORMATION)
    frame.update(frame_id=frame_id, signal_only=True, orders=False)
    return json.dumps(dict(schema='BTC15_INFORMATION_JOURNAL_V1',
                           frame_id=frame_id, frame=frame)).encode()+b'\n'


class ArchiveSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'frames.jsonl'
        self.original = line('old-1')+line('old-2')+line('old-3')
        self.path.write_bytes(self.original)
        self.archive = Path(str(self.path)+'.gz')
        # The local executor prohibits even self-fd inspection. Use a proc-like
        # fixture; production still scans its entire real process namespace.
        self.proc = Path(self.tmp.name)/'123'
        (self.proc/'fd').mkdir(parents=True)
        (self.proc/'fdinfo').mkdir()
        real_check = maintenance.no_writers
        check = patch.object(maintenance, 'no_writers',
                             side_effect=lambda s: real_check(s, [self.proc]))
        check.start(); self.addCleanup(check.stop)

    def run_archive(self, health=lambda: None):
        with redirect_stdout(io.StringIO()):
            return maintenance.archive_once(self.path, len(self.original), 4096, health, pause=0)

    def test_verified_lossless_archive_and_real_reader_in_original_order(self):
        directory = Path(str(self.path)+'.segments'); directory.mkdir()
        # Filename order deliberately contradicts actual writer order.
        for name, stamp, identifier in [('z.jsonl.gz', 100, 'new-1'), ('a.jsonl.gz', 200, 'new-2')]:
            p = directory/name; p.write_bytes(gzip.compress(line(identifier)))
            os.utime(p, (stamp, stamp))
        segments = {p.name: p.read_bytes() for p in directory.iterdir()}
        result = self.run_archive()
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertFalse(self.path.exists())
        self.assertEqual(gzip.decompress(self.archive.read_bytes()), self.original)
        self.assertEqual(result['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(result['compressed_sha256'], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(result['records'], 3)
        self.assertEqual(result['compressed_bytes'], self.archive.stat().st_size)
        self.assertEqual([f['frame_id'] for f in read_information(self.path)],
                         ['old-1', 'old-2', 'old-3', 'new-1', 'new-2'])
        self.assertEqual(segments, {p.name: p.read_bytes() for p in directory.iterdir()})
        self.assertIsNone(self.run_archive())

    def test_both_representations_never_duplicate_records(self):
        self.archive.write_bytes(gzip.compress(self.original))
        self.assertEqual(b''.join(information_lines(self.path)), self.original)
        self.assertEqual(len(read_information(self.archive)), 3)

    def test_insufficient_reserve_measures_but_writes_no_archive(self):
        free = 4096+maintenance.HEADROOM
        with patch.object(maintenance.shutil, 'disk_usage', return_value=SimpleNamespace(free=free)):
            result = self.run_archive()
        self.assertIn('INSUFFICIENT_SPACE', result['error'])
        self.assertGreater(result['compressed_bytes'], 0)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.path.parent.glob('*.partial')))

    def test_open_writer_aborts_before_compression(self):
        (self.proc/'fd'/'7').symlink_to(self.path)
        (self.proc/'fdinfo'/'7').write_text('flags:\t0102001\n')
        with self.path.open('ab'):
            result = self.run_archive()
        self.assertIn('ACTIVE_WRITER', result['error'])
        self.assertNotIn('compressed_bytes', result)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_changed_source_aborts_and_preserves_it(self):
        calls = [0]
        def changing():
            calls[0] += 1
            if calls[0] == 2:
                with self.path.open('ab') as out: out.write(line('concurrent'))
        result = self.run_archive(changing)
        self.assertIn('ORIGINAL_CHANGED', result['error'])
        self.assertEqual(self.path.read_bytes(), self.original+line('concurrent'))
        self.assertFalse(self.archive.exists())

    def test_space_loss_during_write_preserves_original(self):
        calls = [0]
        def space(_):
            calls[0] += 1
            return SimpleNamespace(free=10**9 if calls[0] <= 2 else 0)
        with patch.object(maintenance.shutil, 'disk_usage', side_effect=space):
            result = self.run_archive()
        self.assertIn('OPERATING_RESERVE_THREATENED', result['error'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.path.parent.glob('*.partial')))

    def test_corrupt_decompression_cannot_delete_original(self):
        with patch.object(maintenance.gzip, 'open', return_value=io.BytesIO(b'wrong\n')):
            result = self.run_archive()
        self.assertIn('DECOMPRESSION_BYTES_DIFFER', result['error'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.archive.exists())

    def test_reader_failure_after_durable_archive_preserves_original(self):
        with patch('btc15_information_journal_v1.information_lines', return_value=iter([b'wrong\n'])):
            result = self.run_archive()
        self.assertIn('ARCHIVE_READER_DIFFERS', result['error'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(gzip.decompress(self.archive.read_bytes()), self.original)

    def test_existing_archive_is_never_overwritten(self):
        self.archive.write_bytes(b'prior evidence')
        result = self.run_archive()
        self.assertEqual(result['status'], 'ABORTED')
        self.assertEqual(self.archive.read_bytes(), b'prior evidence')
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_unreadable_process_descriptors_fail_closed(self):
        with patch.object(maintenance, 'no_writers', side_effect=PermissionError('blocked')):
            result = self.run_archive()
        self.assertIn('PermissionError', result['error'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.archive.exists())


if __name__ == '__main__': unittest.main()
