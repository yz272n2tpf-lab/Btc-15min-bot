"""Evidence-pack boundaries: one input, exact replay, safe exclusive writes."""
import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import nextgen_v2_checkpoint as pack
from test_nextgen_v2_review import MANIFEST, bundle
from test_nextgen_v2_longitudinal import later


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = bundle()
        cls.current = later(cls.first)
        cls.files = pack.build_files(cls.current, [cls.first], MANIFEST)

    def saved(self, root):
        directory = Path(root) / 'pack'
        pack.write_pack(directory, self.files)
        return directory

    def reseal(self, directory, receipt):
        raw = pack.encode(receipt)
        (directory / 'pack.json').write_bytes(raw)
        (directory / 'COMPLETE').write_bytes((pack.sha(raw) + '\n').encode())

    def test_deterministic_pack_preserves_all_inputs(self):
        before = copy.deepcopy((self.current, self.first, MANIFEST))
        self.assertEqual(pack.build_files(self.current, [self.first], MANIFEST), self.files)
        self.assertEqual((self.current, self.first, MANIFEST), before)
        receipt = pack.decode(self.files['pack.json'])
        self.assertEqual(receipt['history_count'], 1)
        for key in pack.SAFETY:
            self.assertIs(receipt[key], False)
        self.assertEqual(pack.decode(self.files['review.json'])['future_full_contracts'], 4)
        self.assertEqual(pack.decode(self.files['scorecard.json'])['latest_future_full_contracts'], 4)
        self.assertEqual(pack.decode(self.files['mechanisms.json'])['checks'], 6952)

    def test_offline_verification_has_no_network_or_file_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
            with patch.object(pack.review, 'http_reader', side_effect=AssertionError('network forbidden')):
                result = pack.verify_pack(directory)
            self.assertEqual(result['status'], 'VERIFIED_REPRODUCIBLE_PACK')
            self.assertEqual(result['files'], 16)
            self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()})

    def test_json_object_order_does_not_change_report_bytes(self):
        reordered = copy.deepcopy(MANIFEST)
        reordered['families'] = dict(reversed(list(reordered['families'].items())))
        current = copy.deepcopy(self.current)
        current['manifest'] = reordered
        first = copy.deepcopy(self.first)
        first['manifest'] = reordered
        self.assertEqual(pack.build_files(current, [first], reordered), self.files)

    def test_plain_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            (directory / 'review.md').write_text('invented winner')
            with self.assertRaisesRegex(ValueError, 'digest'):
                pack.verify_pack(directory)

    def test_resealed_forged_report_is_rejected_by_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            (directory / 'review.md').write_text('invented winner')
            receipt = pack.read_json(directory / 'pack.json')
            receipt['artifacts']['review.md'] = pack.sha((directory / 'review.md').read_bytes())
            self.reseal(directory, receipt)
            with self.assertRaisesRegex(ValueError, 'offline replay'):
                pack.verify_pack(directory)

    def test_resealed_source_provenance_forgery_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            receipt = pack.read_json(directory / 'pack.json')
            receipt['source_sha256'] = 'f' * 64
            self.reseal(directory, receipt)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                pack.verify_pack(directory)

    def test_incomplete_pack_has_no_valid_seal(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            (directory / 'COMPLETE').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                pack.verify_pack(directory)

    def test_missing_and_unexpected_files_fail(self):
        for extra in (True, False):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                directory = self.saved(temp)
                if extra:
                    (directory / 'unlisted.json').write_text('{}')
                else:
                    (directory / 'stress.json').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing or unexpected'):
                    pack.verify_pack(directory)

    def test_unsafe_inventory_is_rejected_before_path_read(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            receipt = pack.read_json(directory / 'pack.json')
            receipt['artifacts']['../outside.json'] = 'a' * 64
            self.reseal(directory, receipt)
            with self.assertRaisesRegex(ValueError, 'inventory'):
                pack.verify_pack(directory)

    def test_writer_rejects_unsafe_names_before_creating_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'pack'
            with self.assertRaisesRegex(ValueError, 'inventory'):
                pack.write_pack(directory, {**self.files, '../outside.json': b'{}'})
            self.assertFalse(directory.exists())
            self.assertFalse((Path(temp) / 'outside.json').exists())

    def test_symlink_artifact_and_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            linked = Path(temp) / 'linked'
            linked.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(ValueError):
                pack.verify_pack(linked)
            target = directory / 'review.md'
            external = Path(temp) / 'external'
            external.write_bytes(target.read_bytes())
            target.unlink()
            target.symlink_to(external)
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                pack.verify_pack(directory)

    def test_duplicate_and_nonfinite_json_is_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                pack.decode(raw)

    def test_bounded_inventory_and_file_reads(self):
        for count in (-1, True, '1', 257):
            with self.subTest(count=count), self.assertRaises(ValueError):
                pack.expected_artifacts(count)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'too_big'
            path.write_bytes(b'12345')
            with patch.object(pack, 'MAX_FILE_BYTES', 4), self.assertRaises(ValueError):
                pack.read_bytes(path)

    def test_history_order_duplicates_and_changed_manifest_fail(self):
        for current, history in ((self.first, [self.current]), (self.first, [self.first])):
            with self.assertRaises(ValueError):
                pack.validate_inputs(current, history, MANIFEST)
        changed = copy.deepcopy(self.current)
        changed['manifest']['cutoff_utc'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'manifest'):
            pack.validate_inputs(changed, [self.first], MANIFEST)

    def test_source_drift_blocks_before_report_generation(self):
        with patch.object(pack.causal, 'fingerprint', return_value='changed'), patch.object(pack.review, 'build_review') as build:
            with self.assertRaisesRegex(ValueError, 'frozen revision'):
                pack.build_files(self.current, [self.first], MANIFEST)
            build.assert_not_called()

    def test_changed_report_code_and_python_runtime_fail_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = self.saved(temp)
            with patch.object(pack, 'tool_hashes', return_value={}):
                with self.assertRaisesRegex(ValueError, 'report code'):
                    pack.verify_pack(directory)
            with patch.object(pack.platform, 'python_version', return_value='different'):
                with self.assertRaisesRegex(ValueError, 'runtime'):
                    pack.verify_pack(directory)

    def test_mid_build_report_code_drift_fails(self):
        hashes = pack.tool_hashes()
        with patch.object(pack, 'tool_hashes', side_effect=[hashes, {}]):
            with self.assertRaisesRegex(ValueError, 'changed during capture'):
                pack.build_files(self.current, [self.first], MANIFEST)

    def test_mixed_report_identity_fails(self):
        wrong = pack.decode(self.files['ledger.json'])
        wrong['source_sha256'] = 'changed'
        with patch.object(pack.ledger, 'build_ledger', return_value=wrong):
            with self.assertRaisesRegex(ValueError, 'different snapshots'):
                pack.build_files(self.current, [self.first], MANIFEST)

    def test_unsafe_report_flag_fails(self):
        wrong = pack.decode(self.files['stress.json'])
        wrong['orders'] = True
        with patch.object(pack.costs, 'build_report', return_value=wrong):
            with self.assertRaisesRegex(ValueError, 'Unsafe report flag'):
                pack.build_files(self.current, [self.first], MANIFEST)

    def test_mutating_report_fails(self):
        current = copy.deepcopy(self.current)
        original = pack.ledger.build_ledger
        def mutate(*args):
            result = original(*args)
            current['unwanted'] = True
            return result
        with patch.object(pack.ledger, 'build_ledger', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'mutated'):
                pack.build_files(current, [self.first], MANIFEST)

    def test_partial_write_does_not_mark_pack_complete(self):
        original = Path.open
        def fail(path, *args, **kwargs):
            if path.name == 'ledger.json' and args and args[0] == 'xb':
                raise OSError('simulated disk failure')
            return original(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'pack'
            with patch.object(Path, 'open', fail), self.assertRaises(OSError):
                pack.write_pack(directory, self.files)
            self.assertTrue(directory.exists())
            self.assertFalse((directory / 'COMPLETE').exists())
            with self.assertRaises(FileExistsError):
                pack.write_pack(directory, self.files)

    def test_one_live_capture_feeds_all_reports_and_existing_output_blocks_network(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'pack'
            with patch.object(pack.review, 'http_reader', return_value=object()) as reader, \
                    patch.object(pack.review, 'coherent_capture', return_value=self.current) as capture, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(pack.main(['capture', '--output', str(directory)]), 0)
                reader.assert_called_once_with(MANIFEST['service_url'])
                capture.assert_called_once()
                original = (directory / 'pack.json').read_bytes()
                self.assertEqual(pack.main(['capture', '--output', str(directory)]), 2)
                capture.assert_called_once()
                self.assertEqual((directory / 'pack.json').read_bytes(), original)

    def test_offline_cli_uses_saved_bundle_and_source_drift_blocks_live_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.json'
            source.write_bytes(pack.encode(self.current))
            with patch.object(pack.review, 'http_reader', side_effect=AssertionError('network forbidden')), redirect_stdout(io.StringIO()):
                self.assertEqual(pack.main(['capture', '--bundle', str(source), '--output', str(root / 'offline')]), 0)
                self.assertEqual(pack.main(['verify', str(root / 'offline')]), 0)
                with patch.object(pack.causal, 'fingerprint', return_value='changed'):
                    self.assertEqual(pack.main(['capture', '--output', str(root / 'blocked')]), 2)
                self.assertFalse((root / 'blocked').exists())


if __name__ == '__main__':
    unittest.main()
