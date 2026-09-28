import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from common_journal import scan, report, read_member, MAX_RECORD_BYTES


def member(value):
    return gzip.compress(json.dumps(value).encode() + b'\n', mtime=0)


class JournalIntegrity(unittest.TestCase):
    def parse(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.gz'
            path.write_bytes(data)
            damage = []
            result = list(scan(path, damage))
            self.assertEqual(path.read_bytes(), data)
            return result, damage

    def test_concatenated_members_keep_order_and_offsets(self):
        first = member({'i': 1})
        rows, damage = self.parse(first + member({'i': 2}))
        self.assertEqual([x['record']['i'] for x in rows], [1, 2])
        self.assertEqual(rows[1]['offset'], len(first))
        self.assertFalse(damage)

    def test_partial_crash_member_recovers_next_verified_member(self):
        first, broken = member({'i': 1}), member({'i': 2})[:-7]
        rows, damage = self.parse(first + broken + member({'i': 3}))
        self.assertEqual([x['record']['i'] for x in rows], [1, 3])
        self.assertEqual((damage[0]['start'], damage[0]['end']),
                         (len(first), len(first) + len(broken)))

    def test_bad_crc_is_never_accepted(self):
        bad = bytearray(member({'i': 2}))
        bad[-8] ^= 1
        rows, damage = self.parse(bytes(bad) + member({'i': 3}))
        self.assertEqual([x['record']['i'] for x in rows], [3])
        self.assertTrue(damage)

    def test_truncated_tail_is_reported_not_hidden(self):
        rows, damage = self.parse(member({'i': 1}) + member({'i': 2})[:-2])
        self.assertEqual(len(rows), 1)
        self.assertEqual(damage[0]['kind'], 'incomplete_or_damaged_tail')

    def test_nonfinite_and_multiple_records_are_invalid(self):
        for raw in (b'{"x":NaN}', b'{"i":1}\n{"i":2}'):
            rows, damage = self.parse(gzip.compress(raw))
            self.assertFalse(rows)
            self.assertTrue(damage)

    def test_decode_size_is_bounded(self):
        with self.assertRaises(ValueError):
            read_member(io.BytesIO(member({'x': 'a' * MAX_RECORD_BYTES})), 0)


if __name__ == '__main__':
    unittest.main()
